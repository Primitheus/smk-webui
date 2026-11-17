import unittest
from smk_webui import onboard

class OnboardTests(unittest.TestCase):
    def setUp(self):
        self.raw=bytes((1,0,0,0))+bytes(onboard.SIZE-4)

    def test_extended_control_transfer(self):
        data=bytes((2,0,0,0))+bytes(586)+bytes.fromhex(''.join(c[1:] for c in onboard.PALETTE))
        memory=bytearray(data);reply=bytes(8)
        def get(report):
            return bytes((12,83,77,75,2,2,31,1)) if report==12 else reply
        def put(packet):
            nonlocal reply
            op=packet[1]&15;offset=int.from_bytes(packet[2:4],'little');payload=bytes(3)
            if op==1:payload=bytes(memory[offset:offset+3]).ljust(3,b'\0')
            if op==2:memory[offset:min(offset+3,638)]=packet[4:4+min(3,638-offset)]
            reply=packet[:4]+payload+b'\0'
        control=onboard.Control(get,put)
        self.assertTrue(control.capabilities['custom_palette'])
        control.write(data)
        self.assertEqual(control.read(),data)

    def test_custom_palette_roundtrip(self):
        raw=bytes((2,0,0,0))+bytes(586)+bytes.fromhex(''.join(c[1:] for c in onboard.PALETTE))
        value=onboard.decode(raw);value['palette'][3]='#123456'
        encoded=onboard.encode(value,raw)
        self.assertEqual(len(encoded),638)
        self.assertEqual(onboard.decode(encoded),value)
        value['palette'][0]='#ffffff'
        with self.assertRaises(ValueError):onboard.encode(value,raw)

    def test_factory_colours_and_fn_labels(self):
        from smk_webui.onboard import default_presets,fn_description,encode,decode,SIZE
        presets=default_presets()
        self.assertEqual([len(p) for p in presets],[108]*5)
        self.assertEqual(presets[1][38],2)
        self.assertEqual(presets[1][0],0)
        self.assertEqual(presets[2][88],9)
        self.assertEqual(fn_description(0xb3),'File Explorer')
        self.assertEqual(fn_description(0xfffe),'Direct (WebUI)')
        raw=bytes([1,4])+bytes(SIZE-2)
        draft=decode(raw);draft['reset_all']=True;draft['presets']=presets
        self.assertEqual(encode(draft,raw)[1],0)

    def test_roundtrip_preserves_modes_and_shortcuts(self):
        value=onboard.decode(self.raw)
        value['presets'][3][86]=2
        value['bindings'][73]={'key':6,'mods':1}
        value['bindings'][74]={'key':255,'mods':2}
        value['macros'][1]=[{'key':6,'mods':1,'delay':100},{'key':25,'mods':1,'delay':200}]
        encoded=onboard.encode(value,self.raw)
        self.assertEqual(len(encoded),590)
        self.assertEqual(onboard.decode(encoded),value)

    def test_fn_and_invalid_macros_are_rejected(self):
        value=onboard.decode(self.raw);value['bindings'][99]={'key':4,'mods':0}
        with self.assertRaises(ValueError):onboard.encode(value,self.raw)
        value=onboard.decode(self.raw);value['macros'][0]=[{'key':4,'mods':0,'delay':25}]
        with self.assertRaises(ValueError):onboard.encode(value,self.raw)
        value['macros'][0]=[{'key':4,'mods':0,'delay':100}]*9
        with self.assertRaises(ValueError):onboard.encode(value,self.raw)

    def test_failed_upload_aborts_without_commit(self):
        control=object.__new__(onboard.Control);calls=[]
        def command(op,offset=0,data=b''):
            calls.append(op)
            if op==2:raise RuntimeError('Disconnected')
        control.command=command
        with self.assertRaises(RuntimeError):control.write(self.raw)
        self.assertEqual(calls,[3,2,5])

    def test_save_requires_readback_match(self):
        control=object.__new__(onboard.Control);control.command=lambda *args:bytes(3)
        control.read=lambda:bytes(onboard.SIZE)
        with self.assertRaisesRegex(RuntimeError,'readback'):control.write(self.raw)

    def test_hid_upload_and_readback(self):
        memory=bytearray(self.raw);reply=bytes(8);commands=[]
        def get_feature(report):
            return bytes((12,83,77,75,2,0,31,1)) if report==12 else reply
        def set_feature(packet):
            nonlocal reply
            self.assertEqual(len(packet),8)
            command=packet[1]&15;offset=int.from_bytes(packet[2:4],'little');commands.append(command)
            payload=bytes(3)
            if command==1:payload=bytes(memory[offset:offset+3]).ljust(3,b'\0')
            if command==2:memory[offset:min(offset+3,onboard.SIZE)]=packet[4:4+min(3,onboard.SIZE-offset)]
            reply=packet[:4]+payload+b'\0'
        control=onboard.Control(get_feature,set_feature)
        self.assertEqual(control.capabilities['layout'],'UK ISO')
        data=bytearray(self.raw);data[4]=0x32
        control.write(bytes(data))
        self.assertEqual(control.read(),bytes(data))
        self.assertEqual(commands[0],3)
        self.assertIn(4,commands)

if __name__=='__main__':unittest.main()
