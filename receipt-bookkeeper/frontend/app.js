/** @type {Array<Object>} In-memory store of all parsed receipt rows */
let allRows = [];

const dropZone     = document.getElementById('drop-zone');
const fileInput    = document.getElementById('file-input');
const spinner      = document.getElementById('spinner');
const spinnerText  = document.getElementById('spinner-text');
const errorMsg     = document.getElementById('error-msg');
const resultsSection = document.getElementById('results-section');
const resultsBody  = document.getElementById('results-body');
const rowCount     = document.getElementById('row-count');

// ── Drag-and-drop ──────────────────────────────────────────────
dropZone.addEventListener('dragover', e => {
  e.preventDefault();
  dropZone.classList.add('drag-over');
});
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
dropZone.addEventListener('drop', e => {
  e.preventDefault();
  dropZone.classList.remove('drag-over');
  handleFiles([...e.dataTransfer.files]);
});
dropZone.addEventListener('keydown', e => {
  if (e.key === 'Enter' || e.key === ' ') fileInput.click();
});
fileInput.addEventListener('change', () => handleFiles([...fileInput.files]));

document.getElementById('add-more-btn').addEventListener('click', () => fileInput.click());
document.getElementById('export-xlsx-btn').addEventListener('click', () => exportRows('xlsx'));
document.getElementById('export-csv-btn').addEventListener('click', () => exportRows('csv'));

// ── File handling ──────────────────────────────────────────────
const ALLOWED = new Set(['image/jpeg', 'image/png', 'application/pdf']);

async function handleFiles(files) {
  const valid = files.filter(f => ALLOWED.has(f.type));
  if (!valid.length) {
    showError('請選擇 JPG、PNG 或 PDF 檔案。');
    return;
  }
  hideError();
  showSpinner(`正在處理 ${valid.length} 個收據…`);

  const fd = new FormData();
  valid.forEach(f => fd.append('files', f));

  try {
    const res = await fetch('/api/receipts/upload', { method: 'POST', body: fd });
    if (!res.ok) {
      const detail = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(detail.detail || res.statusText);
    }
    const rows = await res.json();
    rows.forEach(r => allRows.push(r));
    renderTable();
    resultsSection.classList.add('visible');
  } catch (err) {
    showError(`上傳失敗：${err.message}`);
  } finally {
    hideSpinner();
    fileInput.value = '';
  }
}

// ── Table rendering ────────────────────────────────────────────
function categoryBadgeClass(cat) {
  if (cat === 'Meals & Entertainment') return 'badge-meals';
  if (cat === 'Office Supplies')       return 'badge-office';
  if (cat === 'Travel & Transport')    return 'badge-travel';
  if (cat === 'Utilities & Software')  return 'badge-utilities';
  return 'badge-unknown';
}

function renderTable() {
  resultsBody.innerHTML = '';
  allRows.forEach((row, idx) => {
    const tr = document.createElement('tr');
    if (row.category === 'Unclassified') tr.classList.add('unclassified');

    const cells = [
      { key: 'date',        value: row.date || '' },
      { key: 'category',    value: row.category,   badge: true },
      { key: 'description', value: row.description || '' },
      { key: 'vendor',      value: row.vendor || '' },
      { key: 'gst',         value: fmtMoney(row.gst),         money: true },
      { key: 'total',       value: fmtMoney(row.total),       money: true },
      { key: 'base_amount', value: fmtMoney(row.base_amount), money: true },
    ];

    cells.forEach(({ key, value, badge, money }) => {
      const td = document.createElement('td');
      if (badge) {
        td.innerHTML = `<span class="category-badge ${categoryBadgeClass(value)}">${esc(value)}</span>`;
        td.contentEditable = 'true';
        td.dataset.key = key;
        td.dataset.idx = idx;
      } else {
        td.textContent = value;
        td.contentEditable = 'true';
        td.dataset.key = key;
        td.dataset.idx = idx;
        if (money) td.style.textAlign = 'right';
      }
      td.addEventListener('blur', onCellEdit);
      tr.appendChild(td);
    });

    resultsBody.appendChild(tr);
  });
  rowCount.textContent = `(${allRows.length} 筆)`;
}

function onCellEdit(e) {
  const td = e.currentTarget;
  const idx = parseInt(td.dataset.idx, 10);
  const key = td.dataset.key;
  let value = td.textContent.trim();

  if (key === 'gst' || key === 'total' || key === 'base_amount') {
    value = value.replace(/[$,]/g, '');
    const num = parseFloat(value);
    allRows[idx][key] = isNaN(num) ? null : num;
    td.textContent = fmtMoney(allRows[idx][key]);
  } else {
    allRows[idx][key] = value;
  }

  // Re-apply unclassified highlight
  const tr = td.parentElement;
  if (allRows[idx].category === 'Unclassified') {
    tr.classList.add('unclassified');
  } else {
    tr.classList.remove('unclassified');
    if (key === 'category') {
      const badge = td.querySelector('.category-badge') || td;
      badge.className = `category-badge ${categoryBadgeClass(value)}`;
      badge.textContent = value;
    }
  }
}

// ── Export ─────────────────────────────────────────────────────
async function exportRows(format) {
  const rows = readTableToRows();
  try {
    const res = await fetch(`/api/receipts/export/${format}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(rows),
    });
    if (!res.ok) throw new Error(res.statusText);
    const blob = await res.blob();
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href = url;
    a.download = `receipts.${format === 'xlsx' ? 'xlsx' : 'csv'}`;
    a.click();
    URL.revokeObjectURL(url);
  } catch (err) {
    showError(`匯出失敗：${err.message}`);
  }
}

function readTableToRows() {
  const rows = [];
  resultsBody.querySelectorAll('tr').forEach((tr, idx) => {
    rows.push({ ...allRows[idx] });
  });
  return rows;
}

// ── Helpers ─────────────────────────────────────────────────────
function fmtMoney(value) {
  if (value === null || value === undefined || value === '') return '';
  const num = typeof value === 'string' ? parseFloat(value) : value;
  return isNaN(num) ? '' : `$${num.toFixed(2)}`;
}

function esc(str) {
  return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function showSpinner(msg) {
  spinnerText.textContent = msg;
  spinner.classList.add('visible');
}
function hideSpinner() { spinner.classList.remove('visible'); }
function showError(msg) { errorMsg.textContent = msg; errorMsg.classList.add('visible'); }
function hideError()    { errorMsg.classList.remove('visible'); }
