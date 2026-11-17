"""Build a portable Windows app with the local CPython runtime and MinGW."""
import argparse
import ast
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

root=Path(__file__).resolve().parents[1]
release=ast.literal_eval((root/'src/smk_webui/__init__.py').read_text().split('__version__ =',1)[1].strip())
parser=argparse.ArgumentParser();parser.add_argument('--gcc',default='gcc');parser.add_argument('--windres',default='windres');args=parser.parse_args()
output=root/'dist'/'SMK WebUI';runtime=output/'runtime'
runtime.mkdir(parents=True,exist_ok=True)
base=Path(sys.base_prefix)
version=f'python{sys.version_info.major}{sys.version_info.minor}'
for pattern in ['python.exe','pythonw.exe','python*.dll','vcruntime*.dll']:
    for source in base.glob(pattern):shutil.copy2(source,runtime/source.name)
shutil.copytree(base/'DLLs',runtime/'DLLs',dirs_exist_ok=True)
with zipfile.ZipFile(runtime/(version+'.zip'),'w',zipfile.ZIP_DEFLATED) as archive:
    for path in (base/'Lib').rglob('*'):
        relative=path.relative_to(base/'Lib')
        if path.is_file() and path.suffix=='.py' and not set(relative.parts)&{'site-packages','test','tests','__pycache__','idlelib','ensurepip','tkinter','turtledemo'}:archive.write(path,relative)
(runtime/(version+'._pth')).write_text(version+'.zip\nDLLs\n../app\n',encoding='utf-8')
shutil.copytree(root/'src'/'smk_webui',output/'app'/'smk_webui',dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
shutil.copy2(root/'LICENSE',output/'LICENSE')
shutil.copy2(root/'README.md',output/'README.md')
for name in ('Install.ps1','Install.cmd','Uninstall.ps1'):shutil.copy2(root/'scripts'/name,output/name)
shutil.copy2(base/'LICENSE.txt',runtime/'LICENSE.txt')
resources=root/'build';resources.mkdir(exist_ok=True)
subprocess.run([args.gcc,'-O2','-s','-shared',str(root/'scripts/audio_capture.c'),'-o',str(output/'app/smk_webui/audio_capture.dll'),'-lole32','-luuid','-lm'],check=True)
icon=root/'src'/'smk_webui'/'web'/'icon.ico'
(resources/'icon.rc').write_text('1 ICON "'+icon.as_posix()+'"\n',encoding='utf-8')
subprocess.run([args.windres,str(resources/'icon.rc'),'-O','coff','-o',str(resources/'icon.o')],check=True)
subprocess.run([args.gcc,'-Os','-s','-municode','-mwindows',str(root/'scripts'/'launcher.c'),str(resources/'icon.o'),'-o',str(output/'SMK WebUI.exe')],check=True)
package=root/'dist'/f'smk-webui-{release}-windows-x64.zip'
with zipfile.ZipFile(package,'w',zipfile.ZIP_DEFLATED) as archive:
    for path in output.rglob('*'):
        if path.is_file() and 'data' not in path.relative_to(output).parts and '__pycache__' not in path.parts:archive.write(path,path.relative_to(output.parent))
shutil.copy2(package,root/'dist'/'smk-webui-windows.zip')
(root/'dist'/'SHA256SUMS').write_text(hashlib.sha256(package.read_bytes()).hexdigest()+'  '+package.name+'\n',encoding='ascii')
print(package)
