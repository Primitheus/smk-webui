'use strict';
const screenRegions={Full:[0,0,100,100],Left:[0,0,50,100],Right:[50,0,50,100],Top:[0,0,100,50],Bottom:[0,50,100,50]};
function renderScreenControls(p){
 $('screen-controls').hidden=p.type!=='Screen Colours';
 if(p.type!=='Screen Colours')return;
 const monitor=p.screen_monitor||'',select=$('screen-monitor');
 if(![...select.options].some(o=>o.value===monitor))select.add(new Option('Unavailable Display',monitor));select.value=monitor;
 $('screen-mapping').value=p.screen_mode||'Zones';const region=p.screen_region||screenRegions.Full;
 $('screen-region').value=Object.keys(screenRegions).find(k=>JSON.stringify(screenRegions[k])===JSON.stringify(region))||'Custom';
 $('screen-custom-region').hidden=$('screen-region').value!=='Custom';
 ['left','top','width','height'].forEach((k,i)=>$('screen-'+k).value=region[i]);
 $('screen-region-box').style.cssText=`left:${region[0]}%;top:${region[1]}%;width:${region[2]}%;height:${region[3]}%`;
}
async function refreshScreens(){
 const current=state.settings.studio.layers[layerIndex]?.screen_monitor||'';
 try{const response=await api('screens');$('screen-monitor').replaceChildren(new Option('Primary Display',''));
  for(const m of response.monitors)$('screen-monitor').add(new Option(m.name+' / '+m.width+' x '+m.height,m.id));
  if(current&&![...$('screen-monitor').options].some(o=>o.value===current))$('screen-monitor').add(new Option('Unavailable Display',current));$('screen-monitor').value=current;
  $('screen-source-status').textContent=response.error||'';
 }catch(e){$('screen-source-status').textContent=e.message;}
}
function initScreenControls(){
 $('screen-refresh').onclick=refreshScreens;refreshScreens();
 $('screen-monitor').onchange=()=>updateLayer({screen_monitor:$('screen-monitor').value});
 $('screen-mapping').onchange=()=>updateLayer({screen_mode:$('screen-mapping').value});
 $('screen-region').onchange=()=>{const key=$('screen-region').value;$('screen-custom-region').hidden=key!=='Custom';if(screenRegions[key])updateLayer({screen_region:[...screenRegions[key]]});};
 $('screen-region-apply').onclick=()=>updateLayer({screen_region:['left','top','width','height'].map(k=>Number($('screen-'+k).value))});
}
