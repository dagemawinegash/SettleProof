import {$, $$, escape, money, date, icon, hydrateIcons, api, toast, showDialog} from './ui.js';

const state = {view:'workspace', runs:[], run:null, report:null, selected:null, filter:'all', query:'', poll:null};

function render() {
  $$('.nav-item[data-view]').forEach(button => {button.classList.toggle('active',button.dataset.view === state.view);button.setAttribute('aria-current',button.dataset.view === state.view ? 'page' : 'false');});
  $('#breadcrumb-current').textContent = state.view === 'history' ? 'Run history' : 'Reconciliation';
  $('#history-count').textContent = state.runs.length;
  $('#content').innerHTML = state.view === 'history' ? historyView() : workspaceView();
}

function workspaceView() {
  return `<div class="page-heading"><div><span class="eyebrow">RECONCILIATION WORKSPACE</span><h1>Your numbers. Their paper trail.</h1><p class="page-description">Bring your payment export and bank deposits together. Follow every difference back to its source.</p></div></div>
  <section class="welcome"><div class="welcome-copy"><span class="pill green">${icon('shield')}Source-checked reconciliation</span><h2>Close the gap.<br>Keep the evidence.</h2><p>An agent writes and runs the comparison. An independent checker verifies the numbers. You see exactly what matches, and what needs another look.</p><button class="button primary" data-action="new">${icon('plus')}Start a reconciliation</button><button class="text-button" data-action="guide">See how it works ${icon('arrow')}</button><div class="welcome-footnote">${icon('lock')}Your files stay in this workspace and its isolated execution sandbox.</div></div><div class="paper-illustration" aria-hidden="true"><div class="paper-shadow"></div><div class="paper-receipt"><div class="receipt-top"><img src="/static/mark.svg" width="23" height="27" alt=""><span>A CLEARER PICTURE</span></div><div class="receipt-line"><i></i><i></i></div><div class="receipt-line"><i></i><i></i></div><div class="receipt-line"><i></i><i></i></div><div class="receipt-total"><span>Every number</span><strong>A source.</strong></div><div class="receipt-seal">${icon('check')}FOLLOW THE PAPER TRAIL</div><div class="receipt-rip"></div></div></div></section><div class="intro-notes"><div><span>01</span><strong>Two files in</strong><p>Payment activity and bank deposits. One currency, clear rules.</p></div><div><span>02</span><strong>Every claim checked</strong><p>Exact amounts, original rows, and a reproducible comparison.</p></div><div><span>03</span><strong>Answers you can inspect</strong><p>Matches, open questions, and the source evidence behind both.</p></div></div>`;
}

function historyView() {
  return `<div class="page-heading"><div><span class="eyebrow">YOUR WORKSPACE</span><h1>Run history</h1><p class="page-description">A record of your reconciliations, with the work behind each result.</p></div><button class="button" data-action="refresh">${icon('replay')}Refresh</button></div><section class="panel"><div class="panel-heading"><h2>Recent runs</h2><span class="muted">${state.runs.length} runs</span></div>${state.runs.length ? state.runs.map(run => `<button class="history-row" data-run="${escape(run.run_id)}"><span class="file-tile">${icon('ledger')}</span><span><strong>${escape(run.run_id)}</strong><small>${date(run.started_at)}</small></span><span class="pill">${escape(run.status)}</span>${icon('chevron')}</button>`).join('') : '<div class="empty-state">Your first reconciliation will appear here.</div>'}</section>`;
}

async function loadHistory() {
  const result = await api('/runs');
  state.runs = result.runs;
}

async function openRun(runId) {
  state.run = await api('/runs/' + encodeURIComponent(runId));
  state.report = state.run.report_available ? await api('/runs/' + encodeURIComponent(runId) + '/report') : null;
  state.view = 'workspace';
  render();
}

document.addEventListener('click', async event => {
  const close = event.target.closest('[data-close]');
  if (close) {close.closest('dialog').close();return;}
  const navigation = event.target.closest('[data-view]');
  if (navigation) {state.view = navigation.dataset.view;render();return;}
  const run = event.target.closest('[data-run]');
  if (run) {try {await openRun(run.dataset.run);} catch(error) {toast(error.message,true);}return;}
  const action = event.target.closest('[data-action]')?.dataset.action;
  if (action === 'guide') showDialog('#guide-dialog');
  if (action === 'new') showNewRun();
  if (action === 'refresh') {try {await loadHistory();render();} catch(error) {toast(error.message,true);}}
});

function showNewRun() {toast('Preparing file import…');}

document.addEventListener('keydown', event => {
  if (event.key.toLowerCase() === 'n' && !event.ctrlKey && !event.metaKey && !event.altKey && !event.target.closest('input,textarea,select,dialog')) {event.preventDefault();showNewRun();}
});

async function init() {
  hydrateIcons();
  try {
    await api('/health');
    $('#server-dot').classList.add('online');
    $('#server-label').textContent = 'Workspace connected';
    await loadHistory();
    render();
  } catch(error) {render();toast(error.message,true);$('#server-label').textContent = 'Connection unavailable';}
}
init();
