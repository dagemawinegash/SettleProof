export const $ = (selector, root = document) => root.querySelector(selector);
export const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
export const escape = (value) => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
export const money = (minor) => new Intl.NumberFormat('en-US', {style:'currency', currency:'USD'}).format((minor || 0) / 100);
export const date = (value) => value ? new Intl.DateTimeFormat('en-US', {month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'}).format(new Date(value)) : 'Just now';
const paths = {
 ledger:'<rect x="4" y="3" width="16" height="18" rx="2"/><path d="M8 7h8M8 11h8M8 15h3M15 15h1M8 18h3M15 18h1"/>',
 history:'<path d="M3 10a9 9 0 1 1 2 8M3 4v6h6M12 7v5l3 2"/>',
 layers:'<path d="m12 3 9 5-9 5-9-5 9-5Zm-9 9 9 5 9-5M3 16l9 5 9-5"/>',
 plus:'<path d="M12 5v14M5 12h14"/>',
 close:'<path d="m6 6 12 12M6 18 18 6"/>',
 arrow:'<path d="M5 12h14m-5-5 5 5-5 5"/>',
 down:'<path d="m6 9 6 6 6-6"/>',
 up:'<path d="m6 15 6-6 6 6"/>',
 check:'<path d="m5 12 4 4L19 6"/>',
 shield:'<path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6l8-3Z"/><path d="m8 12 3 3 5-6"/>',
 help:'<circle cx="12" cy="12" r="9"/><path d="M9.5 9a2.5 2.5 0 1 1 4 2c-1 .7-1.5 1-1.5 2M12 16h.01"/>',
 upload:'<path d="M12 16V3m-5 5 5-5 5 5M4 15v5h16v-5"/>',
 file:'<path d="M14 3H5v18h14V8l-5-5Zm0 0v5h5M8 12h8M8 16h5"/>',
 bank:'<path d="m3 8 9-5 9 5H3Zm0 13h18M5 11v7M10 11v7M14 11v7M19 11v7"/>',
 search:'<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
 filter:'<path d="M4 6h16M7 12h10M10 18h4"/>',
 alert:'<path d="m12 3 10 18H2L12 3Zm0 6v5m0 3h.01"/>',
 code:'<path d="m8 6-6 6 6 6m8-12 6 6-6 6M14 4l-4 16"/>',
 download:'<path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5"/>',
 replay:'<path d="M3 11a9 9 0 1 1 2 7M3 4v7h7"/>',
 lock:'<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 1 1 8 0v3M12 14v3"/>',
 clock:'<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
 chevron:'<path d="m9 5 7 7-7 7"/>',
 external:'<path d="M14 3h7v7m0-7L10 14M10 3H3v18h18v-7"/>',
 copy:'<rect x="8" y="8" width="12" height="13" rx="2"/><path d="M15 8V3H3v13h5"/>',
 dots:'<circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/>'
};
export const icon = (name, cls = '') => `<svg class="icon ${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name] || paths.file}</svg>`;
export function hydrateIcons(root = document) { $$('[data-icon]', root).forEach(el => {el.innerHTML = icon(el.dataset.icon);}); }
export async function api(path, options = {}) {
  const response = await fetch('/api' + path, {...options, headers:{'X-SettleProof':'1',...options.headers}});
  const result = await response.json();
  if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : 'The request could not be completed. Check the supported file format.');
  return result;
}
export function toast(message, error = false) {
  const element = $('#toast');
  element.textContent = message;
  element.classList.toggle('error', error);
  element.hidden = false;
  clearTimeout(element.timer);
  element.timer = setTimeout(() => {element.hidden = true;}, 6500);
}
export function showDialog(id) {
  const dialog = typeof id === 'string' ? $(id) : id;
  if (dialog.open) return;
  dialog.style.opacity='';dialog.style.transform='';
  dialog.showModal();openModal(dialog);
  if (!dialog.motionEvents) {
    dialog.motionEvents=true;
    dialog.addEventListener('cancel',event => {event.preventDefault();closeDialog(dialog);});
    dialog.addEventListener('click',event => {
      if (event.target !== dialog) return;
      const box=dialog.getBoundingClientRect();
      if (event.clientX<box.left || event.clientX>box.right || event.clientY<box.top || event.clientY>box.bottom) closeDialog(dialog);
    });
  }
}
export async function closeDialog(id) {
  const dialog = typeof id === 'string' ? $(id) : id;
  if (!dialog?.open || dialog.closing) return;
  dialog.closing=true;
  try {await leaveModal(dialog);} finally {dialog.close();dialog.closing=false;dialog.classList.remove('is-closing');dialog.style.opacity='';dialog.style.transform='';}
}
import {openModal, leaveModal} from './transitions.js';
