// ── State ────────────────────────────────────────────────────────────────────
let uploadedFiles = [];   // {name, size, path}
let pollingTimer = null;
let lastResults = null;

// ── File Handling ─────────────────────────────────────────────────────────────
const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');

dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('drag-over'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
dropZone.addEventListener('drop', e => {
  e.preventDefault(); dropZone.classList.remove('drag-over');
  handleFiles([...e.dataTransfer.files]);
});
fileInput.addEventListener('change', () => handleFiles([...fileInput.files]));

async function handleFiles(files) {
  const form = new FormData();
  files.forEach(f => form.append('files', f));
  try {
    const res = await fetch('/upload', { method: 'POST', body: form });
    const data = await res.json();
    files.forEach((f, i) => {
      if (!uploadedFiles.find(u => u.name === f.name))
        uploadedFiles.push({ name: f.name, size: f.size, path: data.paths[i] });
    });
    renderFileList();
    toast(`✓ ${files.length} file(s) added`, 'ok');
  } catch(e) {
    toast('Upload failed: ' + e.message, 'err');
  }
}

function renderFileList() {
  const list = document.getElementById('fileList');
  list.innerHTML = '';
  uploadedFiles.forEach((f, i) => {
    const ext = f.name.split('.').pop().toLowerCase();
    const badgeClass = { csv:'badge-csv', xlsx:'badge-xlsx', xls:'badge-xlsx', tsv:'badge-tsv', txt:'badge-txt' }[ext] || 'badge-txt';
    const div = document.createElement('div');
    div.className = 'file-item';
    div.innerHTML = `<span class="file-badge ${badgeClass}">${ext}</span><span class="fname">${f.name}</span><span class="fsize">${fmtSize(f.size)}</span><button class="rm" onclick="removeFile(${i})">✕</button>`;
    list.appendChild(div);
  });
  document.getElementById('runBtn').disabled = uploadedFiles.length === 0;
}

function removeFile(i) {
  uploadedFiles.splice(i, 1);
  renderFileList();
}

function fmtSize(bytes) {
  if (bytes < 1024) return bytes + 'B';
  if (bytes < 1024*1024) return (bytes/1024).toFixed(1) + 'KB';
  return (bytes/1024/1024).toFixed(1) + 'MB';
}

// ── Param helpers ─────────────────────────────────────────────────────────────
document.getElementById('pFillNa').addEventListener('change', function() {
  document.getElementById('fillValRow').style.display = this.checked ? 'flex' : 'none';
  if (this.checked) document.getElementById('pDropNa').checked = false;
});
document.getElementById('pDropNa').addEventListener('change', function() {
  if (this.checked) document.getElementById('pFillNa').checked = false;
  document.getElementById('fillValRow').style.display = 'none';
});

function collectParams() {
  return {
    delimiter: document.getElementById('pDelimiter').value,
    encoding: document.getElementById('pEncoding').value,
    decimal: document.getElementById('pDecimal').value,
    skip_rows: document.getElementById('pSkipRows').value || '0',
    thousands: document.getElementById('pThousands').value,
    drop_duplicates: document.getElementById('pDropDup').checked,
    drop_na: document.getElementById('pDropNa').checked,
    fill_na: document.getElementById('pFillNa').checked,
    fill_value: document.getElementById('pFillVal').value,
    normalize: document.getElementById('pNormalize').checked,
  };
}

// ── Run pipeline ──────────────────────────────────────────────────────────────
document.getElementById('runBtn').addEventListener('click', async () => {
  if (uploadedFiles.length === 0) return;
  clearResults(true);

  const form = new FormData();
  form.append('files', JSON.stringify(uploadedFiles.map(f => f.path)));
  form.append('params', JSON.stringify(collectParams()));

  try {
    await fetch('/run', { method: 'POST', body: form });
    startPolling();
  } catch(e) {
    toast('Could not start pipeline: ' + e.message, 'err');
  }
});

// ── Polling ───────────────────────────────────────────────────────────────────
function startPolling() {
  document.getElementById('progressWrap').classList.add('visible');
  document.getElementById('runBtn').disabled = true;
  setStatus('running');
  if (pollingTimer) clearInterval(pollingTimer);
  pollingTimer = setInterval(pollStatus, 700);
}

async function pollStatus() {
  const s = await (await fetch('/status')).json();

  // Update progress
  document.getElementById('progressBar').style.width = s.progress + '%';
  document.getElementById('progressPct').textContent = s.progress + '%';
  document.getElementById('progressStatus').textContent = s.status;
  setStatus(s.status);

  // Update log
  const logBox = document.getElementById('logBox');
  logBox.innerHTML = s.log.map(line => {
    let cls = 'log-line-info';
    if (line.includes('✓')) cls = 'log-line-ok';
    if (line.includes('✗') || line.includes('Error')) cls = 'log-line-err';
    return `<div class="${cls}">${escHtml(line)}</div>`;
  }).join('');
  logBox.scrollTop = logBox.scrollHeight;

  if (s.status === 'done') {
    clearInterval(pollingTimer);
    document.getElementById('runBtn').disabled = false;
    loadResults();
    toast('✅ Pipeline complete!', 'ok');
  } else if (s.status === 'error') {
    clearInterval(pollingTimer);
    document.getElementById('runBtn').disabled = false;
    toast('✗ Error: ' + s.error, 'err');
  }
}

async function loadResults() {
  try{
      const data = await (await fetch('/results')).json()
      
      lastResults = data;
      renderCharts(data.charts);
      renderTables(data.dataframes);
      document.getElementById('emptyState').style.display = 'none';
      document.getElementById('tabs').style.display = 'flex';
      document.getElementById('tab-charts').style.display = 'block';
      document.getElementById('tab-tables').style.display = 'none';
      document.getElementById('exportBtn').style.display = '';
      document.getElementById('clearBtn').style.display = '';
  }catch(s){
    toast('✗ Error: ' + s.error, 'err');
  }

}

// ── Render charts ─────────────────────────────────────────────────────────────
function renderCharts(charts) {
  const grid = document.getElementById('chartsGrid');
  grid.innerHTML = '';
  charts.forEach(c => {
    const card = document.createElement('div');
    card.className = 'chart-card';
    card.innerHTML = `
      <div class="chart-card-header">
        <span>${escHtml(c.title)}</span>
        <button class="btn btn-sm" onclick="downloadImg(this, '${escHtml(c.title)}')">⬇</button>
      </div>
      <img src="data:image/png;base64,${c.img}" alt="${escHtml(c.title)}" loading="lazy">`;
    grid.appendChild(card);
    card.querySelector('img')._b64 = c.img;
  });
}

function downloadImg(btn, title) {
  const img = btn.closest('.chart-card').querySelector('img');
  const a = document.createElement('a');
  a.href = 'data:image/png;base64,' + img._b64;
  a.download = title.replace(/[^a-z0-9]/gi, '_') + '.png';
  a.click();
}

// ── Render tables ─────────────────────────────────────────────────────────────
function renderTables(dfs) {
  const container = document.getElementById('tablesContainer');
  container.innerHTML = '';
  dfs.forEach(df => {
    const section = document.createElement('div');
    section.className = 'df-section';
    const cols = df.describe.length > 0 ? Object.keys(df.describe[0]) : [];
    const rows = df.describe.map(row =>
      `<tr>${cols.map(c => `<td>${row[c] !== null && row[c] !== undefined ? escHtml(String(row[c])) : '<span style="color:var(--muted)">—</span>'}</td>`).join('')}</tr>`
    ).join('');
    section.innerHTML = `
      <div class="df-name">📄 ${escHtml(df.name)}</div>
      <div class="df-meta">
        <span>🔢 ${df.shape[0]} rows × ${df.shape[1]} cols</span>
        <span>📋 ${df.columns.length} columns</span>
      </div>
      <div class="table-wrap">
        <table>
          <thead><tr>${cols.map(c => `<th>${escHtml(String(c))}</th>`).join('')}</tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>`;
    container.appendChild(section);
  });
}

// ── Tabs ──────────────────────────────────────────────────────────────────────
document.getElementById('tabs').addEventListener('click', e => {
  const tab = e.target.closest('.tab');
  if (!tab) return;
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  tab.classList.add('active');
  const target = tab.dataset.tab;
  document.getElementById('tab-charts').style.display = target === 'charts' ? 'block' : 'none';
  document.getElementById('tab-tables').style.display = target === 'tables' ? 'block' : 'none';
});

// ── Helpers ───────────────────────────────────────────────────────────────────
function setStatus(s) {
  const el = document.getElementById('statusBadge');
  const colors = { idle:'var(--muted)', running:'#ffd166', done:'var(--accent3)', error:'var(--accent2)' };
  el.textContent = s;
  el.style.color = colors[s] || 'var(--muted)';
}

function clearLog() { document.getElementById('logBox').innerHTML = ''; }

function clearResults(keepLog=false) {
  document.getElementById('chartsGrid').innerHTML = '';
  document.getElementById('tablesContainer').innerHTML = '';
  document.getElementById('emptyState').style.display = '';
  document.getElementById('tabs').style.display = 'none';
  document.getElementById('tab-charts').style.display = 'none';
  document.getElementById('tab-tables').style.display = 'none';
  document.getElementById('exportBtn').style.display = 'none';
  document.getElementById('clearBtn').style.display = 'none';
  document.getElementById('progressWrap').classList.remove('visible');
  if (!keepLog) clearLog();
}

function exportResults() {
  if (!lastResults) return;
  const out = { charts_count: lastResults.charts.length, dataframes: lastResults.dataframes };
  const blob = new Blob([JSON.stringify(out, null, 2)], { type: 'application/json' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'dataflow_results.json';
  a.click();
}

function escHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

let toastTimer;
function toast(msg, type='ok') {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.className = `toast ${type} show`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove('show'), 3500);
}