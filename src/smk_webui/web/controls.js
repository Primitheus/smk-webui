'use strict';
// Keep native select values and change events; replace only their presentation.
function initSelects(){
 let opened=null;
 const close=()=>{if(opened){opened.menu.remove();opened.button.setAttribute('aria-expanded','false');opened=null;}};
 const enhance=select=>{
  if(select.dataset.enhanced)return;select.dataset.enhanced='true';select.classList.add('native-select');select.tabIndex=-1;
  const wrap=document.createElement('span');wrap.className='select-control';select.before(wrap);wrap.append(select);
  const button=document.createElement('button');button.type='button';button.className='select-trigger';button.setAttribute('aria-haspopup','listbox');button.setAttribute('aria-expanded','false');button.setAttribute('aria-label',select.getAttribute('aria-label')||select.closest('label')?.firstChild?.textContent?.trim()||'Select');wrap.append(button);
  const sync=()=>{button.textContent=select.selectedOptions[0]?.text||'Select';button.disabled=select.disabled||!!select.closest('fieldset:disabled');};sync();select.addEventListener('change',sync);select.addEventListener('focus',()=>button.focus());
  const open=()=>{
   if(opened?.button===button){close();return;}close();
   const menu=document.createElement('div');menu.className='select-menu';menu.setAttribute('role','listbox');let index=Math.max(0,select.selectedIndex);
   const pick=i=>{select.selectedIndex=i;select.dispatchEvent(new Event('change',{bubbles:true}));sync();close();button.focus();};
   const items=[...select.options].map((option,i)=>{const item=document.createElement('button');item.type='button';item.className='select-option';item.textContent=option.text;item.setAttribute('role','option');item.setAttribute('aria-selected',String(i===select.selectedIndex));item.disabled=option.disabled;item.onclick=()=>pick(i);menu.append(item);return item;});
   const host=select.closest('dialog')||document.body;host.append(menu);const rect=button.getBoundingClientRect();menu.style.width=rect.width+'px';menu.style.left=Math.min(rect.left,innerWidth-rect.width-8)+'px';menu.style.maxHeight=Math.min(280,innerHeight-24)+'px';const height=menu.getBoundingClientRect().height;menu.style.top=(rect.bottom+height+8>innerHeight?Math.max(8,rect.top-height-5):rect.bottom+5)+'px';
   opened={button,menu};button.setAttribute('aria-expanded','true');items[index]?.focus();
   menu.onkeydown=e=>{if(e.key==='Escape'){e.preventDefault();close();button.focus();return;}if(['ArrowDown','ArrowUp','Home','End'].includes(e.key)){e.preventDefault();index=e.key==='Home'?0:e.key==='End'?items.length-1:Math.max(0,Math.min(items.length-1,index+(e.key==='ArrowDown'?1:-1)));items[index]?.focus();}else if(e.key.length===1){const next=items.findIndex(item=>item.textContent.toLowerCase().startsWith(e.key.toLowerCase()));if(next>=0){index=next;items[index].focus();}}};
  };
  button.onclick=open;button.onkeydown=e=>{if(e.key==='ArrowDown'||e.key==='ArrowUp'){e.preventDefault();open();}};
  return sync;
 };
 const syncs=[];const scan=()=>{for(const select of document.querySelectorAll('select:not([data-enhanced])'))syncs.push(enhance(select));};scan();
 new MutationObserver(scan).observe(document.body,{childList:true,subtree:true});
 setInterval(()=>syncs.forEach(sync=>sync()),150);
 document.addEventListener('pointerdown',e=>{if(opened&&!opened.menu.contains(e.target)&&!opened.button.contains(e.target))close();});window.addEventListener('resize',close);document.addEventListener('scroll',e=>{if(opened&&!opened.menu.contains(e.target))close();},true);
 document.addEventListener('visibilitychange',()=>{if(!document.hidden)startPresetPreviews();});
}
