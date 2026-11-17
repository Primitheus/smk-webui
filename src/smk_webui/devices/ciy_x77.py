"""Adapter for the verified CIY X77 UK ISO fast-streaming firmware."""
import json
from pathlib import Path
from ..transport import Transport

ID='ciy-x77-iso-fast-v1'
NAME='CIY X77 · UK ISO'
FIRMWARE='SMK X77 Fast v1'
KEYS=json.loads(Path(__file__).with_name('ciy_x77_iso.json').read_text())

def open_device():
    return Transport()
