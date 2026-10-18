import {$, $$, escape, money, date, icon, hydrateIcons, api, toast, showDialog, closeDialog} from './ui.js';
import {inspectRun, exportRun} from './inspector.js';
import {renderReview,renderReviewItems,renderReviewDetail,renderFocusedProgress} from './review-view.js';
import {enterPage,enterList,moveFilter,animateDisclosure} from './transitions.js';
import {configureHosting} from './hosted-ui.js';

const state = {view:'workspace', runs:[], run:null, report:null, selected:null, filter:'all', query:'', poll:null, showAllItems:false};

function render() {
  $$('.nav-item[data-view]').forEach(button => {button.classList.toggle('active',button.dataset.view === state.view);button.setAttribute('aria-current',button.dataset.view === state.view ? 'page' : 'false');});
  $('#breadcrumb-current').textContent = state.view === 'history' ? 'Run history' : state.report ? 'Results' : 'Compare files';
  $('#history-count').textContent=state.runs.length;
  const progressUpdate=!!$('#content .focus-progress');
  $('#content').innerHTML = state.view === 'history' ? historyView() : workspaceView();
  if (state.view==='workspace'&&state.run&&!state.report) $('#content').insertAdjacentHTML('beforeend',`<div class="execution-link-row"><button class="text-button" data-action="inspector">How is this being checked? ${icon('arrow')}</button></div>`);
  enterPage($('#content'),progressUpdate&&!!$('#content .focus-progress'));
  requestAnimationFrame(()=>{const tab=$(`[data-filter="${state.filter}"]`);if(tab) moveFilter(tab);});
}

function workspaceView() {
  if (state.report) return reportView();
  if (state.run) return progressView();
  return `<div class="page-heading"><div><span class="eyebrow">RECONCILIATION WORKSPACE</span><h1>Your numbers. Their paper trail.</h1><p class="page-description">Bring your payment export and bank deposits together. Follow every difference back to its source.</p></div></div>
  <section class="welcome"><div class="welcome-copy"><span class="pill green">${icon('shield')}Source-checked reconciliation</span><h2>Close the gap.<br>Keep the evidence.</h2><p>An agent writes and runs the comparison. An independent checker verifies the numbers. You see exactly what matches, and what needs another look.</p><button class="button primary" data-action="new">${icon('plus')}Start a reconciliation</button><button class="text-button" data-action="guide">See how it works ${icon('arrow')}</button><div class="welcome-footnote">${icon('lock')}Your files stay in this workspace and its isolated execution sandbox.</div></div><div class="paper-illustration" aria-hidden="true"><div class="paper-shadow"></div><div class="paper-receipt"><div class="receipt-top"><img src="/static/mark.svg" width="23" height="27" alt=""><span>A CLEARER PICTURE</span></div><div class="receipt-line"><i></i><i></i></div><div class="receipt-line"><i></i><i></i></div><div class="receipt-line"><i></i><i></i></div><div class="receipt-total"><span>Every number</span><strong>A source.</strong></div><div class="receipt-seal">${icon('check')}FOLLOW THE PAPER TRAIL</div><div class="receipt-rip"></div></div></div></section><div class="intro-notes"><div><span>01</span><strong>Two files in</strong><p>Payment activity and bank deposits. One currency, clear rules.</p></div><div><span>02</span><strong>Every claim checked</strong><p>Exact amounts, original rows, and a reproducible comparison.</p></div><div><span>03</span><strong>Answers you can inspect</strong><p>Matches, open questions, and the source evidence behind both.</p></div></div>`;
}

function historyView() {
  const status = run => ({checked:'Checked',failed:'Stopped',cancelled:'Cancelled',interrupted:'Interrupted',running:'In progress',cancelling:'Stopping'}[run.status] || run.status);
  return `<div class="page-heading"><div><span class="eyebrow">YOUR WORKSPACE</span><h1>Run history</h1><p class="page-description">A record of your reconciliations, with the work behind each result.</p></div><button class="button" data-action="refresh">${icon('replay')}Refresh</button></div><div class="history-storage-note">${icon(state.database === 'connected' ? 'check' : 'alert')}<span>${state.database === 'public_demo' ? 'Showing the public synthetic demonstration. Private runs require owner access.' : state.database === 'connected' ? 'History synced with Neon. Source files and execution artifacts stay in this workspace.' : 'Showing local history. The metadata database is currently unavailable.'}</span></div><section class="panel"><div class="panel-heading"><h2>Recent runs</h2><span class="muted">${state.runs.length} runs</span></div>${state.runs.length ? state.runs.map(run => `<button class="history-row" data-run="${escape(run.run_id)}" ${!run.artifacts_available ? 'disabled title="Only metadata is available. The source artifacts are not on this machine."' : ''}><span class="file-tile">${icon('ledger')}</span><span class="history-file-names"><strong>${escape(run.input_names?.payments || 'payments.csv')} <span class="muted">+</span> ${escape(run.input_names?.bank || 'bank.csv')}</strong><small>${date(run.started_at)} <span class="source-plus">·</span> <span class="mono">${escape(run.run_id.slice(-8))}</span>${run.data_kind === 'synthetic_sample' ? '<span class="sample-badge">Synthetic sample</span>' : ''}</small></span><span class="history-difference">${run.summary ? money(run.summary.difference_minor) : '—'}<small>net difference</small></span><span class="pill ${run.status === 'checked' ? 'green' : run.status === 'failed' ? 'amber' : ''}">${escape(status(run))}</span>${!run.artifacts_available ? '<span class="metadata-only">Metadata only</span>' : icon('chevron')}</button>`).join('') : '<div class="empty-state">Your first reconciliation will appear here.<br><button class="text-button" data-action="new">Start a reconciliation '+icon('arrow')+'</button></div>'}</section>`;
}

async function loadHistory() {
  const result = await api('/runs');
  state.runs = result.runs;
  state.database = result.database;
}

async function openRun(runId) {
  state.run = await api('/runs/' + encodeURIComponent(runId));
  state.report = state.run.report_available ? await api('/runs/' + encodeURIComponent(runId) + '/report') : null;
  state.selected=null;state.filter=state.report?.summary.unresolved_items ? 'review' : 'matched';state.query='';state.showAllItems=false;
  state.view = 'workspace';
  render();
}

document.addEventListener('click', async event => {
  const close = event.target.closest('[data-close]');
  if (close) {closeDialog(close.closest('dialog'));return;}
  const navigation = event.target.closest('[data-view]');
  if (navigation) {state.view = navigation.dataset.view;render();return;}
  const run = event.target.closest('[data-run]');
  if (run) {try {await openRun(run.dataset.run);} catch(error) {toast(error.message,true);}return;}
  const action = event.target.closest('[data-action]')?.dataset.action;
  if (action === 'guide') showDialog('#guide-dialog');
  if (action === 'new') showNewRun();
  if (action==='find-item') {$('#review-find').hidden=!$('#review-find').hidden;if (!$('#review-find').hidden) $('#ledger-search').focus();}
  if (action==='more-results') {state.showAllItems=!state.showAllItems;updateLedger();$('[data-action="more-results"]')?.focus();}
  if (action === 'inspector' && state.run) inspectRun(state.run);
  if (action === 'exports' && state.run?.report_available) exportRun(state.run);
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
    dialog.innerHTML = `<div class="modal-top"><span class="eyebrow">NEW RECONCILIATION</span><button class="icon-button" data-close aria-label="Close file import">${icon('close')}</button></div><h2 id="upload-title">Bring both sides of the story.</h2><p class="muted">Compare a payment export with your bank deposits. Your originals stay unchanged.</p><div class="upload-grid">${['payments','bank'].map((kind,index) => `<div><label class="field-label" for="${kind}-file"><span>0${index+1}</span>${kind === 'payments' ? 'Payment activity' : 'Bank deposits'}</label><div class="dropzone" data-kind="${kind}"><input id="${kind}-file" type="file" accept=".csv,text/csv" aria-describedby="${kind}-hint"><span class="upload-icon">${icon(kind === 'payments' ? 'file' : 'bank')}</span><strong id="${kind}-name">Choose a CSV file</strong><small id="${kind}-hint">or drop it here · up to 256 KB</small><span class="choose-file">Browse files ${icon('arrow')}</span></div></div>`).join('')}</div><div class="sample-row"><div>${icon('layers')}<span>Just exploring? <strong>Use synthetic sample files.</strong></span></div><select id="sample-profile" aria-label="Sample file format"><option value="standard">Standard columns</option><option value="renamed">Renamed columns</option></select><button class="button small" id="sample-files">Load samples ${icon('arrow')}</button></div><div id="validation-status" class="validation-status" role="status">Select both files to check their format.</div><details class="format-details"><summary>Supported file format <span>USD · 200 rows per file</span></summary><p>Amounts are decimal dollars. Fees are documented in the payment file; refunds use a positive amount and <code>kind=refund</code>. Shared payout references connect the two files.</p><strong>Payment columns</strong><code>payment_id,payout_id,kind,amount,fee,currency</code><strong>Bank columns</strong><code>deposit_id,payout_id,amount,currency</code><div class="sample-links"><a href="/api/samples/payments" download>Payment sample ↗</a><a href="/api/samples/bank" download>Bank sample ↗</a></div></details><div class="upload-footer"><span>${icon('lock')}Source-checked. No financial writes.</span><button class="button primary" id="start-run" disabled>Reconcile files ${icon('arrow')}</button></div>`;
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
  ++upload.revision;
  upload[kind] = null;
  upload.valid = false;
  $('#start-run').disabled = true;
  $('#' + kind + '-name').textContent = 'Choose a CSV file';
  $('#' + kind + '-hint').textContent = 'or drop it here · up to 256 KB';
  $(`.dropzone[data-kind="${kind}"]`).classList.remove('has-file');
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
    uploadStatus(`${result.payments} payment rows + ${result.bank} bank rows · USD · ${result.profiles.payments === 'renamed' || result.profiles.bank === 'renamed' ? 'renamed headers recognized' : 'standard headers recognized'}`,'valid');
    $('#start-run').disabled = false;
  } catch(error) {if (revision === upload.revision) uploadStatus(error.message,'invalid');}
}

async function loadSamples() {
  $('#sample-files').disabled = true;
  try {
    const kinds = ['payments','bank'];
    const profile = $('#sample-profile')?.value || 'standard';
    const files = await Promise.all(kinds.map(async kind => {const response = await fetch('/api/samples/' + kind + '?profile=' + profile);if (!response.ok) throw new Error('Sample files are unavailable.');return new File([await response.blob()],'sample-' + profile + '-' + kind + '.csv',{type:'text/csv'});}));
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

const stageLabels = {inputs_validated:'Source files validated',generating:'Writing comparison code',creating_sandbox:'Preparing the isolated runtime',sandbox_ready:'CreateOS sandbox ready',executing:'Executing generated Python',revision_needed:'Independent checker requested a revision',checking_replay:'Replaying the checked program',checked:'Report checked against source records',sandbox_deleted:'Sandbox cleanup completed',cleanup_required:'Sandbox cleanup needs attention',failed:'Run stopped',cancelled:'Cancellation accepted',metadata_write_failed:'History could not be saved'};
const activeStatuses = ['running','cancelling'];
function progressView() {return renderFocusedProgress(state.run,stageLabels);}

function pollRun(runId) {
  clearTimeout(state.poll);
  state.activeRunId = runId;
  let failures = 0;
  const tick = async () => {
    try {
      const run = await api('/runs/' + encodeURIComponent(runId));
      failures = 0;
      if (state.run?.run_id === runId) {
        const signature=JSON.stringify([run.status,run.events?.length,run.events?.at(-1)?.stage]);
        const changed=signature!==state.progressSignature;state.progressSignature=signature;
        state.run=run;
        if (run.report_available) state.report = await api('/runs/' + encodeURIComponent(runId) + '/report');
        if(state.view==='workspace'&&changed) {if(run.report_available) state.filter=run.summary?.unresolved_items ? 'review' : 'matched';render();}
      }
      if (!activeStatuses.includes(run.status)) {
        state.activeRunId = null;
        await loadHistory();
        if (state.view === 'history') render();
        toast(run.status === 'checked' ? 'Reconciliation checked. Your evidence report is ready.' : run.status === 'cancelled' ? 'Run cancelled.' : 'Run stopped. Review its execution evidence.',run.status === 'failed');
        return;
      }
    } catch(error) {if (++failures === 3) toast('Connection interrupted. The server may still be working; reconnecting…',true);}
    state.poll = setTimeout(tick,1500);
  };
  tick();
}

async function cancelRun() {
  if (!state.run) return;
  try {
    await api('/runs/'+encodeURIComponent(state.run.run_id)+'/cancel',{method:'POST',body:'{}',headers:{'Content-Type':'application/json'}});
    state.run.status = 'cancelling';render();
  } catch(error) {toast(error.message,true);}
}

document.addEventListener('click',event => {if (event.target.closest('[data-action="cancel"]')) cancelRun();});

document.addEventListener('keydown', event => {
  if (event.key.toLowerCase() === 'n' && !event.ctrlKey && !event.metaKey && !event.altKey && !event.target.closest('input,textarea,select,dialog')) {event.preventDefault();showNewRun();}
});

async function init() {
  hydrateIcons();
  try {
    const health=await api('/health');
    configureHosting(health);
    $('#server-dot').classList.add('online');
    $('#server-label').textContent = 'Workspace connected';
    await loadHistory();
    const active = state.runs.find(run => activeStatuses.includes(run.status));
    const latest = active || state.runs.find(run => run.report_available);
    if (latest) {await openRun(latest.run_id);if (active) pollRun(active.run_id);} else render();
  } catch(error) {render();toast(error.message,true);$('#server-label').textContent = 'Connection unavailable';}
}
init();

function reportItems() {
  const report = state.report;
  if (!report) return [];
  const items = report.groups.map((group,index) => ({...group,key:'g-'+index,label:group.payout_id}));
  for (const kind of ['payment','bank']) {
    for (const row of report[kind === 'payment' ? 'unassigned_payment_rows' : 'unassigned_bank_rows']) {
      const payment = kind === 'payment';
      items.push({key:row.row_id,label:row.row_id,payout_id:'',status:'unreferenced',gross_minor:payment ? row.gross_minor : 0,
        fee_minor:row.fee_minor,expected_minor:payment ? row.net_minor : 0,bank_minor:payment ? 0 : row.net_minor,
        difference_minor:payment ? -row.net_minor : row.net_minor,payment_rows:payment ? [row.row_id] : [],
        bank_rows:payment ? [] : [row.row_id],evidence:{payments:payment ? [row] : [],bank:payment ? [] : [row]}});
    }
  }
  const priority = {discrepancy:0,missing_deposit:1,ambiguous:2,unmatched_deposit:3,unreferenced:4,matched:5};
  return items.sort((a,b) => priority[a.status] - priority[b.status] || a.label.localeCompare(b.label));
}

function reportView() {return renderReview(state,reportItems(),filteredItems());}

function filteredItems() {
  const query = state.query.toLowerCase();
  return reportItems().filter(item => (state.filter === 'all' || (state.filter === 'matched' ? item.status === 'matched' : item.status !== 'matched')) &&
    (!query || JSON.stringify([item.label,item.status,item.payment_rows,item.bank_rows,item.evidence,money(item.expected_minor),money(item.bank_minor)]).toLowerCase().includes(query)));
}

function ledgerRows() {return renderReviewItems(filteredItems(),{expanded:state.showAllItems||!!state.query});}

function openDetail(key) {
  const item=reportItems().find(item=>item.key===key);
  if (!item) return;
  state.selected=key;
  let dialog=$('#detail-dialog');
  if (!dialog) {dialog=document.createElement('dialog');dialog.id='detail-dialog';dialog.className='modal detail-drawer';dialog.setAttribute('aria-labelledby','detail-title');document.body.append(dialog);}
  dialog.innerHTML=renderReviewDetail(item);
  showDialog(dialog);
  dialog.scrollTop=0;
}




function updateLedger(animate=true) {
  $('#ledger-body').innerHTML=ledgerRows();
  $$('[data-filter]').forEach(button=>{button.classList.toggle('active',button.dataset.filter===state.filter);button.setAttribute('aria-selected',String(button.dataset.filter===state.filter));});
  if (animate) enterList($('#ledger-body'));
  const tab=$(`[data-filter="${state.filter}"]`);
  if (tab) moveFilter(tab);
}


document.addEventListener('click',event => {
  const selected = event.target.closest('[data-select]');
  if (selected) {openDetail(selected.dataset.select);}
  const filter = event.target.closest('[data-filter]');
  if (filter) {state.filter=filter.dataset.filter;state.showAllItems=false;updateLedger();}
  if (event.target.closest('[data-action="reset-filter"]')) {state.query='';$('#ledger-search').value='';updateLedger();}
});
document.addEventListener('input',event => {if (event.target.id === 'ledger-search') {state.query=event.target.value;updateLedger(false);}});
document.addEventListener('keydown',event => {
  if (event.key === '/' && !event.target.closest('input,textarea,select,dialog') && $('#ledger-search')) {event.preventDefault();$('#review-find').hidden=false;$('#ledger-search').focus();}
  const row = event.target.closest('[data-select]');
  if (row && ['ArrowDown','ArrowUp'].includes(event.key)) {
    event.preventDefault();const rows=$$('[data-select]',$('#ledger-body')),index=rows.indexOf(row);
    rows[Math.max(0,Math.min(rows.length-1,index+(event.key==='ArrowDown' ? 1 : -1)))]?.focus();
  }
  const tab=event.target.closest('[data-filter]');
  if (tab&&['ArrowLeft','ArrowRight'].includes(event.key)) {
    event.preventDefault();const tabs=$$('[data-filter]'), index=tabs.indexOf(tab);
    const next=tabs[(index+(event.key==='ArrowRight' ? 1 : -1)+tabs.length)%tabs.length];next.click();next.focus();
  }
});

document.addEventListener('toggle',event=>{if(event.target.matches('details')) animateDisclosure(event.target);},true);
