import {$,api,icon,showDialog} from './ui.js';

export function configureHosting(health) {
  if (!health.hosted) return;
  const workspace=$('.workspace-label>div');
  if (workspace) workspace.innerHTML=(health.owner ? 'Owner workspace' : 'Public demo')+'<small>Hosted on CreateOS</small>';
  const note=document.createElement('div');
  note.className='hosted-note';
  note.innerHTML=health.owner ? '<strong>Owner workspace</strong><span>Live comparisons use your configured model and sandbox credits.</span>' : '<strong>Public demo</strong><span>Explore a real, previously executed comparison using synthetic files. Live runs require owner access.</span><a href="https://cap.so/s/5feskmzdaptx9c7" target="_blank" rel="noopener">Watch the demo ↗</a>';
  $('#main').prepend(note);
  if (health.owner) return;
  const top=$('.topbar [data-action="new"]');
  if (health.read_only) {
    top.innerHTML=icon('external')+'Watch live run';
    note.querySelector('span').textContent='Explore a real, previously executed comparison using synthetic files. This public viewer is read-only.';
    document.addEventListener('click',event=>{if(event.target.closest('[data-action="new"]')) {event.preventDefault();event.stopImmediatePropagation();window.open('https://cap.so/s/5feskmzdaptx9c7','_blank','noopener');}},true);
    return;
  }
  top.innerHTML=icon('lock')+'Owner access';
  async function unlock() {
    let dialog=$('#owner-dialog');
    if (!dialog) {
      dialog=document.createElement('dialog');dialog.id='owner-dialog';dialog.className='modal';
      dialog.setAttribute('aria-labelledby','owner-title');
      dialog.innerHTML=`<div class="modal-top"><span class="eyebrow">PRIVATE WORKSPACE</span><button class="icon-button" data-close aria-label="Close owner access">${icon('close')}</button></div><h2 id="owner-title">Run your own comparison.</h2><p class="muted">The public sample is open to everyone. An owner access code unlocks live runs and private history.</p><form id="owner-form"><label class="field-label" for="owner-code">Owner access code</label><input id="owner-code" type="password" autocomplete="current-password" required minlength="20"><p id="owner-error" role="status"></p><button class="button primary" type="submit">Unlock workspace ${icon('arrow')}</button></form>`;
      document.body.append(dialog);
      $('#owner-form').addEventListener('submit',async event=>{
        event.preventDefault();const button=$('#owner-form button');button.disabled=true;
        try {await api('/session',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({code:$('#owner-code').value})});location.reload();}
        catch(error) {$('#owner-error').textContent=error.message;button.disabled=false;}
      });
    }
    showDialog(dialog);
  }
  document.addEventListener('click',event=>{if(event.target.closest('[data-action="new"]')) {event.preventDefault();event.stopImmediatePropagation();unlock();}},true);
  document.addEventListener('keydown',event=>{if(event.key.toLowerCase()==='n'&&!event.ctrlKey&&!event.metaKey&&!event.altKey&&!event.target.closest('input,textarea,select,dialog')) {event.preventDefault();event.stopImmediatePropagation();unlock();}},true);
}
