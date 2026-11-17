"""Per-user Windows startup registration for the bundled application."""
from pathlib import Path
import sys

KEY=r'Software\Microsoft\Windows\CurrentVersion\Run'
NAME='SMKWebUI'

def executable():
    return Path(__file__).resolve().parents[2]/'SMK WebUI.exe'

def status():
    path=executable();available=sys.platform=='win32' and path.is_file()
    enabled=False
    if available:
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,KEY) as key:value,_=winreg.QueryValueEx(key,NAME)
            enabled=value==f'"{path}" --background'
        except FileNotFoundError:pass
    return dict(available=available,enabled=enabled)

def set_enabled(enabled):
    if type(enabled) is not bool:raise ValueError('Expected a startup switch')
    if not status()['available']:raise ValueError('Startup requires the Windows app package')
    import winreg
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER,KEY) as key:
        if enabled:winreg.SetValueEx(key,NAME,0,winreg.REG_SZ,f'"{executable()}" --background')
        else:
            try:winreg.DeleteValue(key,NAME)
            except FileNotFoundError:pass
    return status()
