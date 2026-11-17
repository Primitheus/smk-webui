"""Bounded declarative lighting layers. No expressions or executable scripts."""
import colorsys
import math

TYPES=['Solid','Gradient','Rainbow Wave','Rainbow Wheel','Breathing','Ripple','Reactive','Sparkle','Comet','Scanner','Plasma','Aurora','Fire','Rain','Checker','Orbit','Audio Spectrum','Audio Pulse','Screen Colours']
BLENDS=['Normal','Add','Screen','Multiply']
MASKS=['All','WASD','Arrows','Modifiers','Function Row','Custom']

def layer(kind='Rainbow Wave',**overrides):
    return dict(dict(name=kind,type=kind,enabled=True,blend='Normal',opacity=100,
                     colour='#ff397e',secondary='#48ffd5',speed=1,scale=3,angle=0,
                     density=.3,duration=2,mask='All',cells=[],sensitivity=1.4,smoothing=.6,noise_gate=.05,auto_level=True,screen_monitor='',screen_region=[0,0,100,100],screen_mode='Zones',saturation=1,screen_brightness=1),**overrides)

def validate(value):
    if not isinstance(value,dict) or not {'version','layers'}<=set(value) or set(value)-{'version','layers','boost'} or type(value['version']) is not int or value['version']!=1:
        raise ValueError('Expected a version 1 layer scene')
    boost=value.get('boost',0)
    if type(boost) not in (int,float) or not math.isfinite(boost) or not 0<=boost<=100:raise ValueError('Invalid colour boost')
    layers=value['layers']
    if not isinstance(layers,list) or not 1<=len(layers)<=8:raise ValueError('Use 1–8 layers')
    result=[]
    for item in layers:
        if not isinstance(item,dict) or set(item)-set(layer()):raise ValueError('Unknown layer property')
        p=layer(**item)
        if not isinstance(p['name'],str) or not 1<=len(p['name'])<=48:raise ValueError('Layer name must be 1–48 characters')
        if p['type'] not in TYPES or p['blend'] not in BLENDS or p['mask'] not in MASKS:raise ValueError('Unknown effect, blend or mask')
        if type(p['enabled']) is not bool:raise ValueError('Invalid layer visibility')
        if type(p['auto_level']) is not bool:raise ValueError('Invalid automatic audio level')
        if not isinstance(p['screen_monitor'],str) or len(p['screen_monitor'])>128:raise ValueError('Invalid display')
        if p['screen_mode'] not in ('Zones','Average'):raise ValueError('Invalid screen mapping')
        region=p['screen_region']
        if not isinstance(region,list) or len(region)!=4 or any(type(v) not in (int,float) or not math.isfinite(v) for v in region):raise ValueError('Invalid screen region')
        x,y,width,height=region
        if not (0<=x<=99 and 0<=y<=99 and 1<=width<=100 and 1<=height<=100 and x+width<=100 and y+height<=100):raise ValueError('Region must fit within the display')
        for key,lo,hi in [('opacity',0,100),('speed',.1,4),('scale',.5,12),('angle',0,360),('density',.02,1),('duration',.2,10),('sensitivity',.25,4),('smoothing',0,1),('noise_gate',0,.5),('saturation',0,2),('screen_brightness',0,2)]:
            v=p[key]
            if type(v) not in (int,float) or not math.isfinite(v) or not lo<=v<=hi:raise ValueError('Invalid '+key)
        for key in ('colour','secondary'):
            c=p[key]
            if not isinstance(c,str) or len(c)!=7 or c[0]!='#' or any(ch not in '0123456789abcdefABCDEF' for ch in c[1:]):raise ValueError('Invalid colour')
            try:bytes.fromhex(c[1:])
            except ValueError:raise ValueError('Invalid colour') from None
            p[key]=c.lower()
        if not isinstance(p['cells'],list) or len(p['cells'])>108 or any(type(c) is not int or not 0<=c<108 for c in p['cells']):raise ValueError('Invalid key mask')
        p['cells']=sorted(set(p['cells']));result.append(p)
    return dict(version=1,layers=result,boost=boost)

def masked(p,key):
    c=key['cell'];mask=p['mask']
    return mask=='All' or (mask=='WASD' and c in (38,55,56,57)) or (mask=='Arrows' and c in (88,105,106,107)) or (mask=='Modifiers' and c in (72,85,90,91,92,98,99,100,102)) or (mask=='Function Row' and c<18) or (mask=='Custom' and c in p['cells'])

def render(scene,keys,t,events,now,brightness=1,audio=None,screen=None):
    pixels=[[0.,0.,0.] for _ in range(108)]
    for layer_index,p in enumerate(scene['layers']):
        if not p['enabled']:continue
        a=tuple(v/255 for v in bytes.fromhex(p['colour'][1:]));b=tuple(v/255 for v in bytes.fromhex(p['secondary'][1:]))
        angle=math.radians(p['angle']);speed=p['speed'];phase=t*speed;scale=p['scale'];kind=p['type']
        screen_grid=screen.get(layer_index) if kind=='Screen Colours' and screen else None
        screen_average=tuple(sum(c[i] for c in screen_grid)/len(screen_grid) for i in range(3)) if screen_grid and p.get('screen_mode','Zones')=='Average' else None
        for index,k in enumerate(keys):
            if not masked(p,k):continue
            x=k['x'];y=k['y'];u=x*math.cos(angle)+y*math.sin(angle);r=math.hypot((x-9)/2,y-2.5)
            mix=0.;alpha=1.;colour=None
            if kind=='Screen Colours':
                grid=screen_grid
                if grid is None:alpha=0
                else:
                    rgb=screen_average if screen_average is not None else grid[min(5,max(0,int(y)))*18+min(17,max(0,int(x)))]
                    hue,sat,val=colorsys.rgb_to_hsv(*(v/255 for v in rgb))
                    colour=colorsys.hsv_to_rgb(hue,min(1,sat*p.get('saturation',1)),min(1,val*p.get('screen_brightness',1)))
            elif kind in ('Audio Spectrum','Audio Pulse'):
                bands=audio.get(layer_index,[0.]*16) if audio else [0.]*16
                raw=bands[min(15,max(0,int(x/18*16)))] if kind=='Audio Spectrum' else math.sqrt(sum(v*v for v in bands)/16)
                level=max(0,min(1,(raw-p.get('noise_gate',.05))*p.get('sensitivity',1.4)))
                alpha=max(0,min(1,(level*6-(5.5-y))*2)) if kind=='Audio Spectrum' else level
                mix=max(0,min(1,(5-y)/5)) if kind=='Audio Spectrum' else level
            elif kind=='Gradient':mix=(u/18*scale)%1
            elif kind=='Rainbow Wave':colour=colorsys.hsv_to_rgb((u/18*scale-phase*.15)%1,1,1)
            elif kind=='Rainbow Wheel':colour=colorsys.hsv_to_rgb((math.atan2(y-2.5,(x-9)/2)/math.tau+phase*.12)%1,1,1)
            elif kind=='Breathing':alpha=(1-math.cos(phase*math.tau/3))/2
            elif kind in ('Ripple','Reactive'):
                alpha=0
                for origin,stamp in events:
                    age=(now-stamp)*speed
                    if not 0<=age<p['duration']:continue
                    distance=math.hypot(x-keys[origin]['x'],(y-keys[origin]['y'])*1.2)
                    value=max(0,1-age/p['duration']) if kind=='Reactive' and origin==index else 0
                    if kind=='Ripple':value=max(0,1-abs(distance-age*7)/scale)*min(1,(p['duration']-age)/.3)
                    alpha=max(alpha,value)
            elif kind=='Sparkle':
                cycle=phase*.5+(index*0.61803398875)%1;fraction=cycle%1
                alpha=max(0,1-abs(fraction-.5)/max(.01,p['density']/2))**2;mix=(index*.37)%1
            elif kind=='Comet':alpha=max(0,1-((phase*5-u)%24)/scale);mix=(u/18)%1
            elif kind=='Scanner':alpha=max(0,1-abs(u-(1+math.sin(phase))*9)/scale)
            elif kind=='Plasma':mix=(math.sin(x/scale+phase)+math.sin(y/scale-phase*.8)+math.sin(r-phase)+3)/6
            elif kind=='Aurora':mix=(1+math.sin(x/scale+phase*.5+math.sin(y+phase*.3)))/2;alpha=.2+.8*(1+math.sin(y*1.2+phase+math.sin(x*.4)))/2
            elif kind=='Fire':mix=max(0,min(1,(5-y)/6+.2*math.sin(x*2+phase*6)+.15*math.cos(y*3-phase*4)));alpha=.35+.65*mix
            elif kind=='Rain':alpha=max(0,1-((y-phase*4+(int(x)*1.618)%7)%8)/scale);mix=(int(x)*.23)%1
            elif kind=='Checker':mix=(int(x/scale+phase)+int(y/scale))%2
            elif kind=='Orbit':alpha=max(0,1-math.hypot((x-9)/2-math.cos(phase)*3,y-2.5-math.sin(phase)*2)/scale)
            if colour is None:colour=tuple(a[i]+(b[i]-a[i])*mix for i in range(3))
            alpha*=p['opacity']/100;dst=pixels[k['cell']]
            for i in range(3):
                src=colour[i];old=dst[i]
                target=min(1,old+src) if p['blend']=='Add' else 1-(1-old)*(1-src) if p['blend']=='Screen' else old*src if p['blend']=='Multiply' else src
                dst[i]=old+(target-old)*alpha
    # Lift dim pixels together, preserving channel ratios instead of washing
    # colours toward white. Black and full-scale peaks remain unchanged.
    exponent=1-.65*scene.get('boost',0)/100
    result=[]
    for rgb in pixels:
        peak=max(rgb)
        gain=peak**(exponent-1) if peak>0 else 1
        result.append(tuple(round(max(0,min(1,c*gain))*255*brightness) for c in rgb))
    return result

def library():
    return [
        ('Northern Lights',[layer('Gradient',colour='#06122c',secondary='#240c4c'),layer('Aurora',colour='#24ff9b',secondary='#7861ff',blend='Screen',speed=.6)]),
        ('Raspberry Mint',[layer('Solid',colour='#311020'),layer('Ripple',colour='#baff5b',scale=2),layer('Sparkle',colour='#ff247b',secondary='#ff8ab3',blend='Screen',density=.1)]),
        ('Chromatic Wheel',[layer('Rainbow Wheel',speed=.6)]),
        ('Ocean Glass',[layer('Gradient',colour='#020f2d',secondary='#086c86'),layer('Plasma',colour='#006384',secondary='#47ffe0',blend='Screen',opacity=65,speed=.4)]),
        ('Meteor Shower',[layer('Solid',colour='#100b23'),layer('Comet',colour='#c164ff',secondary='#42e7ff',angle=15,scale=5),layer('Sparkle',colour='#b8ccff',secondary='#ffffff',blend='Screen',density=.08)]),
        ('Ember',[layer('Fire',colour='#58030a',secondary='#ffc335',speed=.7)]),
        ('Neon Rain',[layer('Solid',colour='#080e16'),layer('Rain',colour='#39ff9e',secondary='#54c9ff',scale=2,speed=.7)]),
        ('Candy Waves',[layer('Gradient',colour='#7e22cd',secondary='#ff70ad'),layer('Comet',colour='#ffe59d',secondary='#ff68db',blend='Screen',angle=20,scale=7,speed=.5)]),
        ('Bioluminescence',[layer('Solid',colour='#021e20'),layer('Reactive',colour='#7fffcc',duration=3),layer('Sparkle',colour='#00a0bc',secondary='#b0ffc9',blend='Screen',density=.12,speed=.4)]),
        ('Sunset Orbit',[layer('Gradient',colour='#9b144f',secondary='#ff992c',angle=90),layer('Orbit',colour='#fff2ae',blend='Screen',scale=2,speed=.5)]),
        ('Prism Drift',[layer('Rainbow Wave',scale=1.4,angle=20,speed=.4)]),
        ('Midnight Pulse',[layer('Solid',colour='#070b20'),layer('Breathing',colour='#4255e8',blend='Screen',speed=.5),layer('Reactive',colour='#ffffff',blend='Screen')]),
        ('Laser Grid',[layer('Checker',colour='#051324',secondary='#164c67',scale=2,speed=.3),layer('Scanner',colour='#ff376b',scale=1.3,blend='Screen')]),
        ('Peach Clouds',[layer('Plasma',colour='#ff8b87',secondary='#a891ff',scale=4,speed=.25)]),
        ('Spectrum Neon',[layer('Solid',colour='#020712'),layer('Audio Spectrum',colour='#24f5aa',secondary='#fc447e',blend='Screen',sensitivity=2.2,smoothing=.3,noise_gate=.02)]),
        ('Velvet Pulse',[layer('Solid',colour='#0c0318'),layer('Audio Pulse',colour='#6624e8',secondary='#ff668c',blend='Screen',sensitivity=2.8,smoothing=.4,noise_gate=.02)]),
        ('Screen Mirror',[layer('Screen Colours',smoothing=.3)]),
        ('Screen + Sound',[layer('Screen Colours',smoothing=.4),layer('Audio Pulse',colour='#245bcd',secondary='#ff7a98',blend='Screen',opacity=40,sensitivity=2.8,smoothing=.4,noise_gate=.02)])]
