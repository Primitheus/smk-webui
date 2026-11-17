/* WASAPI loopback capture and a bounded 16-band spectrum. No audio files. */
#define COBJMACROS
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <initguid.h>
#include <mmdeviceapi.h>
#include <audioclient.h>
#include <mmreg.h>
#include <math.h>
#include <stdlib.h>
#include <string.h>
#define N 2048
#define BANDS 16
#define API __declspec(dllexport)
typedef struct {
    IMMDeviceEnumerator *enumerator; IMMDevice *device;
    IAudioClient *client; IAudioCaptureClient *capture;
    WAVEFORMATEX *format; LPWSTR id;
    float ring[N]; unsigned cursor,filled; int floating;
    ULONGLONG last_data,last_device_check;
} Audio;
static void spectrum(const float *ring,unsigned cursor,unsigned filled,unsigned rate,float *out) {
    double re[N],im[N]; unsigned i,j,k,len;
    memset(out,0,sizeof(float)*BANDS);
    if(filled<N || rate<8000)return;
    for(i=0;i<N;i++){re[i]=ring[(cursor+i)%N]*(.5-.5*cos(6.283185307179586*i/(N-1)));im[i]=0;}
    for(i=1,j=0;i<N;i++){unsigned bit=N>>1;for(;j&bit;bit>>=1)j^=bit;j^=bit;if(i<j){double t=re[i];re[i]=re[j];re[j]=t;}}
    for(len=2;len<=N;len<<=1){double a=-6.283185307179586/len;for(i=0;i<N;i+=len)for(j=0;j<len/2;j++){
        unsigned p=i+j,q=p+len/2;double wr=cos(a*j),wi=sin(a*j),tr=wr*re[q]-wi*im[q],ti=wr*im[q]+wi*re[q];
        re[q]=re[p]-tr;im[q]=im[p]-ti;re[p]+=tr;im[p]+=ti;
    }}
    for(i=0;i<BANDS;i++){
        double low=60*pow(200.,i/16.),high=60*pow(200.,(i+1)/16.),peak=0;
        unsigned first=(unsigned)ceil(low*N/rate),last=(unsigned)ceil(high*N/rate);
        if(first<1)first=1;
        if(last<=first)last=first+1;
        if(last>N/2)last=N/2;
        for(k=first;k<last;k++){double mag=sqrt(re[k]*re[k]+im[k]*im[k])*4/N;if(mag>peak)peak=mag;}
        /* Preserve musical dynamics instead of flattening most audible levels
           into the upper part of a logarithmic meter. */
        double level=peak>.001?sqrt(peak):0;
        out[i]=(float)(level<0?0:level>1?1:level);
    }
}
API void smk_audio_close(void *context) {
    Audio *a=context;if(!a)return;
    if(a->client)IAudioClient_Stop(a->client);
    if(a->capture)IAudioCaptureClient_Release(a->capture);
    if(a->client)IAudioClient_Release(a->client);
    if(a->device)IMMDevice_Release(a->device);
    if(a->enumerator)IMMDeviceEnumerator_Release(a->enumerator);
    CoTaskMemFree(a->format);CoTaskMemFree(a->id);free(a);CoUninitialize();
}
API HRESULT smk_audio_open(void **context) {
    HRESULT hr;Audio *a;*context=NULL;
    hr=CoInitializeEx(NULL,COINIT_MULTITHREADED);if(FAILED(hr))return hr;
    a=calloc(1,sizeof(*a));if(!a){CoUninitialize();return E_OUTOFMEMORY;}
    hr=CoCreateInstance(&CLSID_MMDeviceEnumerator,NULL,CLSCTX_ALL,&IID_IMMDeviceEnumerator,(void**)&a->enumerator);if(FAILED(hr))goto fail;
    hr=IMMDeviceEnumerator_GetDefaultAudioEndpoint(a->enumerator,eRender,eMultimedia,&a->device);if(FAILED(hr))goto fail;
    hr=IMMDevice_GetId(a->device,&a->id);if(FAILED(hr))goto fail;
    hr=IMMDevice_Activate(a->device,&IID_IAudioClient,CLSCTX_ALL,NULL,(void**)&a->client);if(FAILED(hr))goto fail;
    hr=IAudioClient_GetMixFormat(a->client,&a->format);if(FAILED(hr))goto fail;
    WORD tag=a->format->wFormatTag,bits=a->format->wBitsPerSample;
    if(tag==WAVE_FORMAT_EXTENSIBLE && a->format->cbSize>=22)tag=(WORD)((WAVEFORMATEXTENSIBLE*)a->format)->SubFormat.Data1;
    a->floating=tag==WAVE_FORMAT_IEEE_FLOAT;
    if(!a->format->nChannels||a->format->nChannels>32||a->format->nSamplesPerSec<8000||
       !((a->floating&&bits==32)||(tag==WAVE_FORMAT_PCM&&(bits==16||bits==24||bits==32)))||
       a->format->nBlockAlign!=a->format->nChannels*(bits/8)){hr=AUDCLNT_E_UNSUPPORTED_FORMAT;goto fail;}
    hr=IAudioClient_Initialize(a->client,AUDCLNT_SHAREMODE_SHARED,AUDCLNT_STREAMFLAGS_LOOPBACK,1000000,0,a->format,NULL);if(FAILED(hr))goto fail;
    hr=IAudioClient_GetService(a->client,&IID_IAudioCaptureClient,(void**)&a->capture);if(FAILED(hr))goto fail;
    hr=IAudioClient_Start(a->client);if(FAILED(hr))goto fail;
    a->last_data=a->last_device_check=GetTickCount64();*context=a;return S_OK;
fail:smk_audio_close(a);return hr;
}
API HRESULT smk_audio_read(void *context,float *out) {
    Audio *a=context;HRESULT hr;UINT32 count=0;ULONGLONG now=GetTickCount64();
    if(!a||!out)return E_POINTER;
    memset(out,0,sizeof(float)*BANDS);
    if(now-a->last_device_check>1000){
        IMMDevice *current=NULL;LPWSTR id=NULL;a->last_device_check=now;
        hr=IMMDeviceEnumerator_GetDefaultAudioEndpoint(a->enumerator,eRender,eMultimedia,&current);
        if(SUCCEEDED(hr))hr=IMMDevice_GetId(current,&id);
        int same=SUCCEEDED(hr)&&wcscmp(a->id,id)==0;CoTaskMemFree(id);if(current)IMMDevice_Release(current);
        if(!same)return AUDCLNT_E_DEVICE_INVALIDATED;
    }
    hr=IAudioCaptureClient_GetNextPacketSize(a->capture,&count);if(FAILED(hr))return hr;
    unsigned packets=0;
    while(count && packets++<256){
        BYTE *data;UINT32 frames;DWORD flags;
        hr=IAudioCaptureClient_GetBuffer(a->capture,&data,&frames,&flags,NULL,NULL);if(FAILED(hr))return hr;
        if(flags&AUDCLNT_BUFFERFLAGS_DATA_DISCONTINUITY){a->filled=0;a->cursor=0;}
        unsigned bytes=a->format->wBitsPerSample/8,channels=a->format->nChannels;
        for(UINT32 i=0;i<frames;i++){
            float sample=0;
            if(!(flags&AUDCLNT_BUFFERFLAGS_SILENT))for(unsigned ch=0;ch<channels;ch++){
                BYTE *p=data+i*a->format->nBlockAlign+ch*bytes;float v=0;
                if(a->floating)memcpy(&v,p,4);
                else if(bytes==2){short v16;memcpy(&v16,p,2);v=v16/32768.f;}
                else if(bytes==4){LONG v32;memcpy(&v32,p,4);v=v32/2147483648.f;}
                else {LONG v24=p[0]|(p[1]<<8)|(p[2]<<16);if(v24&0x800000)v24|=(LONG)0xff000000;v=v24/8388608.f;}
                if(isfinite(v))sample+=v/channels;
            }
            a->ring[a->cursor]=sample;a->cursor=(a->cursor+1)%N;if(a->filled<N)a->filled++;
        }
        a->last_data=now;hr=IAudioCaptureClient_ReleaseBuffer(a->capture,frames);if(FAILED(hr))return hr;
        hr=IAudioCaptureClient_GetNextPacketSize(a->capture,&count);if(FAILED(hr))return hr;
    }
    if(now-a->last_data<150)spectrum(a->ring,a->cursor,a->filled,a->format->nSamplesPerSec,out);
    else a->filled=0;
    return S_OK;
}
#ifdef SMK_AUDIO_TEST
API void smk_audio_test(const float *samples,unsigned rate,float *out){spectrum(samples,0,N,rate,out);}
#endif
