"""Validated, atomic local settings storage. No input events are stored."""
import json
import os
from pathlib import Path
import tempfile
import math
from . import studio

DEFAULT_OPTIONS={'reactive_fade':1.5,'ripple_fade':2.0,'ripple_width':1.6}

def validate_options(value):
    if not isinstance(value,dict) or set(value)!=set(DEFAULT_OPTIONS): raise ValueError('Invalid effect options')
    result={}
    for key,v in value.items():
        low,high=(.25,6) if key=='ripple_width' else (.2,10)
        if type(v) not in (int,float) or not math.isfinite(v) or not low<=v<=high:
            raise ValueError('Effect option out of range: '+key)
        result[key]=float(v)
    return result


def validate(data):
    def integer(value,low,high):
        if type(value) is not int or not low<=value<=high: raise ValueError('Invalid settings value')
        return value
    def rgb(value):
        if not isinstance(value,(list,tuple)) or len(value)!=3: raise ValueError('Invalid RGB colour')
        return tuple(integer(channel,0,255) for channel in value)
    def mapping(name,keys,low,high):
        value=data[name]
        if not isinstance(value,dict):raise ValueError('Invalid '+name)
        value=dict(value)
        if name in ('speeds','brightness'):value.setdefault('8',5 if name=='speeds' else 100)
        if set(value)!={str(k) for k in keys}: raise ValueError('Invalid '+name)
        return {int(k):integer(v,low,high) for k,v in value.items()}
    if not isinstance(data,dict) or type(data.get('version')) is not int or data['version']!=1:
        raise ValueError('Unsupported settings version')
    try:
        mode=integer(data['mode'],0,8)
        if not isinstance(data['colours'],list) or len(data['colours'])!=88: raise ValueError('Expected 88 colours')
        colours=[rgb(v) for v in data['colours']]
        speeds=mapping('speeds',(1,2,4,5,6,7,8),1,10)
        brightness=mapping('brightness',(0,1,2,4,5,6,7,8),0,100)
        reactive=data['reactive_colours']
        if not isinstance(reactive,dict) or set(reactive)!={'6','7'}: raise ValueError('Invalid reactive colours')
        reactive={int(k):rgb(v) for k,v in reactive.items()}
        background=data.get('background_colours',{'6':[0,0,0],'7':[0,0,0]})
        if not isinstance(background,dict) or set(background)!={'6','7'}: raise ValueError('Invalid background colours')
        background={int(k):rgb(v) for k,v in background.items()}
        directions=data.get('directions',{'4':1,'5':3})
        if not isinstance(directions,dict) or set(directions)!={'4','5'}: raise ValueError('Invalid directions')
        directions={4:integer(directions['4'],0,1),5:integer(directions['5'],2,3)}
        options=validate_options(data.get('effect_options',DEFAULT_OPTIONS))
    except KeyError as exc:
        raise ValueError('Missing settings field') from exc
    return dict(mode=mode,colours=colours,speeds=speeds,brightness=brightness,reactive_colours=reactive,
                background_colours=background,directions=directions,effect_options=options,studio=studio.validate(data.get('studio',{'version':1,'layers':[studio.layer()]})))


def save(path,data):
    path=Path(path)
    validate(data)
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=None
    try:
        with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=path.parent,
                                         prefix=path.name+'.',suffix='.tmp',delete=False) as stream:
            temporary=Path(stream.name)
            json.dump(data,stream,indent=2)
            stream.write('\n');stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,path)
        temporary=None
    finally:
        if temporary is not None: temporary.unlink(missing_ok=True)
