'use strict';
const $=id=>document.getElementById(id);
let currentTab='lighting',presetWorkflow=null,activePreset='',deviceBaseline=null,deviceNeedsRead=true,nextDeviceRead=0;
let token, state, selected=new Set(), queue=Promise.resolve(), lastPc=4, deviceDraft=null;
const hex=c=>'#'+c.map(v=>v.toString(16).padStart(2,'0')).join('');
const rgb=h=>[1,3,5].map(i=>parseInt(h.slice(i,i+2),16));
function toast(message){$('toast').textContent=message;$('toast').classList.add('show');setTimeout(()=>$('toast').classList.remove('show'),3500);}
async function api(path,data){const r=await fetch('/api/'+path,{method:data===undefined?'GET':'POST',headers:{'X-SMK-Token':token||'','Content-Type':'application/json'},body:data===undefined?undefined:JSON.stringify(data)});const v=await r.json();if(!r.ok)throw Error(v.error||'Request failed');return v;}
let undoStack=[],redoStack=[],soloLayer=null,soloRenewed=0;
function renderHistory(){$('solo-notice').hidden=soloLayer===null;$('solo-notice').textContent=soloLayer===null?'':'Solo: '+(state.settings.studio.layers[soloLayer]?.name||'Layer')+' (Exit)';$('studio-undo').disabled=!undoStack.length;$('studio-redo').disabled=!redoStack.length;$('solo-layer').setAttribute('aria-pressed',String(soloLayer===layerIndex));$('solo-layer').textContent=soloLayer===layerIndex?'Exit Solo':'Solo';}
function rememberLighting(before){if(JSON.stringify(before.settings)===JSON.stringify(state.settings))return;undoStack.push(before);if(undoStack.length>50)undoStack.shift();redoStack=[];}
function patch(value,report=true){queue=queue.catch(()=>{}).then(async()=>{const before={settings:structuredClone(state.settings),layer:renderedLayerIndex};state.settings=await api('settings',value);soloLayer=null;rememberLighting(before);renderControls();}).catch(e=>{if(report)toast(e.message);else throw e;});return queue;}
function historyStep(redo=false){queue=queue.catch(()=>{}).then(async()=>{const from=redo?redoStack:undoStack,to=redo?undoStack:redoStack;if(!from.length)return;const target=from[from.length-1],current={settings:structuredClone(state.settings),layer:layerIndex};const restored=await api('settings/restore',target.settings);from.pop();to.push(current);state.settings=restored;soloLayer=null;layerIndex=Math.min(target.layer,restored.studio.layers.length-1);selectingLayerKeys=false;layerRendered='';renderControls();}).catch(e=>toast(e.message));return queue;}
function toggleSolo(){queue=queue.catch(()=>{}).then(async()=>{const index=soloLayer===layerIndex?null:layerIndex;await api('solo',{index});soloLayer=index;soloRenewed=Date.now();renderHistory();}).catch(e=>toast(e.message));return queue;}
async function renewSolo(){if(soloLayer===null)return;if(currentTab!=='lighting'||state.settings.mode!==8){await api('solo',{index:null});soloLayer=null;renderHistory();return;}if(Date.now()-soloRenewed>2000){await api('solo',{index:soloLayer});soloRenewed=Date.now();}}

function button(label,fn,cls='button secondary'){const b=document.createElement('button');b.textContent=label;b.className=cls;b.onclick=()=>Promise.resolve().then(fn).catch(e=>toast(e.message));return b;}
function renderControls(){const s=state.settings,m=s.mode,per=m===0||m===2,react=m===6||m===7;
 renderHistory();renderPresetActions();renderAdvancedVisibility();$('effect-name').textContent=state.effects[m].replace(' (PC)','');$('studio-preset').value=activePreset;
 $('pc-effect-field').hidden=m===3;$('saved').hidden=m===3;$('effects').disabled=m===3;$('effects').value=m===3?lastPc:m;if(m!==3)lastPc=m;$('source-pc').classList.toggle('active',m!==3);$('source-onboard').classList.toggle('active',m===3);$('source-detail').textContent='';renderDeviceInfo();
 for(const [id,visible] of Object.entries({'onboard-note':m===3,'colour-controls':per||react,'background-field':react,'brightness-field':m!==3,'speed-field':m in s.speeds,'direction-field':m===4||m===5,'reactive-details':react,'width-field':m===7,'select-all':per}))$(id).hidden=!visible;
 $('selection-hint').textContent=selected.size?`${selected.size} Selected`:'';
 const fg=react?s.reactive_colours[m]:s.colours[[...selected][0]||0],bg=react?s.background_colours[m]:[0,0,0];
 for(const [id,c] of [['foreground',fg],['background',bg]]){$(id).value=hex(c);$(id).parentElement.style.setProperty('--swatch',hex(c));$(id+'-hex').textContent=hex(c).toUpperCase();}
 $('foreground-label').textContent=per?'Selected Keys':'Effect Colour';
 for(const [id,v,suffix] of [['brightness',s.brightness[m]||0,'%'],['speed',s.speeds[m]||5,''],['fade',s.effect_options[m===6?'reactive_fade':'ripple_fade'],' s'],['width',s.effect_options.ripple_width,' keys']]){if(document.activeElement!==$(id))$(id).value=v;$(id+'-value').textContent=v+suffix;rangeFill($(id));}
 const directions=m===4?[[0,'Left'],[1,'Right']]:[[2,'Up'],[3,'Down']];$('direction').replaceChildren(...directions.map(([v,n])=>new Option(n,v)));$('direction').value=s.directions[m];
 for(const g of $('keyboard').children)g.classList.toggle('selected',(per||m===8)&&selected.has(+g.dataset.index));
}
function keyboard(target="keyboard",onSelect=null){const ns='http://www.w3.org/2000/svg';state.device.keys.forEach((k,i)=>{const row=Math.floor(k.cell/18),col=k.cell%18;let x=col,w=1,y=row?row+.45:0;
 if(row===1&&col===14){x=13;w=2;}
 if(row===2&&col<15){x=col===0?0:col+.5;w=col===0?1.5:1;}
 if(row===3){x=col===0?0:col+.75;w=col===0?1.75:1;}
 if(row===4){if(col===0){x=0;w=1.25;}else if(col===14)x=1.25;else if(col===13){x=12.25;w=2.75;}else if(col<14)x=col+1.25;}
 if(row===5){const positions={0:[0,1.25],1:[1.25,1.25],2:[2.5,1.25],5:[3.75,6.25],8:[10,1.25],9:[11.25,1.25],10:[12.5,1.25],12:[13.75,1.25]};if(positions[col])[x,w]=positions[col];}
 if(col>=15)x=col+.5;
 const g=document.createElementNS(ns,'g');g.dataset.index=i;g.setAttribute('class','key');g.setAttribute('role','button');g.setAttribute('tabindex','0');g.setAttribute('aria-label',k.name);
 const shape=document.createElementNS(ns,row===3&&col===13?'path':'rect');
 if(row===3&&col===13)shape.setAttribute('d','M705 130 H777 V229 H718 V177 H705 Z');else{shape.setAttribute('x',x*52+2);shape.setAttribute('y',y*52+2);shape.setAttribute('width',w*52-5);shape.setAttribute('height',46);shape.setAttribute('rx',6);}
 const text=document.createElementNS(ns,'text');text.setAttribute('x',(x+w/2)*52);text.setAttribute('y',y*52+29);text.textContent=k.name.replace(/^Key: /,'').replace('Escape','Esc').replace('Backspace','Back').replace('Control','Ctrl').replace('Windows','Win').replace('Left ','').replace('Right ','').replace('Caps Lock','Caps').replace('Scroll Lock','Scroll').replace('Print Screen','PrtSc').replace(' Arrow','').replace('Page Up','PgUp').replace('Page Down','PgDn');
 const title=document.createElementNS(ns,'title');title.textContent=k.name;g.append(shape,text,title);
 const select=e=>{if(target==='keyboard'&&e.type!=='keydown'&&Date.now()<suppressLayerClickUntil)return;if(onSelect){onSelect(k.cell);return;}if(![0,2,8].includes(state.settings.mode))return;if(!e.shiftKey&&!(state.settings.mode===8&&selectingLayerKeys))selected.clear();if(selected.has(i))selected.delete(i);else selected.add(i);renderControls();};g.onclick=select;g.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();select(e);}};$(target).append(g);
 });}
async function refresh(){state=await api('state');$('app-version').textContent='SMK WebUI '+(state.version||'');adoptWorkspace();renderControls();renderPresets();renderWorkflow();$('notice').hidden=!state.notice;$('notice').textContent=state.notice||'';}
function nameDialog(title,initial,action){$('confirm-dialog').textContent='Save';$('dialog-title').textContent=title;$('preset-name').value=initial;$('name-dialog').showModal();$('preset-name').focus();$('name-form').onsubmit=async e=>{e.preventDefault();try{await action($('preset-name').value.trim());$('name-dialog').close();await refresh();}catch(err){toast(err.message);}};}
function showTab(tab){
 currentTab=tab;for(const name of ['lighting','presets','settings','keyboard-settings'])$(name+'-view').hidden=name!==tab;
 $('page-title').textContent={lighting:'Lighting',presets:'Presets',settings:'Settings','keyboard-settings':'Keyboard'}[tab];
 document.querySelectorAll('.nav').forEach(n=>n.classList.toggle('active',n.dataset.tab===tab));
 if(tab==='presets')startPresetPreviews();
 if(tab==='keyboard-settings'&&(!deviceDraft||deviceNeedsRead)&&!deviceDirty)loadDevice().catch(e=>toast(e.message));
}
function adoptWorkspace(){const w=state.workspace||{};activePreset=w.preset_id||'';presetWorkflow=w.workflow||null;}
function stable(value){if(Array.isArray(value))return value.map(stable);if(value&&typeof value==='object')return Object.fromEntries(Object.keys(value).sort().map(k=>[k,stable(value[k])]));return value;}
function lightingValue(s){
 if(!s)return null;const m=s.mode,v={mode:m,brightness:s.brightness?.[m],speed:s.speeds?.[m]};
 if(m===8)v.studio={...s.studio,boost:s.studio?.boost||0,layers:(s.studio?.layers||[]).map(p=>({...newLayer(p.type),...p}))};
 if(m===0||m===2)v.colours=s.colours;
 if(m===4||m===5)v.direction=s.directions?.[m];
 if(m===6||m===7){v.foreground=s.reactive_colours?.[m];v.background=s.background_colours?.[m];v.fade=s.effect_options?.[m===6?'reactive_fade':'ripple_fade'];if(m===7)v.width=s.effect_options?.ripple_width;}
 return JSON.stringify(stable(v));
}
function selectedPreset(){return allPresets().find(p=>p.id===activePreset);}
function presetBaseline(){return selectedPreset()?.settings||state.workspace?.baseline;}
function lightingModified(){const base=presetBaseline();return !!base&&lightingValue(base)!==lightingValue(state.settings);}
function renderPresetActions(){
 const p=selectedPreset(),changed=lightingModified();$('preset-edit-status').textContent=presetWorkflow?'Draft: '+presetWorkflow.name+(changed?' / Modified':''):p?p.name+(changed?' / Modified':' / Saved'):'Custom Lighting';
 $('preset-edit-status').classList.toggle('modified',changed);
 $('update-preset').hidden=!p||p.builtin||!!presetWorkflow;$('update-preset').disabled=!changed||state.settings.mode===3;
 $('save-copy').hidden=!!presetWorkflow;$('save-copy').disabled=state.settings.mode===3;
 $('revert-preset').hidden=!changed;$('saved').textContent=changed?'Modified':'Live';
}
async function workspace(value){state.workspace=await api('workspace',value);adoptWorkspace();renderWorkflow();renderPresetActions();}
async function loadPreset(p,edit=false){
 await queue.catch(()=>{});if((presetWorkflow||lightingModified())&&!confirm('Discard unfinished lighting edits and load this preset?')){$('studio-preset').value=activePreset;return;}
 await api('presets/load',{id:p.id});undoStack=[];redoStack=[];soloLayer=null;selectingLayerKeys=false;
 if(edit)await api('workspace',{preset_id:p.id,workflow:{id:p.builtin?null:p.id,name:p.name+(p.builtin?' Copy':'')},baseline:p.settings});
 await refresh();if(edit)showTab('lighting');
}
function renderWorkflow(){$('preset-workflow').hidden=!presetWorkflow;$('preset-workflow-name').textContent=presetWorkflow?(presetWorkflow.id?'Editing: ':'New Preset: ')+presetWorkflow.name:'';$('new-preset').disabled=!!presetWorkflow;}
function createPreset(){nameDialog('Create Lighting Preset','',async name=>{await queue.catch(()=>{});if(allPresets().some(p=>p.name.toLowerCase()===name.toLowerCase()))throw Error('A preset already uses that name');if(state.settings.mode===3)await patch({mode:lastPc},false);await workspace({preset_id:'',workflow:{id:null,name},baseline:state.settings});showTab('lighting');});$('confirm-dialog').textContent='Continue';}
async function revertPreset(){await queue.catch(()=>{});const baseline=presetBaseline();if(!baseline||!confirm('Revert to the saved lighting settings?'))return;const before={settings:structuredClone(state.settings),layer:layerIndex};state.settings=await api('settings/restore',baseline);rememberLighting(before);soloLayer=null;layerRendered='';renderControls();}
function allPresets(){return [...state.presets,...(state.library||[])];}
function renderPresets(){
 $('preset-count').textContent=allPresets().length;$('preset-grid').replaceChildren();$('studio-preset').replaceChildren(new Option('Custom Lighting',''));
 if(!allPresets().length)$('preset-grid').textContent='No lighting presets yet. Choose Create new to start.';
 for(const p of allPresets()){
  $('studio-preset').add(new Option(p.name,p.id));const card=document.createElement('article');card.className='preset-tile';
  const load=button('',()=>loadPreset(p),'preset-load');load.setAttribute('aria-label','Load '+p.name);
  const banner=document.createElement('canvas');banner.className='preset-banner';banner.width=520;banner.height=176;banner.dataset.preset=p.id;banner.setAttribute('aria-hidden','true');
  const title=document.createElement('strong');title.textContent=p.name;const detail=document.createElement('small');detail.textContent=(state.effects[p.settings?.mode]||'Lighting preset').replace(' (PC)','');load.append(banner,title,detail);
  const menu=document.createElement('details');menu.className='preset-menu';const summary=document.createElement('summary');summary.textContent='•••';summary.setAttribute('aria-label','Options for '+p.name);menu.append(summary);const actions=document.createElement('div');actions.className='preset-menu-items';
  const action=(name,fn)=>actions.append(button(name,async()=>{menu.open=false;await fn();},'menu-action'));
  action('Edit',()=>loadPreset(p,true));if(!p.builtin)action('Rename',()=>nameDialog('Rename Preset',p.name,name=>api('presets/rename',{id:p.id,name})));action('Duplicate',()=>nameDialog('Duplicate Preset',p.name+' copy',name=>api('presets/duplicate',{id:p.id,name})));
  action('Export',async()=>{const data=await api('presets/'+p.id),url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'})),a=document.createElement('a');a.href=url;a.download=p.name.replace(/[^a-z0-9_-]/gi,'-')+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
  if(!p.builtin)action('Delete',async()=>{if(confirm('Delete '+p.name+'?')){await api('presets/delete',{id:p.id});if(activePreset===p.id)activePreset='';await refresh();}});menu.append(actions);card.append(load,menu);$('preset-grid').append(card);
 }
 $('studio-preset').value=activePreset;startPresetPreviews();
}
async function live(){try{await renewSolo();const v=await api('live');$('screen-status').textContent='Screen / '+(v.screen||'Idle');$('audio-status').textContent='System Audio / '+(v.audio||'Idle');if(v.mode!==undefined&&v.mode!==state.settings.mode)await refresh();const wasConnected=state.connected;state.connected=v.connected;if(!v.connected||!wasConnected)deviceNeedsRead=true;if(v.capabilities!==undefined)state.capabilities=v.capabilities;if(v.onboard){const old=state.onboard||{};if(old.editing||old.saving||v.onboard.editing||v.onboard.saving)deviceNeedsRead=true;state.onboard=v.onboard;renderDeviceInfo();}if(currentTab==='keyboard-settings'&&v.connected&&deviceNeedsRead&&!deviceDirty&&!deviceBusy&&Date.now()>nextDeviceRead&&!v.onboard?.editing&&!v.onboard?.saving){nextDeviceRead=Date.now()+5000;loadDevice().catch(()=>{});}$('connection').classList.toggle('online',v.connected);$('connection').textContent=v.connected?'Connected':state.demo?'Preview mode':'Disconnected';$('sidebar-status').textContent=v.status;$('fps').textContent=v.connected?v.fps+' FPS':'— FPS';$('preview-label').textContent=state.settings.mode===3?'Onboard lighting':v.connected?'Output preview':'Preview only';for(const g of $('keyboard').children){const cell=state.device.keys[+g.dataset.index].cell,c=v.onboard?.windows_locked&&cell===91?[255,0,0]:v.pixels[cell]||[0,0,0];g.firstChild.style.fill=`rgb(${c.map(n=>Math.round(23+n*.45)).join(',')})`;g.firstChild.style.stroke=hex(c);}}catch(e){$('connection').textContent='App disconnected';}setTimeout(live,100);}
async function refreshLogs(){const d=await api('logs');$('log-status').textContent=`PID ${d.pid} · ${d.status} · ${d.fps} FPS`;$('log-path').textContent=d.log_file;$('log-output').textContent=d.entries.join('\n')||'No entries.';}
function rangeFill(input){input.style.setProperty('--progress',((+input.value-input.min)/(input.max-input.min)*100)+'%');}
async function init(){token=(await api('session')).token;state=await api('state');adoptWorkspace();keyboard();state.effects.forEach((name,i)=>{if(i!==3&&i!==8)$('effects').add(new Option(name.replace(' (PC)',''),i));});$('effects').onchange=()=>patch({mode:+$('effects').value});$('source-pc').onclick=()=>patch({mode:lastPc});$('source-onboard').onclick=()=>patch({mode:3});initDeviceControls();renderControls();renderPresets();
 document.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>showTab(b.dataset.tab));
 $('solo-notice').onclick=()=>{queue=queue.catch(()=>{}).then(async()=>{await api('solo',{index:null});soloLayer=null;renderHistory();}).catch(e=>toast(e.message));};$('studio-undo').onclick=()=>historyStep();$('studio-redo').onclick=()=>historyStep(true);
 document.addEventListener('keydown',e=>{if(currentTab!=='lighting'||document.querySelector('dialog[open]')||e.target.closest('input,textarea,select,[contenteditable=true]')||!(e.ctrlKey||e.metaKey)||e.altKey)return;const key=e.key.toLowerCase();if(key==='z'||key==='y'){e.preventDefault();historyStep(key==='y'||e.shiftKey);}});
 initStudio();renderWorkflow();initLayerKeyDrag();initTheme();initAdvanced();initStartup();initSelects();$('logs-view').ontoggle=()=>{if($('logs-view').open)refreshLogs().catch(e=>toast(e.message));};
 $('refresh-logs').onclick=()=>refreshLogs().catch(e=>toast(e.message));
 $('download-logs').onclick=async()=>{try{const d=await api('logs');const text=`PID: ${d.pid}\nStatus: ${d.status}\nFPS: ${d.fps}\n\n`+d.entries.join('\n');const url=URL.createObjectURL(new Blob([text],{type:'text/plain'}));const a=document.createElement('a');a.href=url;a.download='smk-webui.log';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}catch(e){toast(e.message);}};
 $('select-all').onclick=()=>{selected=new Set(state.device.keys.map((_,i)=>i));renderControls();};
 for(const id of ['brightness','speed','fade','width']){$(id).oninput=()=>{$(id+'-value').textContent=$(id).value+({brightness:'%',fade:' s',width:' keys'}[id]||'');rangeFill($(id));};$(id).onchange=()=>{const v=+$(id).value;patch(id==='fade'||id==='width'?{effect_options:{[id==='width'?'ripple_width':state.settings.mode===6?'reactive_fade':'ripple_fade']:v}}:{[id]:v});};}
 for(const id of ['foreground','background'])$(id).oninput=()=>{$(id).parentElement.style.setProperty('--swatch',$(id).value);$(id+'-hex').textContent=$(id).value.toUpperCase();};
 $('direction').onchange=()=>patch({direction:+$('direction').value});$('background').onchange=()=>patch({background:rgb($('background').value)});$('foreground').onchange=()=>{const c=rgb($('foreground').value);patch([0,2].includes(state.settings.mode)?{key_colour:{indices:selected.size?[...selected]:state.device.keys.map((_,i)=>i),rgb:c}}:{foreground:c});};
 $('export-library').onclick=async()=>{try{const data=await api('library'),url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'})),a=document.createElement('a');a.href=url;a.download='smk-lighting-library.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}catch(e){toast(e.message);}};
 $('cancel-dialog').onclick=()=>$('name-dialog').close();$('import-preset').onclick=()=>$('preset-file').click();$('preset-file').onchange=async e=>{try{const file=e.target.files[0];if(!file)return;if(file.size>4194304)throw Error('Preset is too large');const p=JSON.parse(await file.text());if(p.format==='smk-webui-library'&&p.version===1){const result=await api('presets/import-library',p);state=await api('state');renderPresets();toast(`Imported ${result.imported} Presets`);return;}if(p.format!=='smk-webui-preset'||p.version!==1)throw Error('Unsupported preset format');nameDialog('Import Preset',p.name,name=>api('presets/import',{name,settings:p.settings}));}catch(err){toast(err.message);}e.target.value='';};
 $('quit').onclick=async()=>{if(confirm('Stop PC lighting and return to onboard lighting?')){await api('quit',{});toast('Lighting app closed');}};live();}
const deviceEffects=['Radial Wave','Rainbow Wave','Vertical Wave','White','Off','Breathing','Colour Cycle','Reactive Typing','Ripple','Scanner'];
const factoryPalette=['#000000','#ffffff','#ff0000','#ff4000','#ffa000','#ffff00','#80ff00','#00ff00','#00ff80','#00ffff','#0080ff','#0000ff','#8000ff','#ff00ff','#ff0080','#ff80c0'];
const outputKeys=[['None',0],...Array.from({length:26},(_,i)=>[String.fromCharCode(65+i),4+i]),...Array.from({length:9},(_,i)=>[String(i+1),30+i]),['0',39],['Enter',40],['Esc',41],['Backspace',42],['Tab',43],['Space',44],['Minus',45],['Equal',46],['LeftBracket',47],['RightBracket',48],['Hash',50],['Semicolon',51],['Quote',52],['Grave',53],['Comma',54],['Dot',55],['Slash',56],['CapsLock',57],...Array.from({length:12},(_,i)=>['F'+(i+1),58+i]),['PrintScreen',70],['ScrollLock',71],['Pause',72],['Insert',73],['Home',74],['PageUp',75],['Delete',76],['End',77],['PageDown',78],['Right',79],['Left',80],['Down',81],['Up',82],['Backslash',100],['Menu',101]];
const modifiers=[['Ctrl',1],['Shift',2],['Alt',4],['Win',8],['RCtrl',16],['RShift',32],['AltGr',64],['RWin',128]];
let deviceBusy=false, deviceDirty=false, deviceCell=0, deviceView="bindings", paintColour=1, paintTool=true, painting=false, paintUndo=[];
function renderDeviceInfo(){
 const c=state.capabilities,available=!!c&&state.connected,o=state.onboard||{};
 $('firmware-summary').textContent=c?'Firmware '+c.version+' · '+c.layout:'Fast v1 · legacy controls';
 $('keyboard-capabilities').textContent=c?`Firmware ${c.version} · ${c.layout} · ${c.colour_modes} colour modes · ${c.macros} macros (${c.macro_steps} steps each)`:'Keyboard configuration requires firmware 2.0. Existing PC effects remain available.';
 $('read-keyboard').disabled=!available||deviceBusy;$('write-keyboard').disabled=!available||!deviceDraft||!deviceDirty||deviceBusy;$('keyboard-draft-controls').disabled=deviceBusy||!available;$('reset-keyboard').disabled=deviceBusy||!available;$('discard-keyboard').hidden=!deviceDirty;$('write-keyboard').hidden=!deviceDirty;$('windows-lock').hidden=!o.windows_locked;
 $('onboard-unsupported').hidden=available;$('onboard-unsupported').textContent='Use Fn shortcuts on the keyboard. Firmware 2.0 adds controls here.';$('onboard-controls').hidden=!available;
 $('onboard-edit-status').textContent=o.editing?'CM editing active — tap keys to cycle colours; press the same Fn+number to save.':o.saving?'Saving to keyboard…':o.save_failed?'Save failed. Check Logs.':'';
 if(document.activeElement!==$('onboard-effect'))$('onboard-effect').value=o.effect===undefined?'':o.effect;
 for(const [i,b] of [...$('cm-buttons').children].entries())b.classList.toggle('active',o.effect===10+i);
}
function configValue(d,fromInputs=false){return JSON.stringify({version:d.version,presets:d.presets,palette:d.palette,bindings:d.bindings,macros:fromInputs?Array.from({length:4},(_,i)=>parseMacro($('macro-'+i).value)):d.macros,reset_lighting:!!d.reset_lighting,reset_all:!!d.reset_all});}
function dirtyDevice(){try{deviceDirty=configValue(deviceDraft,true)!==deviceBaseline;}catch{deviceDirty=true;}$('keyboard-save-status').textContent=deviceDirty?'Unsaved keyboard changes':'Matches stored configuration';renderDeviceKeyboard();renderDeviceInfo();}
function renderBinding(){
 if(!deviceDraft)return;
 const cell=+$('binding-key').value,b=deviceDraft.bindings[cell];
 $('binding-type').value=b.key===255?'macro':b.key===254?'disabled':b.key||b.mods?'shortcut':'default';
 $('binding-output').value=b.key<160?b.key:0;$('binding-macro').value=b.key===255?b.mods-1:0;
 for(const checkbox of $('binding-modifiers').querySelectorAll('input'))checkbox.checked=!!(b.mods&+checkbox.value);
 bindingFields();
}
function bindingFields(){const type=$('binding-type').value;$('binding-shortcut').hidden=type!=='shortcut';$('binding-macro-field').hidden=type!=='macro';$('binding-type').disabled=deviceCell===99;$('binding-reserved').hidden=deviceCell!==99;}
function currentPalette(){return deviceDraft?.palette||factoryPalette;}
function renderPalette(){if(!deviceDraft)return;const value=paintColour;for(const [i,b] of [...$('cm-palette').children].entries()){b.style.background=currentPalette()[i];b.title=i===0?'Off':currentPalette()[i];b.classList.toggle('active',i===value);b.setAttribute('aria-pressed',String(i===value));}$('paint-colour-label').textContent='Brush: '+(paintColour===0?'Off':currentPalette()[paintColour].toUpperCase());$('cm-custom-colour').value=currentPalette()[paintColour];$('cm-custom-hex').textContent=currentPalette()[paintColour].toUpperCase();$('cm-custom-colour').parentElement.style.setProperty('--swatch',currentPalette()[paintColour]);$('cm-custom-colour').disabled=!deviceDraft.palette;$('cm-colour-note').textContent=deviceDraft.palette?'15 editable colours plus Off, shared across CM1–CM5.':'Custom CM colours require firmware 2.2.';}
function applyBinding(){if(!deviceDraft||deviceCell===99)return;const type=$('binding-type').value;let key=0,mods=0;if(type==='shortcut'){key=+$('binding-output').value;for(const c of $('binding-modifiers').querySelectorAll('input:checked'))mods|=+c.value;}else if(type==='macro'){key=255;mods=+$('binding-macro').value+1;}else if(type==='disabled')key=254;deviceDraft.bindings[+$('binding-key').value]={key,mods};dirtyDevice();}
function bindingDescription(cell){
 const b=deviceDraft.bindings[cell];
 if(deviceView==='fn')return deviceDraft.fn_bindings?.[cell]||'Read from firmware 2.1 to view';
 if(cell===99)return 'Fn · reserved';
 if(b.key===255)return 'Macro '+b.mods;
 if(b.key===254)return 'Disabled';
 if(!b.key&&!b.mods)return 'Default';
 return [...modifiers.filter(m=>b.mods&m[1]).map(m=>m[0]),...(b.key?[outputKeys.find(k=>k[1]===b.key)?.[0]||'HID '+b.key]:[])].join('+');
}
function selectDeviceKey(cell){
 deviceCell=cell;$('binding-key').value=cell;$('cm-edit-key').value=cell;
 renderBinding();renderPalette();renderDeviceKeyboard();
}
function renderDeviceKeyboard(){
 if(!deviceDraft)return;
 const colours=deviceView==='colours',fn=deviceView==='fn',profile=+$('cm-edit-profile').value;
 for(const b of document.querySelectorAll('[data-device-view]')){const active=b.dataset.deviceView===deviceView;b.classList.toggle('active',active);b.setAttribute('aria-pressed',String(active));}
 $('assignment-card').hidden=colours||fn;$('colour-mode-card').hidden=!colours;$('macro-card').hidden=colours||fn;$('fn-card').hidden=!fn;
 const key=state.device.keys.find(k=>k.cell===deviceCell);
 $('device-key-selection').textContent=key.name.replace('Key: ','');
 const colour=currentPalette()[deviceDraft.presets[profile][deviceCell]];
 $('device-key-detail').textContent=colours?'CM'+(profile+1)+' · '+(colour==='#000000'?'Off':colour.toUpperCase()):bindingDescription(deviceCell);
 $('device-preview-label').textContent=colours?'CM'+(profile+1)+' draft':fn?'Built-in Fn layer':'Assignment draft';
 $('fn-key-name').textContent='Fn + '+key.name.replace('Key: ','');$('fn-key-action').textContent=bindingDescription(deviceCell);
 $('device-keyboard').classList.toggle('painting',colours&&paintTool);$('paint-undo').disabled=!paintUndo.length||deviceBusy;
 for(const g of $('device-keyboard').children){
  const cell=state.device.keys[+g.dataset.index].cell,b=deviceDraft.bindings[cell],colour=currentPalette()[deviceDraft.presets[profile][cell]],changed=fn?deviceDraft.fn_bindings?.[cell]&&deviceDraft.fn_bindings[cell]!=='Base key':b.key||b.mods;
  g.classList.toggle('selected',cell===deviceCell);g.setAttribute('aria-pressed',String(cell===deviceCell));
  g.firstChild.style.fill=colours?colour:changed?'#414b56':'#262626';g.firstChild.style.stroke=colours?'#777':changed?'#9caebf':'#555';
  const c=rgb(colour);g.querySelector('text').style.fill=colours&&(c[0]*.2126+c[1]*.7152+c[2]*.0722)>145?'#111':'#eee';
  const detail=colours?(colour==='#000000'?'Off':colour):bindingDescription(cell),label=state.device.keys[+g.dataset.index].name+' · '+detail;
  g.setAttribute('aria-label',label);g.querySelector('title').textContent=label;
 }
}
function rememberPaint(){
 if(!deviceDraft)return;
 const profile=+$('cm-edit-profile').value;paintUndo.push({profile,colours:[...deviceDraft.presets[profile]]});if(paintUndo.length>30)paintUndo.shift();
}
function paintKey(cell){
 if(!deviceDraft||deviceBusy||!state.connected||deviceView!=='colours'||!paintTool)return;
 selectDeviceKey(cell);const keys=deviceDraft.presets[+$('cm-edit-profile').value];
 if(keys[cell]!==paintColour){keys[cell]=paintColour;dirtyDevice();}
}
function initPainting(){
 const svg=$('device-keyboard');
 svg.onpointerdown=e=>{if(e.button!==0||deviceView!=='colours'||!paintTool||deviceBusy||!state.connected)return;const key=e.target.closest('g.key');if(!key)return;e.preventDefault();rememberPaint();painting=true;paintKey(state.device.keys[+key.dataset.index].cell);};
 svg.onpointermove=e=>{if(!painting)return;e.preventDefault();const key=document.elementFromPoint(e.clientX,e.clientY)?.closest('#device-keyboard g.key');if(key)paintKey(state.device.keys[+key.dataset.index].cell);};
 const stop=()=>{painting=false;};window.addEventListener('pointerup',stop);window.addEventListener('pointercancel',stop);window.addEventListener('blur',stop);
 for(const [id,value] of [['paint-tool',true],['select-tool',false]])$(id).onclick=()=>{paintTool=value;$('paint-tool').classList.toggle('active',value);$('select-tool').classList.toggle('active',!value);renderDeviceKeyboard();};
 $('paint-fill').onclick=()=>{rememberPaint();deviceDraft.presets[+$('cm-edit-profile').value].fill(paintColour);dirtyDevice();};
 $('paint-undo').onclick=()=>{const previous=paintUndo.pop();if(!previous)return;deviceDraft.presets[previous.profile]=previous.colours;$('cm-edit-profile').value=previous.profile;dirtyDevice();};
 svg.addEventListener('keydown',e=>{if((e.key==='Enter'||e.key===' ')&&deviceView==='colours'&&paintTool){const key=e.target.closest('g.key');if(key){rememberPaint();paintKey(state.device.keys[+key.dataset.index].cell);}}});
}
function resetDraft(kind){
 if(!deviceDraft)return;
 if(kind==='cm'){
  const profile=+$('cm-edit-profile').value,defaults=deviceDraft.defaults.presets[profile];
  if(deviceDraft.palette){
   const colours=[...deviceDraft.palette],used=new Set(deviceDraft.presets.flatMap((p,i)=>i===profile?[]:p)),mapping={0:0};
   for(const slot of new Set(defaults)){if(slot===0)continue;const colour=factoryPalette[slot];let at=colours.indexOf(colour);if(at<0){at=colours.findIndex((c,i)=>i>0&&!used.has(i));if(at<0)throw Error('No free colour slots for this default. Clear another CM or reset all colour modes.');colours[at]=colour;}used.add(at);mapping[slot]=at;}
   deviceDraft.palette=colours;deviceDraft.presets[profile]=defaults.map(i=>mapping[i]);
  }else deviceDraft.presets[profile]=[...defaults];
 }
 if(kind==='colours'||kind==='all'){deviceDraft.presets=deviceDraft.defaults.presets.map(p=>[...p]);if(deviceDraft.palette)deviceDraft.palette=[...factoryPalette];}
 if(kind==='key')deviceDraft.bindings[deviceCell]={key:0,mods:0};
 if(kind==='bindings'||kind==='all')deviceDraft.bindings=deviceDraft.bindings.map(()=>({key:0,mods:0}));
 if(kind==='macros'||kind==='all')for(let i=0;i<4;i++)$('macro-'+i).value='';
 else if(/^macro[0-3]$/.test(kind))$('macro-'+kind.slice(-1)).value='';
 if(kind==='lighting'||kind==='all')deviceDraft.reset_lighting=true;if(kind==='all')deviceDraft.reset_all=true;
 paintUndo=[];renderBinding();renderPalette();renderDeviceKeyboard();
}
function initResets(){
 const scope=$('reset-scope'),input=$('reset-confirm');
 const describe=()=>{const all=scope.value==='all';$('reset-confirm-label').hidden=!all;input.required=all;input.pattern=all?'RESET':'.*';input.value='';$('reset-description').textContent=all?'Restore factory CM colours, clear remaps and macros, and reset onboard lighting.':'Reset '+scope.selectedOptions[0].text+'? CM factory layouts are Glacier, Arena, Midnight, Sunset and Aurora. Clear removes colours; Restore default restores these layouts.';};
 $('reset-keyboard').onclick=async()=>{try{if(!await loadDevice(true))return;describe();$('reset-dialog').showModal();}catch(e){toast(e.message);}};
 scope.onchange=describe;$('reset-cancel').onclick=()=>$('reset-dialog').close();
 $('reset-form').onsubmit=async e=>{e.preventDefault();if(!deviceDraft||deviceBusy)return;const kind=scope.value;if(kind==='all'&&input.value!=='RESET')return;
  if((kind==='lighting'||kind==='all')&&state.capabilities?.version==='2.0'){toast('Firmware 2.1 is required to reset lighting here');return;}
  try{resetDraft(kind);dirtyDevice();$('reset-dialog').close();await saveDevice();toast('Keyboard reset saved and verified');}catch(e){toast(e.message);}
 };
}
function chooseCustomColour(colour){
 if(!deviceDraft?.palette)return;
 const colours=deviceDraft.palette;let slot=colours.indexOf(colour);
 if(slot<0){const used=new Set(deviceDraft.presets.flat());slot=colours.findIndex((c,i)=>i>0&&!used.has(i));
  if(slot<0){slot=paintColour||1;if(!confirm('All colour slots are in use. Replace '+colours[slot]+' everywhere it appears across CM1–CM5?')){renderPalette();return;}}
  colours[slot]=colour;dirtyDevice();
 }
 paintColour=slot;renderPalette();renderDeviceKeyboard();
}
function adoptDevice(value){
 deviceDraft=value;deviceBaseline=configValue(value);deviceDirty=false;deviceNeedsRead=false;paintUndo=[];
 for(let i=0;i<4;i++)$('macro-'+i).value=formatMacro(value.macros[i]);
 $('keyboard-editors').hidden=false;selectDeviceKey(deviceCell);$('keyboard-save-status').textContent='Matches stored configuration';renderDeviceInfo();
}
async function loadDevice(force=false){
 if(deviceBusy||!state.connected||!state.capabilities)return false;
 if(deviceDirty&&(!force||!confirm('Discard unsaved keyboard changes and reload stored settings?')))return false;
 $('keyboard-loading').hidden=false;$('keyboard-loading').textContent='Loading keyboard configuration…';
 try{adoptDevice(await deviceAction('read'));return true;}
 catch(e){$('keyboard-save-status').textContent='Could not load keyboard: '+e.message;throw e;}
 finally{$('keyboard-loading').hidden=true;}
}
async function saveDevice(){
 if(!deviceDraft||deviceBusy)return;
 try{deviceDraft.macros=Array.from({length:4},(_,i)=>parseMacro($('macro-'+i).value));$('keyboard-save-status').textContent='Saving to keyboard…';adoptDevice(await deviceAction('write',deviceDraft));$('keyboard-save-status').textContent='Saved to keyboard · verified';}
 catch(e){$('keyboard-save-status').textContent='Not saved: '+e.message;throw e;}
}
function initStudio(){
 $('new-preset').onclick=createPreset;$('create-preset').onclick=createPreset;
 $('studio-preset').onchange=()=>{const p=allPresets().find(p=>p.id===$('studio-preset').value);if(p)loadPreset(p).catch(e=>toast(e.message));else workspace({preset_id:'',workflow:null,baseline:state.settings}).catch(e=>toast(e.message));};
 $('cancel-preset-edit').onclick=()=>workspace({...state.workspace,workflow:null}).catch(e=>toast(e.message));
 $('update-preset').onclick=async()=>{try{await queue;const p=selectedPreset();if(!p||p.builtin)return;await api('presets/replace',{id:p.id});await refresh();toast('Preset Updated');}catch(e){toast(e.message);}};
 $('save-copy').onclick=()=>nameDialog('Save Copy',(selectedPreset()?.name||'Lighting')+' Copy',async name=>{await queue;await api('presets/save',{name});});
 $('revert-preset').onclick=()=>revertPreset().catch(e=>toast(e.message));
 $('finish-preset').onclick=async()=>{if(!presetWorkflow)return;try{await queue;if(state.settings.mode===3)throw Error('Choose Direct lighting before finishing a lighting preset');const p=presetWorkflow;const result=await api(p.id?'presets/replace':'presets/save',p.id?{id:p.id}:{name:p.name});activePreset=result.id;presetWorkflow=null;await refresh();renderWorkflow();toast('Lighting preset saved');}catch(e){toast(e.message);}};
}
function initTheme(){
 const media=matchMedia('(prefers-color-scheme: light)');let preference='dark';try{preference=localStorage.getItem('smk-theme')||'dark';}catch{}
 if(!['dark','light','system'].includes(preference))preference='dark';$('theme').value=preference;
 const apply=()=>{document.documentElement.dataset.theme=$('theme').value==='system'?(media.matches?'light':'dark'):$('theme').value;};
 $('theme').onchange=()=>{apply();try{localStorage.setItem('smk-theme',$('theme').value);}catch{}};media.addEventListener('change',apply);apply();
}
function formatMacro(steps){return steps.map(s=>[...modifiers.filter(m=>s.mods&m[1]).map(m=>m[0]),outputKeys.find(k=>k[1]===s.key)?.[0]||'None'].join('+')+', '+s.delay).join('\n');}
function parseMacro(text){
 const lines=text.split(/\r?\n/).map(s=>s.trim()).filter(Boolean);if(lines.length>8)throw Error('A macro can contain up to eight steps');
 return lines.map(line=>{const parts=line.split(',');if(parts.length>2)throw Error('Use Shortcut, delay');const delay=parts.length===1?100:Number(parts[1].trim());if(!Number.isInteger(delay)||delay<0||delay>2550||delay%10)throw Error('Delay must be 0–2550 ms, in steps of 10');let mods=0,key=null;for(const name of parts[0].split('+').map(s=>s.trim())){const mod=modifiers.find(m=>m[0].toUpperCase()===name.toUpperCase());if(mod)mods|=mod[1];else{const found=outputKeys.find(k=>k[0].toUpperCase()===name.toUpperCase());if(!found||key!==null)throw Error('Unknown or extra macro key: '+name);key=found[1];}}return {key:key===null?0:key,mods,delay};});
}
async function deviceAction(action,data={}){deviceBusy=true;renderDeviceInfo();try{return await api('device/'+action,data);}finally{deviceBusy=false;renderDeviceInfo();}}
function initDeviceControls(){
 [...deviceEffects,'CM1','CM2','CM3','CM4','CM5'].forEach((n,i)=>$('onboard-effect').add(new Option(n,i)));
 $('onboard-effect').onchange=async()=>{try{const n=+$('onboard-effect').value;await deviceAction(n<10?'effect':'preset',{index:n<10?n:n-10});await refresh();}catch(e){toast(e.message);}};
 for(let i=0;i<5;i++){$('cm-buttons').append(button('CM'+(i+1),async()=>{await deviceAction('preset',{index:i});await refresh();},'button secondary'));$('cm-edit-profile').add(new Option('CM'+(i+1)+' · '+['Glacier','Arena','Midnight','Sunset','Aurora'][i],i));}
 for(const key of state.device.keys){const name=key.name.replace('Key: ','');$('binding-key').add(new Option(name+(key.cell===99?' (reserved)':''),key.cell));$('cm-edit-key').add(new Option(name,key.cell));}
 outputKeys.forEach(([name,value])=>$('binding-output').add(new Option(name,value)));
 for(const [name,mask] of modifiers){const label=document.createElement('label'),input=document.createElement('input');input.type='checkbox';input.value=mask;label.append(input,document.createTextNode(name));$('binding-modifiers').append(label);}
 for(let i=0;i<4;i++){$('binding-macro').add(new Option('Macro '+(i+1),i));const label=document.createElement('label');label.className='field';label.textContent='Macro '+(i+1);const input=document.createElement('textarea');input.id='macro-'+i;input.rows=6;input.spellcheck=false;input.placeholder='Ctrl+C, 100\nCtrl+V, 100';input.oninput=dirtyDevice;label.append(input);$('macro-editors').append(label);}
 factoryPalette.forEach((colour,i)=>{const b=button(i===0?'Off':'',()=>{if(!deviceDraft)return;paintColour=i;$('paint-colour-label').textContent='Brush: '+(i===0?'Off':currentPalette()[i].toUpperCase());renderPalette();},'palette-colour');b.style.background=colour;b.title=i===0?'Off':colour;b.setAttribute('aria-label',b.title);$('cm-palette').append(b);});
 $('cm-edit-profile').onchange=()=>{renderPalette();renderDeviceKeyboard();};$('cm-edit-key').onchange=()=>selectDeviceKey(+$('cm-edit-key').value);$('binding-key').onchange=()=>selectDeviceKey(+$('binding-key').value);$('binding-type').onchange=()=>{bindingFields();applyBinding();};
 for(const input of [$('binding-output'),$('binding-macro'),...$('binding-modifiers').querySelectorAll('input')])input.onchange=()=>applyBinding();
 keyboard('device-keyboard',selectDeviceKey);for(const b of document.querySelectorAll('[data-device-view]'))b.onclick=()=>{deviceView=b.dataset.deviceView;renderDeviceKeyboard();};
 $('cm-clear').onclick=()=>{rememberPaint();deviceDraft.presets[+$('cm-edit-profile').value].fill(0);dirtyDevice();};
 initPainting();initResets();

 $('read-keyboard').onclick=()=>loadDevice(true).catch(e=>toast(e.message));$('discard-keyboard').onclick=()=>loadDevice(true).catch(e=>toast(e.message));
 $('write-keyboard').onclick=()=>saveDevice().catch(e=>toast(e.message));
 $('cm-custom-colour').onchange=()=>chooseCustomColour($('cm-custom-colour').value);
 $('cm-default').onclick=()=>{try{resetDraft('cm');dirtyDevice();}catch(e){toast(e.message);}};
 $('default-key').onclick=()=>{resetDraft('key');dirtyDevice();};
}

window.addEventListener('beforeunload',e=>{if(deviceDirty){e.preventDefault();e.returnValue='';}});
init().catch(e=>{$('connection').textContent='Unable to connect';toast(e.message);});
