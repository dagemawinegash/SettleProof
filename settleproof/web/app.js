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

const upload = {payments:null, bank:null, valid:false, revision:0, starting:false};
function showNewRun() {
  let dialog = $('#upload-dialog');
  if (!dialog) {
    dialog = document.createElement('dialog');
    dialog.id = 'upload-dialog';
    dialog.className = 'modal upload-modal';
    dialog.setAttribute('aria-labelledby','upload-title');
    dialog.innerHTML = `<div class="modal-top"><span class="eyebrow">NEW RECONCILIATION</span><button class="icon-button" data-close aria-label="Close file import">${icon('close')}</button></div><h2 id="upload-title">Bring both sides of the story.</h2><p class="muted">Compare a payment export with your bank deposits. Your originals stay unchanged.</p><div class="upload-grid">${['payments','bank'].map((kind,index) => `<div><label class="field-label" for="${kind}-file"><span>0${index+1}</span>${kind === 'payments' ? 'Payment activity' : 'Bank deposits'}</label><div class="dropzone" data-kind="${kind}"><input id="${kind}-file" type="file" accept=".csv,text/csv" aria-describedby="${kind}-hint"><span class="upload-icon">${icon(kind === 'payments' ? 'file' : 'bank')}</span><strong id="${kind}-name">Choose a CSV file</strong><small id="${kind}-hint">or drop it here · up to 256 KB</small><span class="choose-file">Browse files ${icon('arrow')}</span></div></div>`).join('')}</div><div class="sample-row"><div>${icon('layers')}<span>Just exploring? <strong>Use synthetic sample files.</strong></span></div><button class="button small" id="sample-files">Load samples ${icon('arrow')}</button></div><div id="validation-status" class="validation-status" role="status">Select both files to check their format.</div><details class="format-details"><summary>Supported file format <span>USD · 200 rows per file</span></summary><p>Amounts are decimal dollars. Fees are documented in the payment file; refunds use a positive amount and <code>kind=refund</code>. Shared payout references connect the two files.</p><strong>Payment columns</strong><code>payment_id,payout_id,kind,amount,fee,currency</code><strong>Bank columns</strong><code>deposit_id,payout_id,amount,currency</code><div class="sample-links"><a href="/api/samples/payments" download>Payment sample ↗</a><a href="/api/samples/bank" download>Bank sample ↗</a></div></details><div class="upload-footer"><span>${icon('lock')}Source-checked. No financial writes.</span><button class="button primary" id="start-run" disabled>Reconcile files ${icon('arrow')}</button></div>`;
    document.body.append(dialog);
    $$('.dropzone',dialog).forEach(zone => {
      const input = $('input',zone);
      input.addEventListener('change',() => chooseFile(zone.dataset.kind,input.files[0]));
      zone.addEventListener('dragover',event => {event.preventDefault();zone.classList.add('dragging');});
      zone.addEventListener('dragleave',() => zone.classList.remove('dragging'));
      zone.addEventListener('drop',event => {event.preventDefault();zone.classList.remove('dragging');chooseFile(zone.dataset.kind,event.dataTransfer.files[0]);});
    });
    $('#sample-files').addEventListener('click',loadSamples);
    $('#start-run').addEventListener('click',startRun);
  }
  showDialog('#upload-dialog');
}

function uploadStatus(message, type = '') {
  const el = $('#validation-status');
  el.className = 'validation-status ' + type;
  el.innerHTML = (type === 'valid' ? icon('check') : type === 'invalid' ? icon('alert') : '') + `<span>${escape(message)}</span>`;
}

async function chooseFile(kind, file) {
  upload.valid = false;
  $('#start-run').disabled = true;
  if (!file) return;
  if (file.size > 256000) {uploadStatus('Each file must be at most 256,000 bytes.','invalid');return;}
  if (!file.name.toLowerCase().endsWith('.csv')) {uploadStatus('Choose a .csv file for each source.','invalid');return;}
  upload[kind] = file;
  $('#' + kind + '-name').textContent = file.name;
  $('#' + kind + '-hint').textContent = (file.size / 1000).toFixed(1) + ' KB · ready to validate';
  $(`.dropzone[data-kind="${kind}"]`).classList.add('has-file');
  await validateUpload();
}

function uploadForm() {const form = new FormData();form.append('payments',upload.payments);form.append('bank',upload.bank);return form;}

async function validateUpload() {
  const revision = ++upload.revision;
  if (!upload.payments || !upload.bank) {uploadStatus('Choose the other file to check both sources.');return;}
  uploadStatus('Checking file formats and source records…');
  try {
    const result = await api('/validate',{method:'POST',body:uploadForm()});
    if (revision !== upload.revision) return;
    upload.valid = true;
    uploadStatus(`${result.payments} payment rows + ${result.bank} bank rows · USD · ready to reconcile`,'valid');
    $('#start-run').disabled = false;
  } catch(error) {if (revision === upload.revision) uploadStatus(error.message,'invalid');}
}

async function loadSamples() {
  $('#sample-files').disabled = true;
  try {
    const kinds = ['payments','bank'];
    const files = await Promise.all(kinds.map(async kind => {const response = await fetch('/api/samples/' + kind);if (!response.ok) throw new Error('Sample files are unavailable.');return new File([await response.blob()],'sample-' + kind + '.csv',{type:'text/csv'});}));
    for (let i = 0; i < kinds.length; i++) {upload[kinds[i]] = files[i];$('#' + kinds[i] + '-name').textContent = files[i].name;$('#' + kinds[i] + '-hint').textContent = 'Synthetic data · safe to explore';$(`.dropzone[data-kind="${kinds[i]}"]`).classList.add('has-file');}
    upload.valid = false;
    await validateUpload();
  } catch(error) {uploadStatus(error.message,'invalid');}
  finally {$('#sample-files').disabled = false;}
}

async function startRun() {
  if (!upload.valid || upload.starting) return;
  upload.starting = true;
  const button = $('#start-run');button.disabled = true;button.innerHTML = '<span class="spinner"></span>Starting…';
  try {
    const result = await api('/runs',{method:'POST',body:uploadForm()});
    $('#upload-dialog').close();
    await openRun(result.run_id);
    pollRun(result.run_id);
  } catch(error) {uploadStatus(error.message,'invalid');}
  finally {upload.starting = false;button.disabled = !upload.valid;button.innerHTML = `Reconcile files ${icon('arrow')}`;}
}

function pollRun(runId) {toast('Reconciliation started. The agent is working in the background.');}

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
