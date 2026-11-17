'use strict';
let selectingLayerKeys=false,draggedLayer=null,renderedLayerIndex=0;
let advancedReady=false,layerIndex=0,layerRendered='',previewTimer=null,previewBusy=false;
const layerBlends=['Normal','Add','Screen','Multiply'],layerMasks=['All','WASD','Arrows','Modifiers','Function Row','Custom'];
function newLayer(type='Rainbow Wave'){return {name:type,type,enabled:true,blend:'Normal',opacity:100,colour:'#ff397e',secondary:'#48ffd5',speed:1,scale:3,angle:0,density:.3,duration:2,mask:'All',cells:[],sensitivity:1.4,smoothing:.6,noise_gate:.05,auto_level:true,screen_monitor:'',screen_region:[0,0,100,100],screen_mode:'Zones',saturation:1,screen_brightness:1};}
function renderAdvancedVisibility(){
 const advanced=state.settings.mode===8;
 $('screen-status').hidden=!advanced||!state.settings.studio.layers.some(p=>p.type==='Screen Colours');
 $('audio-status').hidden=!advanced||!state.settings.studio.layers.some(p=>p.type.startsWith('Audio '));
 $('layer-key-picker').hidden=!advanced||!selectingLayerKeys;$('layer-picker-apply').textContent='Apply '+selected.size+' Keys';$('layer-picker-apply').disabled=!selected.size;
 $('keyboard').classList.toggle('choosing-keys',advanced&&selectingLayerKeys);
 const boost=state.settings.studio?.boost||0;$('colour-boost').value=boost;$('colour-boost-value').textContent=boost+'%';rangeFill($('colour-boost'));
 for(const key of ['brightness','speed']){const input=$('master-'+key),value=state.settings[key==='speed'?'speeds':'brightness'][8];input.value=value;$('master-'+key+'-value').textContent=value+(key==='brightness'?'%':'');rangeFill(input);}
 $('advanced-studio').hidden=!advanced;$('simple-studio').hidden=advanced;
 $('studio-simple').classList.toggle('active',!advanced);$('studio-advanced').classList.toggle('active',advanced);
 if(advancedReady&&advanced&&layerRendered!==JSON.stringify(state.settings.studio))renderLayers();
}
function updateLayer(value){const scene=structuredClone(state.settings.studio);Object.assign(scene.layers[layerIndex],value);return patch({studio:scene});}
function reorderLayer(from,to){
 const scene=structuredClone(state.settings.studio);if(from===to||from<0||to<0||from>=scene.layers.length||to>=scene.layers.length)return Promise.resolve();
 const active=scene.layers[layerIndex],moved=scene.layers.splice(from,1)[0];scene.layers.splice(to,0,moved);layerIndex=scene.layers.indexOf(active);selectingLayerKeys=false;
 return patch({studio:scene}).then(()=>{$('layer-order-status').textContent=moved.name+' moved to position '+(scene.layers.length-to)+' of '+scene.layers.length;});
}
function clearLayerDrag(){draggedLayer=null;document.querySelectorAll('.layer-row').forEach(row=>row.classList.remove('dragging','drop-before','drop-after'));}
function renderLayers(){
 const scene=state.settings.studio;if(!scene)return;
 layerRendered=JSON.stringify(scene);layerIndex=Math.min(layerIndex,scene.layers.length-1);renderedLayerIndex=layerIndex;
 $('layer-list').replaceChildren();
 for(let i=scene.layers.length-1;i>=0;i--){
  const layer=scene.layers[i],row=document.createElement('div');row.className='layer-row'+(i===layerIndex?' active':'');
  const enabled=button(layer.enabled?'On':'Off',()=>{const value=structuredClone(state.settings.studio);value.layers[i].enabled=!value.layers[i].enabled;return patch({studio:value});},'layer-toggle');enabled.setAttribute('role','switch');enabled.setAttribute('aria-checked',String(layer.enabled));enabled.setAttribute('aria-label',layer.name+' visibility');row.classList.toggle('layer-disabled',!layer.enabled);
  const select=button('',()=>{selectingLayerKeys=false;layerIndex=i;renderLayers();renderControls();},'layer-select');select.setAttribute('aria-pressed',String(i===layerIndex));
  const name=document.createElement('strong');name.textContent=layer.name;const detail=document.createElement('small');detail.textContent=layer.type+' / '+(layer.mask==='All'?'All Keys':layer.mask==='Custom'?layer.cells.length+' Keys':layer.mask);select.append(name,detail);
  const grip=document.createElement('button');grip.type='button';grip.className='layer-grip';grip.draggable=true;grip.setAttribute('aria-label','Reorder '+layer.name);grip.title='Drag to reorder. Arrow keys move this layer.';
  grip.onkeydown=e=>{if(e.key==='ArrowUp'||e.key==='ArrowDown'){e.preventDefault();const to=i+(e.key==='ArrowUp'?1:-1);reorderLayer(i,to).then(()=>document.querySelector('[data-layer="'+Math.max(0,Math.min(scene.layers.length-1,to))+'"] .layer-grip')?.focus());}};
  row.dataset.layer=i;
  grip.ondragstart=e=>{draggedLayer=i;e.dataTransfer.effectAllowed='move';e.dataTransfer.setData('text/plain',String(i));if(e.dataTransfer.setDragImage)e.dataTransfer.setDragImage(row,25,20);row.classList.add('dragging');};grip.ondragend=clearLayerDrag;
  row.ondragover=e=>{if(draggedLayer===null||draggedLayer===i)return;e.preventDefault();e.dataTransfer.dropEffect='move';document.querySelectorAll('.layer-row').forEach(r=>r.classList.remove('drop-before','drop-after'));const rect=row.getBoundingClientRect();row.classList.add(e.clientY<rect.top+rect.height/2?'drop-before':'drop-after');};
  row.ondrop=e=>{if(draggedLayer===null)return;e.preventDefault();const from=draggedLayer,before=row.classList.contains('drop-before');const visual=scene.layers.map((_,n)=>n).reverse().filter(n=>n!==from);if(from!==i){visual.splice(visual.indexOf(i)+(before?0:1),0,from);const to=scene.layers.length-1-visual.indexOf(from);clearLayerDrag();return reorderLayer(from,to);}clearLayerDrag();};
  row.append(grip,select,enabled);$('layer-list').append(row);
 }
 $('layer-count').textContent=scene.layers.length+'/8';
 const p=scene.layers[layerIndex];renderScreenControls(p);$('layer-name').value=p.name;$('delete-layer').disabled=scene.layers.length===1;$('duplicate-layer').disabled=scene.layers.length===8;$('add-layer').disabled=scene.layers.length===8;
 for(const key of ['type','blend','mask'])$('layer-'+key).value=p[key];
 $('layer-key-count').textContent=p.mask==='Custom'?p.cells.length+' Keys':'';
 $('layer-selected').textContent=p.mask==='Custom'?'Edit Keys':'Choose Keys';
 for(const key of ['colour','secondary']){$('layer-'+key).value=p[key];$('layer-'+key+'-hex').textContent=p[key].toUpperCase();$('layer-'+key).parentElement.style.setProperty('--swatch',p[key]);}
 for(const key of ['opacity','speed','scale','angle','density','duration','sensitivity','smoothing','noise_gate','saturation','screen_brightness']){$('layer-'+key).value=p[key];$('layer-'+key+'-value').textContent=p[key];rangeFill($('layer-'+key));}
 $('layer-auto-level').checked=p.auto_level!==false;$('audio-level-control').hidden=!p.type.startsWith('Audio ');
 const uses={opacity:true,speed:!['Solid','Gradient','Audio Spectrum','Audio Pulse','Screen Colours'].includes(p.type),scale:['Gradient','Rainbow Wave','Ripple','Comet','Scanner','Plasma','Aurora','Rain','Checker','Orbit'].includes(p.type),angle:['Gradient','Rainbow Wave','Comet','Scanner'].includes(p.type),density:p.type==='Sparkle',duration:['Ripple','Reactive'].includes(p.type),sensitivity:p.type.startsWith('Audio '),smoothing:p.type.startsWith('Audio ')||p.type==='Screen Colours',noise_gate:p.type.startsWith('Audio '),saturation:p.type==='Screen Colours',screen_brightness:p.type==='Screen Colours'};
 $('layer-colours-section').hidden=['Rainbow Wave','Rainbow Wheel','Screen Colours'].includes(p.type);$('layer-animation-section').hidden=!Object.entries(uses).some(([key,v])=>key!=='opacity'&&v);
 for(const [key,visible] of Object.entries(uses))$('layer-'+key).closest('label').hidden=!visible;
 $('layer-secondary').closest('label').hidden=['Solid','Breathing','Ripple','Reactive','Scanner','Orbit','Rainbow Wave','Rainbow Wheel'].includes(p.type);$('layer-colour').closest('label').hidden=['Rainbow Wave','Rainbow Wheel','Screen Colours'].includes(p.type);
}
function initAdvanced(){
 $('layer-auto-level').onchange=()=>updateLayer({auto_level:$('layer-auto-level').checked});
 $('solo-layer').onclick=toggleSolo;
 $('duplicate-layer').onclick=()=>{const scene=structuredClone(state.settings.studio);if(scene.layers.length>=8)return;const copy=structuredClone(scene.layers[layerIndex]);let n=1,name;do{name=copy.name.slice(0,37)+' Copy'+(n===1?'':' '+n);n++;}while(scene.layers.some(l=>l.name===name));copy.name=name;scene.layers.splice(layerIndex+1,0,copy);layerIndex++;return patch({studio:scene});};
 $('colour-boost').oninput=()=>{$('colour-boost-value').textContent=$('colour-boost').value+'%';rangeFill($('colour-boost'));};$('colour-boost').onchange=()=>patch({studio:{...structuredClone(state.settings.studio),boost:+$('colour-boost').value}});
 for(const key of ['brightness','speed']){const input=$('master-'+key);input.oninput=()=>{$('master-'+key+'-value').textContent=input.value+(key==='brightness'?'%':'');rangeFill(input);};input.onchange=()=>patch({[key]:+input.value});}
 for(const type of state.studio_types||[])$('layer-type').add(new Option(type,type));
 for(const name of layerBlends)$('layer-blend').add(new Option(name,name));
 for(const name of layerMasks)$('layer-mask').add(new Option(({All:'Whole Keyboard',Custom:'Custom Keys'})[name]||name,name));
 for(const [key,name,min,max,step] of [['opacity','Opacity',0,100,1],['speed','Speed',.1,4,.1],['scale','Scale',.5,12,.1],['angle','Angle',0,360,1],['density','Density',.02,1,.01],['duration','Duration',.2,10,.1],['sensitivity','Sensitivity',.25,4,.05],['smoothing','Smoothing',0,1,.05],['noise_gate','Noise Gate',0,.5,.01],['saturation','Saturation',0,2,.05],['screen_brightness','Screen Brightness',0,2,.05]]){
  const label=document.createElement('label');label.className='range-field';const heading=document.createElement('span'),output=document.createElement('output');output.id='layer-'+key+'-value';heading.append(document.createTextNode(name),output);const input=document.createElement('input');input.type='range';input.id='layer-'+key;input.min=min;input.max=max;input.step=step;input.oninput=()=>{output.textContent=input.value;rangeFill(input);};input.onchange=()=>updateLayer({[key]:+input.value});label.append(heading,input);$(key==='opacity'?'layer-opacity-slot':'layer-sliders').append(label);
 }
 $('studio-advanced').onclick=()=>patch({mode:8});$('studio-simple').onclick=()=>{selectingLayerKeys=false;return patch({mode:4});};
 for(const key of ['name','type','blend','mask','colour','secondary'])$('layer-'+key).onchange=()=>{const value=$('layer-'+key).value,p=state.settings.studio.layers[layerIndex];return updateLayer(key==='type'&&p.name===p.type?{type:value,name:value}:{[key]:value});};
 $('add-layer').onclick=()=>{const scene=structuredClone(state.settings.studio);if(scene.layers.length>=8)return;scene.layers.push(newLayer('Sparkle'));layerIndex=scene.layers.length-1;patch({studio:scene});};
 $('delete-layer').onclick=()=>{const scene=structuredClone(state.settings.studio);if(scene.layers.length<2)return;scene.layers.splice(layerIndex,1);layerIndex=Math.max(0,layerIndex-1);patch({studio:scene});};
 const chooseKeys=()=>{const p=state.settings.studio.layers[layerIndex];selected=new Set(state.device.keys.flatMap((k,i)=>p.mask==='Custom'&&p.cells.includes(k.cell)?[i]:[]));selectingLayerKeys=true;renderControls();$('keyboard').scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth',block:'center'});};
 $('layer-selected').onclick=chooseKeys;
 $('layer-picker-all').onclick=()=>{selected=new Set(state.device.keys.map((_,i)=>i));renderControls();};
 $('layer-picker-clear').onclick=()=>{selected.clear();renderControls();};
 $('layer-picker-cancel').onclick=()=>{selectingLayerKeys=false;selected.clear();renderLayers();renderControls();};
 $('layer-picker-apply').onclick=async()=>{if(!selected.size)return;await updateLayer({mask:'Custom',cells:[...selected].map(i=>state.device.keys[i].cell)});selectingLayerKeys=false;renderControls();};
 $('layer-mask').onchange=()=>{if($('layer-mask').value==='Custom')chooseKeys();else{selectingLayerKeys=false;updateLayer({mask:$('layer-mask').value});}};
 $('scene-code').onclick=()=>{$('scene-json').value=JSON.stringify(state.settings.studio,null,2);$('scene-error').textContent='';$('scene-dialog').showModal();};$('scene-cancel').onclick=()=>$('scene-dialog').close();
 $('scene-form').onsubmit=async e=>{e.preventDefault();try{const scene=JSON.parse($('scene-json').value);await patch({mode:8,studio:scene},false);$('scene-dialog').close();}catch(error){$('scene-error').textContent=error.message;}};
 $('scene-export').onclick=()=>{const url=URL.createObjectURL(new Blob([JSON.stringify(state.settings.studio,null,2)],{type:'application/json'})),a=document.createElement('a');a.href=url;a.download='smk-scene.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
 advancedReady=true;initScreenControls();renderLayers();
}
async function initStartup(){try{const value=await api('startup');$('auto-start').checked=value.enabled;$('auto-start').disabled=!value.available;}catch{$('auto-start').disabled=true;}
 $('auto-start').onchange=async()=>{try{const value=await api('startup',{enabled:$('auto-start').checked});$('auto-start').checked=value.enabled;$('startup-status').textContent=value.enabled?'Enabled':'Disabled';}catch(e){$('auto-start').checked=!$('auto-start').checked;toast(e.message);}};
}
let suppressLayerClickUntil=0;
function initLayerKeyDrag(){
 const svg=$('keyboard');let stroke=null;
 const keyAt=(x,y)=>{const g=document.elementFromPoint(x,y)?.closest('g.key');return g&&svg.contains(g)?+g.dataset.index:null;};
 const paint=index=>{if(index===null||stroke.visited.has(index))return;stroke.visited.add(index);if(stroke.add)selected.add(index);else selected.delete(index);};
 svg.addEventListener('pointerdown',e=>{if(!selectingLayerKeys||state.settings.mode!==8||e.button!==0||stroke)return;const g=e.target.closest('g.key');if(!g||!svg.contains(g))return;const index=+g.dataset.index;stroke={id:e.pointerId,add:!selected.has(index),before:new Set(selected),visited:new Set(),x:e.clientX,y:e.clientY};paint(index);suppressLayerClickUntil=Date.now()+500;svg.setPointerCapture(e.pointerId);e.preventDefault();renderControls();});
 svg.addEventListener('pointermove',e=>{if(!stroke||stroke.id!==e.pointerId)return;e.preventDefault();const dx=e.clientX-stroke.x,dy=e.clientY-stroke.y,steps=Math.max(1,Math.ceil(Math.hypot(dx,dy)/6));for(let i=1;i<=steps;i++)paint(keyAt(stroke.x+dx*i/steps,stroke.y+dy*i/steps));stroke.x=e.clientX;stroke.y=e.clientY;renderControls();});
 const finish=(e,cancel=false)=>{if(!stroke||e&&stroke.id!==e.pointerId)return;const id=stroke.id;if(cancel)selected=stroke.before;stroke=null;suppressLayerClickUntil=Date.now()+500;if(svg.hasPointerCapture(id))svg.releasePointerCapture(id);renderControls();};
 svg.addEventListener('pointerup',e=>finish(e));svg.addEventListener('pointercancel',e=>finish(e,true));svg.addEventListener('lostpointercapture',e=>finish(e,true));window.addEventListener('blur',()=>finish(null,true));
}
function drawPreset(canvas,pixels){
 const context=canvas.getContext('2d');context.fillStyle='#111';context.fillRect(0,0,canvas.width,canvas.height);
 for(const key of state.device.keys){const c=pixels[key.cell];context.fillStyle=`rgb(${c.join(',')})`;context.fillRect(10+key.x*27,9+key.y*27,20,20);}
}
function startPresetPreviews(){
 if(previewTimer)return;
 const tick=async()=>{
  previewTimer=null;if(currentTab!=='presets'||document.hidden||previewBusy)return;
  previewBusy=true;
  try{const canvases=[...document.querySelectorAll('canvas[data-preset]')].filter(c=>{const r=c.getBoundingClientRect();return r.bottom>0&&r.top<innerHeight;}),ids=canvases.map(c=>c.dataset.preset),time=(performance.now()/1000)%100000;
   for(let offset=0;offset<ids.length;offset+=12){const frames=await api('previews',{ids:ids.slice(offset,offset+12),time});for(const canvas of canvases)if(frames[canvas.dataset.preset])drawPreset(canvas,frames[canvas.dataset.preset]);}
  }catch{}finally{previewBusy=false;}
  if(currentTab==='presets'&&!matchMedia('(prefers-reduced-motion: reduce)').matches)previewTimer=setTimeout(tick,100);
 };
 previewTimer=setTimeout(tick,50);
}
