import {$, $$, escape, money, date, icon, hydrateIcons, api, toast, showDialog} from './ui.js';
import {inspectRun, exportRun} from './inspector.js';

const state = {view:'workspace', runs:[], run:null, report:null, selected:null, filter:'all', query:'', poll:null};

function render() {
  $$('.nav-item[data-view]').forEach(button => {button.classList.toggle('active',button.dataset.view === state.view);button.setAttribute('aria-current',button.dataset.view === state.view ? 'page' : 'false');});
  $('#breadcrumb-current').textContent = state.view === 'history' ? 'Run history' : 'Reconciliation';
  $('#history-count').textContent = state.runs.length;
  $('#content').innerHTML = state.view === 'history' ? historyView() : workspaceView();
}

function workspaceView() {
  if (state.report) return reportView();
  if (state.run) return progressView();
  return `<div class="page-heading"><div><span class="eyebrow">RECONCILIATION WORKSPACE</span><h1>Your numbers. Their paper trail.</h1><p class="page-description">Bring your payment export and bank deposits together. Follow every difference back to its source.</p></div></div>
  <section class="welcome"><div class="welcome-copy"><span class="pill green">${icon('shield')}Source-checked reconciliation</span><h2>Close the gap.<br>Keep the evidence.</h2><p>An agent writes and runs the comparison. An independent checker verifies the numbers. You see exactly what matches, and what needs another look.</p><button class="button primary" data-action="new">${icon('plus')}Start a reconciliation</button><button class="text-button" data-action="guide">See how it works ${icon('arrow')}</button><div class="welcome-footnote">${icon('lock')}Your files stay in this workspace and its isolated execution sandbox.</div></div><div class="paper-illustration" aria-hidden="true"><div class="paper-shadow"></div><div class="paper-receipt"><div class="receipt-top"><img src="/static/mark.svg" width="23" height="27" alt=""><span>A CLEARER PICTURE</span></div><div class="receipt-line"><i></i><i></i></div><div class="receipt-line"><i></i><i></i></div><div class="receipt-line"><i></i><i></i></div><div class="receipt-total"><span>Every number</span><strong>A source.</strong></div><div class="receipt-seal">${icon('check')}FOLLOW THE PAPER TRAIL</div><div class="receipt-rip"></div></div></div></section><div class="intro-notes"><div><span>01</span><strong>Two files in</strong><p>Payment activity and bank deposits. One currency, clear rules.</p></div><div><span>02</span><strong>Every claim checked</strong><p>Exact amounts, original rows, and a reproducible comparison.</p></div><div><span>03</span><strong>Answers you can inspect</strong><p>Matches, open questions, and the source evidence behind both.</p></div></div>`;
}

function historyView() {
  const status = run => ({checked:'Checked',failed:'Stopped',cancelled:'Cancelled',interrupted:'Interrupted',running:'In progress',cancelling:'Stopping'}[run.status] || run.status);
  return `<div class="page-heading"><div><span class="eyebrow">YOUR WORKSPACE</span><h1>Run history</h1><p class="page-description">A record of your reconciliations, with the work behind each result.</p></div><button class="button" data-action="refresh">${icon('replay')}Refresh</button></div><div class="history-storage-note">${icon(state.database === 'connected' ? 'check' : 'alert')}<span>${state.database === 'connected' ? 'History synced with Neon. Source files and execution artifacts stay on this machine.' : 'Showing local history. The metadata database is currently unavailable.'}</span></div><section class="panel"><div class="panel-heading"><h2>Recent runs</h2><span class="muted">${state.runs.length} runs</span></div>${state.runs.length ? state.runs.map(run => `<button class="history-row" data-run="${escape(run.run_id)}" ${!run.artifacts_available ? 'disabled title="Only metadata is available. The source artifacts are not on this machine."' : ''}><span class="file-tile">${icon('ledger')}</span><span class="history-file-names"><strong>${escape(run.input_names?.payments || 'payments.csv')} <span class="muted">+</span> ${escape(run.input_names?.bank || 'bank.csv')}</strong><small>${date(run.started_at)} <span class="source-plus">·</span> <span class="mono">${escape(run.run_id.slice(-8))}</span>${run.data_kind === 'synthetic_sample' ? '<span class="sample-badge">Synthetic sample</span>' : ''}</small></span><span class="history-difference">${run.summary ? money(run.summary.difference_minor) : '—'}<small>net difference</small></span><span class="pill ${run.status === 'checked' ? 'green' : run.status === 'failed' ? 'amber' : ''}">${escape(status(run))}</span>${!run.artifacts_available ? '<span class="metadata-only">Metadata only</span>' : icon('chevron')}</button>`).join('') : '<div class="empty-state">Your first reconciliation will appear here.<br><button class="text-button" data-action="new">Start a reconciliation '+icon('arrow')+'</button></div>'}</section>`;
}

async function loadHistory() {
  const result = await api('/runs');
  state.runs = result.runs;
  state.database = result.database;
}

async function openRun(runId) {
  state.run = await api('/runs/' + encodeURIComponent(runId));
  state.report = state.run.report_available ? await api('/runs/' + encodeURIComponent(runId) + '/report') : null;
  state.selected = null;state.filter = 'all';state.query = '';
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
function progressView() {
  const run = state.run, active = activeStatuses.includes(run.status), failed = ['failed','interrupted','cancelled'].includes(run.status);
  const latest = run.events?.at(-1), stage = latest?.stage;
  const title = run.status === 'cancelling' ? 'Stopping at a safe checkpoint.' : active ? 'Following the paper trail.' : run.status === 'checked' ? 'The comparison is checked.' : run.status === 'cancelled' ? 'This run was cancelled.' : 'This run needs another look.';
  const subtitle = active ? 'The agent is writing and testing real code. Every accepted result must pass an independent check.' : failed ? 'There is no accepted report for this run. Its execution evidence is preserved.' : 'The generated program and its replay agree with the original sources.';
  const steps = [{label:'Validate sources',events:['inputs_validated']},{label:'Write & execute',events:['generating','creating_sandbox','sandbox_ready','executing','revision_needed']},{label:'Check & replay',events:['checking_replay','checked']},{label:'Save & clean up',events:['sandbox_deleted']}];
  let current = steps.findIndex(s => s.events.includes(stage));
  if (current < 0) current = active ? 1 : failed ? -1 : 3;
  return `<div class="page-heading"><div><span class="eyebrow">${active ? 'RECONCILIATION IN PROGRESS' : 'EXECUTION RECORD'}</span><h1>${title}</h1><p class="page-description">${subtitle}</p></div>${active ? `<button class="button" data-action="cancel" ${run.status === 'cancelling' ? 'disabled' : ''}>${icon('close')}${run.status === 'cancelling' ? 'Cancellation requested' : 'Cancel run'}</button>` : '<button class="button" data-action="new">Try another run</button>'}</div><div class="run-file-line">${icon('file')}<span>${escape(run.input_names?.payments || 'payments.csv')}</span><span class="muted">+</span>${icon('bank')}<span>${escape(run.input_names?.bank || 'bank.csv')}</span><span class="mono">${escape(run.run_id.slice(-8))}</span></div><section class="panel progress-panel"><div class="progress-heading"><span class="${active ? 'spinner' : 'progress-result'}">${active ? '' : icon(failed ? 'alert' : 'check')}</span><div><h2>${active ? escape(stageLabels[stage] || 'Starting the controller') : run.status === 'checked' ? 'Independent checks passed' : escape(run.status)}</h2><p>${run.status === 'cancelling' ? 'The current model or execution request may finish first. The controller then stops and cleans up.' : active ? 'Live controller events · no simulated progress' : escape(run.error || 'The original files and execution record are preserved.')}</p></div><span class="pill ${failed ? 'amber' : 'green'}">${active ? 'Live run' : escape(run.status)}</span></div><div class="run-steps">${steps.map((step,index) => `<div class="run-step ${index < current || (!active && !failed) ? 'complete' : index === current ? 'current' : ''}"><span>${index < current || (!active && !failed) ? icon('check') : '0'+(index+1)}</span><strong>${step.label}</strong></div>`).join('')}</div><div class="event-list" aria-live="polite">${(run.events || []).map(event => `<div class="event-row ${event.stage === 'revision_needed' ? 'revision' : ''}"><span class="event-dot"></span><time>${new Date(event.time).toLocaleTimeString('en-US',{hour12:false})}</time><span>${escape(stageLabels[event.stage] || event.stage)}${event.attempt ? `<small>Attempt ${event.attempt}</small>` : ''}</span>${event.stage === 'revision_needed' ? `<p>${escape(event.reason)}</p>` : ''}</div>`).join('') || '<div class="empty-state">The controller is accepting this run…</div>'}</div></section><div class="run-bottom-note">${icon('lock')}Generated code runs in CreateOS. API keys remain in the trusted controller.</div>`;
}

function pollRun(runId) {
  clearTimeout(state.poll);
  state.activeRunId = runId;
  let failures = 0;
  const tick = async () => {
    try {
      const run = await api('/runs/' + encodeURIComponent(runId));
      failures = 0;
      if (state.run?.run_id === runId) {
        state.run = run;
        if (run.report_available) state.report = await api('/runs/' + encodeURIComponent(runId) + '/report');
        if (state.view === 'workspace') render();
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
    await api('/health');
    $('#server-dot').classList.add('online');
    $('#server-label').textContent = 'Workspace connected';
    await loadHistory();
    const active = state.runs.find(run => activeStatuses.includes(run.status));
    const latest = active || state.runs.find(run => run.report_available);
    if (latest) {await openRun(latest.run_id);if (active) pollRun(active.run_id);} else render();
  } catch(error) {render();toast(error.message,true);$('#server-label').textContent = 'Connection unavailable';}
}
init();

const statusInfo = {
  matched:{label:'Matched',tone:'green'},discrepancy:{label:'Difference',tone:'red'},
  missing_deposit:{label:'Not deposited',tone:'amber'},ambiguous:{label:'Ambiguous',tone:'amber'},
  unmatched_deposit:{label:'Bank only',tone:''},unreferenced:{label:'No reference',tone:''}
};
const badge = status => `<span class="pill ${statusInfo[status]?.tone || ''}"><span class="badge-dot"></span>${escape(statusInfo[status]?.label || status)}</span>`;

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

function reportView() {
  const run = state.run, summary = state.report.summary, items = reportItems();
  if (!items.some(item => item.key === state.selected)) state.selected = items[0]?.key;
  const total = summary.payment_records + summary.bank_records;
  return `<div class="page-heading report-heading"><div><span class="eyebrow">RECONCILIATION REPORT <span class="eyebrow-divider">/</span> ${escape(run.run_id.slice(-8).toUpperCase())}${run.data_kind === 'synthetic_sample' ? '<span class="sample-badge">Synthetic sample</span>' : ''}</span><div class="heading-title"><h1>Every payout, accounted for.</h1><span class="pill green">${icon('shield')}Source checks passed</span></div><p class="page-description">${escape(run.input_names?.payments || 'payments.csv')}<span class="source-plus">+</span>${escape(run.input_names?.bank || 'bank.csv')}<span class="source-plus">·</span>${date(run.started_at)}</p></div><button class="button" data-action="exports">${icon('download')}Export report ${icon('down')}</button></div>
  <section class="summary-grid" aria-label="Reconciliation totals"><article class="summary-card"><div class="summary-label">Expected net payouts ${icon('ledger')}</div><div class="summary-number">${money(summary.expected_minor)}</div><p>After ${money(summary.fee_minor)} in documented fees</p></article><article class="summary-card"><div class="summary-label">Bank deposits ${icon('bank')}</div><div class="summary-number">${money(summary.bank_minor)}</div><p>${summary.bank_records} source records · USD</p></article><article class="summary-card difference-card"><div class="summary-label">Net difference <span class="pill amber">${summary.unresolved_items} to review</span></div><div class="summary-number ${summary.difference_minor === 0 ? '' : 'difference-number'}">${money(summary.difference_minor)}</div><p>${summary.unresolved_items ? 'An investigation starting point, not proven loss' : 'Both files balance under the supported rules'}</p></article></section>
  <div class="proof-strip"><span>${icon('shield')}<strong>${total}/${total} source rows accounted for</strong></span><span>${icon('check')}Exact amounts</span><span>${icon('check')}References checked</span><span>${icon(run.replay_verified ? 'replay' : 'clock')}${run.replay_verified ? 'Replay verified' : 'Replay not verified'}</span><button class="text-button" data-action="inspector">View execution ${icon('arrow')}</button></div>
  <div class="report-toolbar"><div class="report-tabs"><button class="active" data-action="ledger-tab">Reconciliation</button><button data-action="inspector">Execution evidence ${icon('code')}</button></div><span class="report-count">${summary.payment_records} payment rows <span>↔</span> ${summary.bank_records} bank rows</span></div>
  <div class="investigation-grid"><section class="panel ledger-panel" aria-label="Settlement ledger"><div class="ledger-heading"><div><h2>Settlement ledger</h2><p>Follow a payout to its original records.</p></div><span class="ledger-group-count">${state.report.groups.length} payout groups</span></div><div class="ledger-filters"><div class="filter-tabs">${[['all','All',items.length],['review','Needs review',items.filter(i => i.status !== 'matched').length],['matched','Matched',items.filter(i => i.status === 'matched').length]].map(([key,label,count]) => `<button data-filter="${key}" class="${state.filter === key ? 'active' : ''}">${label}<span>${count}</span></button>`).join('')}</div><label class="search-box">${icon('search')}<input id="ledger-search" type="search" placeholder="Find a payout or source row…" value="${escape(state.query)}" aria-label="Search payouts or source rows"><kbd>/</kbd></label></div><div class="ledger-scroll"><div class="ledger-columns" aria-hidden="true"><span>Payout reference</span><span>Status</span><span>Expected</span><span>Received</span><span>Difference</span><span></span></div><div id="ledger-body">${ledgerRows()}</div></div><div class="ledger-footnote">${icon('lock')}Matched by shared payout reference. Amounts alone never establish a match.</div></section><aside id="evidence-panel" class="panel evidence-panel" aria-label="Selected payout evidence">${evidenceView()}</aside></div>
  <div class="interpretation-note">${icon('help')}<p>Open items need a closer look. Timing, missing exports, or split deposits can explain differences. Originals are never adjusted to force a match.</p></div>`;
}

function filteredItems() {
  const query = state.query.toLowerCase();
  return reportItems().filter(item => (state.filter === 'all' || (state.filter === 'matched' ? item.status === 'matched' : item.status !== 'matched')) &&
    (!query || JSON.stringify([item.label,item.status,item.payment_rows,item.bank_rows,item.evidence,money(item.expected_minor),money(item.bank_minor)]).toLowerCase().includes(query)));
}

function ledgerRows() {
  const items = filteredItems();
  return items.map(item => `<button class="ledger-row ${item.key === state.selected ? 'selected' : ''}" data-select="${escape(item.key)}" aria-pressed="${item.key === state.selected}"><span class="payout-name" title="${escape(item.label)}"><strong>${escape(item.label)}</strong><small>${item.status === 'unreferenced' ? 'No payout reference' : item.payment_rows.length + ' payment ' + (item.payment_rows.length === 1 ? 'row' : 'rows') + ' · ' + item.bank_rows.length + ' bank'}</small></span><span>${badge(item.status)}</span><span class="amount">${money(item.expected_minor)}</span><span class="amount">${item.bank_rows.length ? money(item.bank_minor) : '—'}</span><span class="amount ${item.status !== 'matched' && item.difference_minor !== 0 ? 'amount-review' : item.status === 'matched' ? 'amount-matched' : ''}">${money(item.difference_minor)}</span>${icon('chevron')}</button>`).join('') || `<div class="empty-state">No records match this view.<br><button class="text-button" data-action="reset-filter">Clear filters ${icon('arrow')}</button></div>`;
}

function evidenceView() {
  const item = reportItems().find(item => item.key === state.selected);
  if (!item) return '<div class="empty-state">Choose a payout to inspect its evidence.</div>';
  const explanation = {
    matched:['The payout matches.','The referenced bank record equals the net amount supported by the payment rows.'],
    discrepancy:['A difference to investigate.',`The referenced bank record is ${money(Math.abs(item.difference_minor))} ${item.difference_minor < 0 ? 'below' : 'above'} the expected net amount. No extra adjustments were assumed.`],
    missing_deposit:['No bank record in this export.','The payment activity has a payout reference, but the bank file has no corresponding record. Check settlement timing and export completeness.'],
    ambiguous:['Several records. One reference.','Multiple bank records carry this payout reference. Split deposits are unsupported, so the group stays ambiguous even if its total balances.'],
    unmatched_deposit:['A deposit without payment evidence.','This reference appears only in the bank file. Check whether the payment export is complete and uses the same references.'],
    unreferenced:['This row needs a payout reference.','Equal amounts are not enough to connect records. This row remains unassigned until a supported reference is available.']
  }[item.status];
  return `<div class="evidence-heading"><span class="eyebrow">SOURCE EVIDENCE</span><h2>${escape(item.label)}</h2>${badge(item.status)}</div><div class="evidence-reason ${item.status === 'matched' ? 'reason-matched' : ''}"><span class="reason-symbol">${icon(item.status === 'matched' ? 'check' : 'search')}</span><div><strong>${explanation[0]}</strong><p>${escape(explanation[1])}</p></div></div><div class="evidence-calculation"><div><span>Payment activity <small>charges less refunds</small></span><strong>${money(item.gross_minor)}</strong></div><div><span>Documented fees</span><strong>${item.fee_minor ? '−' : ''}${money(item.fee_minor)}</strong></div><div class="expected-total"><span>Expected net payout</span><strong>${money(item.expected_minor)}</strong></div><div><span>Bank deposits <small>${item.bank_rows.length} referenced ${item.bank_rows.length === 1 ? 'record' : 'records'}</small></span><strong>${item.bank_rows.length ? money(item.bank_minor) : '—'}</strong></div><div class="calculation-total ${item.status === 'matched' ? 'matched-total' : ''}"><span>${item.status === 'matched' ? 'Difference · balanced' : 'Difference · investigate'}</span><strong>${money(item.difference_minor)}</strong></div></div><div class="source-evidence"><div class="source-section-title"><span>${icon('file')}Payment records</span><span>${item.evidence.payments.length}</span></div>${item.evidence.payments.length ? item.evidence.payments.map(row => sourceRecord(row,'payments')).join('') : '<p class="no-source">No payment rows carry this reference.</p>'}<div class="source-section-title bank-source-title"><span>${icon('bank')}Bank records</span><span>${item.evidence.bank.length}</span></div>${item.evidence.bank.length ? item.evidence.bank.map(row => sourceRecord(row,'bank')).join('') : '<p class="no-source">No bank row carries this reference.</p>'}</div><div class="evidence-footer">${icon('lock')}Original source values. Expand a record to inspect every field.</div>`;
}

function sourceRecord(row, kind) {
  const source = row.source;
  const identity = source.payment_id || source.transaction_reference || source.deposit_id || source.bank_transaction_id || row.row_id;
  const label = kind === 'payments' ? 'net' : 'deposit';
  return `<details class="source-record"><summary><span class="source-row-id">${escape(row.row_id)}</span><span class="source-identity"><strong title="${escape(identity)}">${escape(identity)}</strong><small>CSV record ${row.record}</small></span><span class="source-amount">${money(row.net_minor)}<small>${label}</small></span>${icon('down')}</summary><div class="raw-record">${Object.entries(source).map(([key,value]) => `<div><span>${escape(key)}</span><code>${escape(value) || '<i>empty</i>'}</code></div>`).join('')}</div></details>`;
}

function updateLedger() {
  const visible = filteredItems();
  if (!visible.some(item => item.key === state.selected)) state.selected = visible[0]?.key || null;
  $('#ledger-body').innerHTML = ledgerRows();
  $('#evidence-panel').innerHTML = evidenceView();
  $$('[data-filter]').forEach(button => button.classList.toggle('active',button.dataset.filter === state.filter));
}

document.addEventListener('click',event => {
  const selected = event.target.closest('[data-select]');
  if (selected) {state.selected = selected.dataset.select;updateLedger();}
  const filter = event.target.closest('[data-filter]');
  if (filter) {state.filter = filter.dataset.filter;updateLedger();}
  if (event.target.closest('[data-action="reset-filter"]')) {state.filter = 'all';state.query = '';$('#ledger-search').value = '';updateLedger();}
});
document.addEventListener('input',event => {if (event.target.id === 'ledger-search') {state.query = event.target.value;updateLedger();}});
document.addEventListener('keydown',event => {
  if (event.key === '/' && !event.target.closest('input,textarea,select,dialog') && $('#ledger-search')) {event.preventDefault();$('#ledger-search').focus();}
  const row = event.target.closest('[data-select]');
  if (row && ['ArrowDown','ArrowUp'].includes(event.key)) {
    event.preventDefault();const items = filteredItems();const index = items.findIndex(item => item.key === row.dataset.select);
    state.selected = items[Math.max(0,Math.min(items.length-1,index+(event.key === 'ArrowDown' ? 1 : -1)))]?.key;
    updateLedger();$(`[data-select="${state.selected}"]`)?.focus();
  }
});
