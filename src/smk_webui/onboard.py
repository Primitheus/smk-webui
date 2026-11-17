"""Versioned X77 configuration codec and HID control messages."""
import time

SIZE=590
EXTENDED_SIZE=638
BINDINGS=274
LENGTHS=490
SEQUENCES=494
PALETTE=['#000000','#ffffff','#ff0000','#ff4000','#ffa000','#ffff00','#80ff00','#00ff00',
         '#00ff80','#00ffff','#0080ff','#0000ff','#8000ff','#ff00ff','#ff0080','#ff80c0']
EFFECTS=['Radial wave','Rainbow wave','Vertical wave','White','Off','Breathing','Colour cycle','Reactive typing','Ripple','Scanner']

def decode(data):
    if (len(data),data[0]) not in ((SIZE,1),(EXTENDED_SIZE,2)) or data[1]>4 or data[2] or data[3]:raise ValueError('Unsupported keyboard configuration')
    if any(data[LENGTHS+i]>8 for i in range(4)):raise ValueError('Invalid macro length')
    result=dict(version=data[0],presets=[[(data[4+p*54+i//2]>>((i%2)*4))&15 for i in range(108)] for p in range(5)],
                bindings=[dict(key=data[BINDINGS+i*2],mods=data[BINDINGS+i*2+1]) for i in range(108)],
                macros=[[dict(key=data[SEQUENCES+p*24+i*3],mods=data[SEQUENCES+p*24+i*3+1],delay=data[SEQUENCES+p*24+i*3+2]*10) for i in range(data[LENGTHS+p])] for p in range(4)])
    if len(data)==EXTENDED_SIZE:result['palette']=['#'+data[i:i+3].hex() for i in range(590,638,3)]
    encode(result,data)
    return result

def integer(value,low,high):
    if type(value)!=int or not low<=value<=high:raise ValueError(f'Expected integer between {low} and {high}')
    return value

def encode(value,original):
    if not isinstance(value,dict) or value.get('version') not in (1,2):raise ValueError('Invalid configuration version')
    data=bytearray(original)
    if (len(data),value['version']) not in ((SIZE,1),(EXTENDED_SIZE,2)) or value['version']!=data[0]:raise ValueError('Invalid configuration size')
    if len(data)==EXTENDED_SIZE:
        colours=value.get('palette')
        if not isinstance(colours,list) or len(colours)!=16 or not isinstance(colours[0],str) or colours[0].lower()!='#000000':raise ValueError('Expected 15 RGB colours plus Off')
        for i,colour in enumerate(colours):
            if not isinstance(colour,str) or len(colour)!=7 or not colour.startswith('#'):raise ValueError('Invalid palette colour')
            data[590+i*3:593+i*3]=bytes.fromhex(colour[1:])
    if value.get('reset_all'):data[1]=0
    presets=value.get('presets');bindings=value.get('bindings');macros=value.get('macros')
    if not isinstance(presets,list) or len(presets)!=5 or not isinstance(bindings,list) or len(bindings)!=108 or not isinstance(macros,list) or len(macros)!=4:raise ValueError('Expected five colour modes, 108 bindings and four macros')
    for p,keys in enumerate(presets):
        if not isinstance(keys,list) or len(keys)!=108:raise ValueError('Invalid colour mode')
        for i in range(54):data[4+p*54+i]=integer(keys[i*2],0,15)|(integer(keys[i*2+1],0,15)<<4)
    for i,binding in enumerate(bindings):
        key=integer(binding['key'],0,255);mods=integer(binding['mods'],0,255)
        if i==99 and (key or mods):raise ValueError('Fn must remain available')
        if key==255:
            integer(mods,1,4)
        elif key not in (0,254) and not 4<=key<160:raise ValueError('Unsupported HID key')
        data[BINDINGS+i*2:BINDINGS+i*2+2]=bytes((key,mods))
    for p,steps in enumerate(macros):
        if not isinstance(steps,list) or len(steps)>8:raise ValueError('A macro can contain up to eight steps')
        data[LENGTHS+p]=len(steps);data[SEQUENCES+p*24:SEQUENCES+(p+1)*24]=bytes(24)
        for i,step in enumerate(steps):
            key=integer(step['key'],0,159);mods=integer(step['mods'],0,255);delay=integer(step['delay'],0,2550)
            if key and key<4:raise ValueError('Unsupported macro key')
            if delay%10:raise ValueError('Delays must be multiples of 10 ms')
            data[SEQUENCES+p*24+i*3:SEQUENCES+p*24+i*3+3]=bytes((key,mods,delay//10))
    return bytes(data)

class Control:
    def __init__(self,get_feature,set_feature):
        self.get=get_feature;self.set=set_feature;self.sequence=0
        raw=self.get(12)
        if raw[:4]!=b'\x0cSMK' or raw[4]!=2:raise ValueError('Unsupported firmware control protocol')
        self.size=EXTENDED_SIZE if raw[5]>=2 else SIZE
        self.capabilities=dict(custom_palette=raw[5]>=2,version=f'{raw[4]}.{raw[5]}',layout='UK ISO' if raw[7]==1 else 'ANSI',
                               flags=raw[6],colour_modes=5,macros=4,macro_steps=8)

    def command(self,command,offset=0,data=b''):
        self.sequence=(self.sequence+1)&15;tag=(self.sequence<<4)|command
        request=bytes((11,tag,offset&255,offset>>8))+bytes(data).ljust(3,b'\0')+b'\0'
        self.set(request)
        deadline=time.monotonic()+2
        while time.monotonic()<deadline:
            reply=self.get(11)
            if reply[:4]==request[:4]:
                if reply[7]:raise RuntimeError('Keyboard is busy editing/saving or rejected the configuration' if reply[7]==1 else 'Keyboard rejected the command')
                return reply[4:7]
            time.sleep(.003)
        raise TimeoutError('Keyboard control command timed out')

    def read(self):
        result=b''.join(self.command(1,offset) for offset in range(0,self.size,3))[:self.size]
        decode(result)
        return result

    def write(self,data):
        if len(data)!=getattr(self,'size',SIZE):raise ValueError('Invalid configuration size')
        self.command(3)
        try:
            for offset in range(0,len(data),3):self.command(2,offset,data[offset:offset+3])
            self.command(4)
        except Exception:
            try:self.command(5)
            except Exception:pass
            raise
        deadline=time.monotonic()+10
        while time.monotonic()<deadline:
            status=self.command(6)
            if not status[0]:
                if status[2]&1:raise RuntimeError('Keyboard could not verify the save. Previous flash slot is retained.')
                if self.read()!=data:raise RuntimeError('Keyboard configuration readback differs')
                return
            time.sleep(.02)
        raise TimeoutError('Keyboard save timed out')


def default_presets():
    def colour(preset,cell):
        row,col=divmod(cell,18)
        if row==4:col=1 if col==14 else col+1 if 1<=col<=10 else col
        if preset==0:return 10 if row==5 else 1 if row in (2,3) else 9 if row==1 else 12
        if preset==1:return 2 if cell in (38,55,56,57,88,105,106,107) else 3 if row==1 and 1<=col<=5 else 11 if row==5 else 0
        if preset==2:return 9 if cell in (88,105,106,107) else 13 if row==0 else 12 if row==5 else 11
        if preset==3:return [12,13,14,2,3,4,5][min(6,col*7//18)]
        return [12,10,9,8,7,12][row]
    return [[colour(preset,cell) for cell in range(108)] for preset in range(5)]


def fn_description(code):
    names={0:'No action',1:'Base key',0xa8:'Mute',0xa9:'Volume up',0xaa:'Volume down',
           0xab:'Next track',0xac:'Previous track',0xad:'Stop media',0xae:'Play / pause',
           0xb1:'Mail',0xb2:'Calculator',0xb3:'File Explorer',0xb5:'Browser home',0xfffe:'Direct (WebUI)'}
    custom=['Next lighting effect','Windows key lock','Brightness up','Brightness down','Speed up','Speed down',
            'Colour forward','Colour back','Reset lighting','Radial wave','Rainbow wave','Vertical wave','White','Off',
            'CM1','CM2','CM3','CM4','CM5']
    names.update({0x7e40+i:name for i,name in enumerate(custom)})
    return names.get(code,f'Keycode 0x{code:04X}')
