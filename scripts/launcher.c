#ifndef UNICODE
#define UNICODE
#endif
#include <windows.h>
#include <wchar.h>

int WINAPI wWinMain(HINSTANCE instance,HINSTANCE previous,LPWSTR arguments,int show) {
    wchar_t directory[32768], executable[32768], command[32768];
    if (!GetModuleFileNameW(NULL,directory,32768)) return 1;
    wchar_t *slash=wcsrchr(directory,L'\\');
    if (!slash) return 1;
    *slash=0;
    if (swprintf(executable,32768,L"%ls\\runtime\\pythonw.exe",directory)<0) return 1;
    if (swprintf(command,32768,L"\"%ls\" -m smk_webui %ls",executable,arguments)<0) return 1;
    STARTUPINFOW startup={0}; startup.cb=sizeof(startup);
    PROCESS_INFORMATION process={0};
    if (!CreateProcessW(executable,command,NULL,NULL,FALSE,CREATE_NO_WINDOW,NULL,directory,&startup,&process)) {
        MessageBoxW(NULL,L"The bundled runtime could not start. Extract the complete app folder first.",L"SMK WebUI",MB_OK|MB_ICONERROR);
        return 1;
    }
    CloseHandle(process.hThread);CloseHandle(process.hProcess);return 0;
}
