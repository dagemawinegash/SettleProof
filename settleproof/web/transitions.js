import {animate, stagger} from './vendor/motion.js';

export const reducedMotion = () => matchMedia('(prefers-reduced-motion: reduce)').matches;
const ease = [0.22, 1, 0.36, 1];
export function enterPage(root, progressUpdate = false) {
  if (reducedMotion()) return;
  const targets = [...root.querySelectorAll(progressUpdate ? '.progress-current-title' : '.motion-enter')].slice(0,12);
  if (!targets.length&&!progressUpdate) targets.push(...[...root.children].slice(0,8));
  if (targets.length) animate(targets,{opacity:[0,1],y:[progressUpdate ? 5 : 16,0]},
    {duration:progressUpdate ? .25 : .55,delay:stagger(.055),ease});
  const mark = root.querySelector('.completion-art');
  if (mark && !progressUpdate) animate(mark,{opacity:[0,1],scale:[.88,1],rotate:[-5,0]},
    {type:'spring',duration:.8,bounce:.2,delay:.12});
}
export function enterList(root) {
  if (reducedMotion()) return;
  const items = [...root.querySelectorAll('.review-item')].slice(0,10);
  if (items.length) animate(items,{opacity:[0,1],y:[8,0]},{duration:.32,delay:stagger(.035),ease});
}
export function openModal(dialog) {
  dialog.classList.remove('is-closing');
  dialog.getAnimations().forEach(animation=>animation.cancel());
  if (reducedMotion()) return;
  const drawer = dialog.classList.contains('detail-drawer');
  const mobile=matchMedia('(max-width:760px)').matches;
  animate(dialog,drawer ? mobile ? {opacity:[.6,1],y:[90,0]} : {opacity:[.5,1],x:[80,0]} : {opacity:[0,1],y:[24,0],scale:[.97,1]},
    {type:'spring',duration:drawer ? .5 : .4,bounce:drawer ? .08 : .12});
}
export async function leaveModal(dialog) {
  if (reducedMotion()) return;
  dialog.classList.add('is-closing');
  const drawer=dialog.classList.contains('detail-drawer'), mobile=matchMedia('(max-width:760px)').matches;
  await animate(dialog,drawer ? mobile ? {opacity:0,y:55} : {opacity:0,x:55} : {opacity:0,y:12,scale:.98},
    {duration:.17,ease:'easeIn'});
}
export function animateDisclosure(details) {
  if (reducedMotion() || !details.open) return;
  const content = details.querySelector('.disclosure-body');
  if (content) animate(content,{opacity:[0,1],y:[-6,0]},{duration:.3,ease});
}
export function moveFilter(target) {
  const parent = target.closest('.review-tabs');
  const marker = parent?.querySelector('.tab-marker');
  if (!marker) return;
  const x = target.offsetLeft, width = target.offsetWidth;
  if (reducedMotion()) {marker.style.transform=`translateX(${x}px)`;marker.style.width=width+'px';return;}
  animate(marker,{x,width},{type:'spring',duration:.35,bounce:.08});
}
