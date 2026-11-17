from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock, patch
from smk_webui import startup


class StartupTests(TestCase):
    def test_registration_and_removal_use_bundled_executable(self):
        values={}
        handle=MagicMock()
        def query(key,name):
            if name not in values:raise FileNotFoundError
            return values[name],1
        registry=SimpleNamespace(HKEY_CURRENT_USER=1,REG_SZ=1,
            OpenKey=lambda *args:handle,CreateKey=lambda *args:handle,
            QueryValueEx=query,SetValueEx=lambda key,name,res,kind,value:values.update({name:value}),
            DeleteValue=lambda key,name:values.pop(name))
        with patch.dict('sys.modules',winreg=registry),patch.object(startup.sys,'platform','win32'), \
             patch.object(startup,'executable',return_value=Path('C:/Apps/SMK WebUI/SMK WebUI.exe')), \
             patch.object(Path,'is_file',return_value=True):
            self.assertFalse(startup.status()['enabled'])
            self.assertTrue(startup.set_enabled(True)['enabled'])
            self.assertEqual(values[startup.NAME],'"C:\\Apps\\SMK WebUI\\SMK WebUI.exe" --background')
            self.assertFalse(startup.set_enabled(False)['enabled'])
            with self.assertRaises(ValueError):startup.set_enabled('yes')
