/* ════════════════════════════════════════════════════
   AUTO LEAD BERGAMO — Dashboard App
   ════════════════════════════════════════════════════ */

const state = {
  stato: '',
  fonte: '',
  brand: '',
  min_score: 0,
  q: '',
  view: 'lista',
};

let _runPollInterval = null;
let _toastTimer = null;

// ── INIT ──────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  // Pipeline nav
  document.querySelectorAll('.nav-item').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.nav-item').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state.stato = btn.dataset.stato;
      loadLeads();
    });
  });

  // Filters
  document.getElementById('filter-fonte').addEventListener('change', e => {
    state.fonte = e.target.value; loadLeads();
  });
  document.getElementById('filter-brand').addEventListener('change', e => {
    state.brand = e.target.value; loadLeads();
  });
  document.getElementById('filter-score').addEventListener('input', e => {
    state.min_score = e.target.value;
    document.getElementById('score-display').textContent = e.target.value;
    loadLeads();
  });

  // Search (debounced)
  let _searchTimer;
  document.getElementById('search-input').addEventListener('input', e => {
    clearTimeout(_searchTimer);
    _searchTimer = setTimeout(() => {
      state.q = e.target.value.trim();
      loadLeads();
    }, 300);
  });

  // View toggle
  document.querySelectorAll('.vt-btn').forEach(btn => {
    btn.addEventListener('click', () => setView(btn.dataset.view));
  });

  // Run pipeline button
  document.getElementById('run-btn').addEventListener('click', runPipeline);

  loadAll();
});

// ── VIEW ──────────────────────────────────────────────
function setView(view) {
  state.view = view;
  document.querySelectorAll('.vt-btn').forEach(b => {
    b.classList.toggle('active', b.dataset.view === view);
  });
  document.getElementById('leads-area').style.display = view === 'lista' ? '' : 'none';
  document.getElementById('map-container').classList.toggle('visible', view === 'mappa');
  if (view === 'mappa') {
    MapModule.init();
    MapModule.render(window._lastLeads || []);
  }
}

// ── STATS ─────────────────────────────────────────────
async function loadStats() {
  const res = await fetch('/api/stats');
  const s   = await res.json();

  setText('stat-totale',     s.totale    ?? '—');
  setText('stat-nuovi',      s.nuovi     ?? '—');
  setText('stat-contattati', s.contattati ?? '—');
  setText('stat-venduti',    s.venduti   ?? '—');
  setText('stat-score',      s.score_medio ? s.score_medio + '/10' : '—');

  setText('cnt-all',          s.totale       ?? '—');
  setText('cnt-nuovo',        s.nuovi        ?? '—');
  setText('cnt-contattato',   s.contattati   ?? '—');
  setText('cnt-risposto',     s.risposti     ?? '—');
  setText('cnt-appuntamento', s.appuntamenti ?? '—');
  setText('cnt-venduto',      s.venduti      ?? '—');

  populateSelect('filter-fonte', s.fonti  || [], 'Tutte le fonti', state.fonte);
  populateSelect('filter-brand', s.brands || [], 'Tutti i brand',  state.brand);
}

function populateSelect(id, items, placeholder, current) {
  const sel = document.getElementById(id);
  sel.innerHTML = `<option value="">${placeholder}</option>`;
  items.forEach(v => {
    const o = document.createElement('option');
    o.value = v; o.textContent = v;
    if (v === current) o.selected = true;
    sel.appendChild(o);
  });
}

// ── LEADS ─────────────────────────────────────────────
async function loadLeads() {
  const grid = document.getElementById('leads-grid');
  grid.innerHTML = '<div class="loading-state"><div class="loading-dots"><span></span><span></span><span></span></div></div>';

  const p = new URLSearchParams();
  if (state.stato)         p.set('stato', state.stato);
  if (state.fonte)         p.set('fonte', state.fonte);
  if (state.brand)         p.set('brand', state.brand);
  if (+state.min_score > 0) p.set('min_score', state.min_score);
  if (state.q)             p.set('q', state.q);

  const res   = await fetch('/api/leads?' + p);
  const leads = await res.json();

  setText('results-count', leads.length + (leads.length === 1 ? ' lead' : ' lead'));

  if (!leads.length) {
    grid.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">🔍</div>
        <div class="empty-title">Nessun lead trovato</div>
        <div class="empty-sub">Allarga i filtri o avvia lo scraping.</div>
      </div>`;
    return;
  }

  grid.innerHTML = leads.map(renderCard).join('');
  window._lastLeads = leads;
  if (state.view === 'mappa') MapModule.render(leads);
}

// ── RENDER CARD ───────────────────────────────────────
function renderCard(l) {
  const score      = l.ai_score || 0;
  const scoreClass = score >= 7 ? 'score-high' : score >= 5 ? 'score-mid' : score > 0 ? 'score-low' : 'score-zero';
  const stripClass = { ALTA: 'strip-alta', MEDIA: 'strip-media', BASSA: 'strip-bassa' }[l.ai_urgenza] || 'strip-none';

  const price = l.price_raw
    || (l.budget          ? '€' + l.budget.toLocaleString('it-IT')               : '')
    || (l.ai_budget_stimato ? '~€' + Number(l.ai_budget_stimato).toLocaleString('it-IT') : '—');

  const specs = [
    l.brand && l.year ? `${l.brand} ${l.year}`              : '',
    l.km              ? l.km.toLocaleString('it-IT') + ' km' : '',
  ].filter(Boolean);

  const zonaLabel = {
    industriale:  'Industriale',
    residenziale: 'Residenziale',
    pendolare:    'Pendolare',
    montagna:     'Montagna',
  }[l.zona_tipo] || '';

  const pills = [
    l.ai_intento   ? `<span class="pill p-${(l.ai_intento||'').toLowerCase()}">${{ VENDE:'Vende', COMPRA:'Compra', ENTRAMBI:'Entrambi' }[l.ai_intento] || ''}</span>` : '',
    l.ai_urgenza   ? `<span class="pill p-${(l.ai_urgenza||'').toLowerCase()}">${{ ALTA:'Alta', MEDIA:'Media', BASSA:'Bassa' }[l.ai_urgenza] || ''}</span>` : '',
    l.seller_type === 'dealer' ? `<span class="pill p-dealer">Dealer</span>` : `<span class="pill p-privato">Privato</span>`,
    zonaLabel      ? `<span class="pill p-zona">${zonaLabel}</span>` : '',
    `<span class="pill p-stato">${(l.stato || 'nuovo').replace('_', ' ')}</span>`,
  ].filter(Boolean).join('');

  const stati   = ['nuovo','contattato','risposto','appuntamento','venduto','non_interessato'];
  const options = stati.map(s =>
    `<option value="${s}" ${s === (l.stato || 'nuovo') ? 'selected' : ''}>${s.replace('_', ' ')}</option>`
  ).join('');

  return `
  <div class="lead-card" data-id="${l.id}">
    <div class="card-strip ${stripClass}"></div>

    <div class="card-header">
      <div class="score-badge ${scoreClass}">${score || '—'}</div>
      <div class="card-title-area">
        <div class="card-title" title="${esc(l.title)}">${esc(l.title) || 'Senza titolo'}</div>
        <div class="card-pills">${pills}</div>
      </div>
    </div>

    <div class="card-body">
      <div class="card-price-row">
        <div class="card-price">${esc(price)}</div>
        ${l.location ? `<div class="card-location">📍 ${esc(l.location)}</div>` : ''}
      </div>

      ${specs.length ? `
      <div class="card-specs">
        ${specs.map(s => `<span>${esc(s)}</span>`).join('<span class="spec-sep"> · </span>')}
        ${l.fonte ? `<span class="spec-sep"> · </span><span style="opacity:.45">${esc(l.fonte)}</span>` : ''}
      </div>` : ''}

      ${l.phone ? `
      <div class="card-phone">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07A19.5 19.5 0 0 1 4.69 12 19.79 19.79 0 0 1 1.61 3.44 2 2 0 0 1 3.6 1.27h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L7.91 9a16 16 0 0 0 6 6l.92-.92a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/>
        </svg>
        ${esc(l.phone)}
      </div>` : ''}

      ${l.description ? `<div class="card-desc">${esc(l.description)}</div>` : ''}

      ${(l.ai_profilo || l.ai_budget_stimato || l.ai_auto_attuale) ? `
      <div class="ai-section">
        <div class="ai-tag">Analisi AI</div>
        ${(l.ai_budget_stimato || l.ai_auto_attuale) ? `
        <div class="ai-meta">
          ${l.ai_budget_stimato ? `<span class="ai-meta-item">Budget: <strong>€${Number(l.ai_budget_stimato).toLocaleString('it-IT')}</strong></span>` : ''}
          ${l.ai_auto_attuale   ? `<span class="ai-meta-item">Auto attuale: <strong>${esc(l.ai_auto_attuale)}</strong></span>` : ''}
        </div>` : ''}
        ${l.ai_profilo ? `<div class="ai-profilo-text">${esc(l.ai_profilo)}</div>` : ''}
      </div>` : ''}

      ${l.ai_messaggio ? `
      <div class="ai-msg-box">
        <div style="flex:1;min-width:0">
          <div class="ai-msg-label">Messaggio pronto</div>
          <div class="ai-msg-text">${linkify(esc(l.ai_messaggio))}</div>
        </div>
        <button class="copy-btn" onclick="copyMessage(${l.id}, this)">
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
            <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
          </svg>
          Copia
        </button>
      </div>` : ''}

      <div class="note-section">
        <div class="note-label">Note</div>
        <textarea class="note-input" id="note-${l.id}" placeholder="Aggiungi note su questo lead..." rows="2">${esc(l.note || '')}</textarea>
      </div>

      <div class="card-actions">
        <select class="stato-select" onchange="updateStato(${l.id}, this.value)">${options}</select>
        <button class="save-note-btn" id="save-note-${l.id}" onclick="saveNote(${l.id})">Salva nota</button>
        ${l.url ? `<a class="open-link" href="${esc(l.url)}" target="_blank" rel="noopener">Apri ↗</a>` : ''}
      </div>
    </div>
  </div>`;
}

// ── ACTIONS ───────────────────────────────────────────
async function updateStato(id, stato) {
  await fetch(`/api/lead/${id}/stato`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ stato }),
  });
  showToast('Stato aggiornato', 'success');
  loadStats();
}

async function saveNote(id) {
  const textarea = document.getElementById('note-' + id);
  if (!textarea) return;

  await fetch(`/api/lead/${id}/note`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ note: textarea.value }),
  });

  const btn = document.getElementById('save-note-' + id);
  if (btn) {
    btn.classList.add('saved');
    btn.textContent = '✓ Salvato';
    setTimeout(() => { btn.classList.remove('saved'); btn.textContent = 'Salva nota'; }, 2200);
  }
}

function copyMessage(id, btn) {
  const card  = document.querySelector(`[data-id="${id}"]`);
  const msgEl = card && card.querySelector('.ai-msg-text');
  if (!msgEl) return;

  navigator.clipboard.writeText(msgEl.textContent).then(() => {
    btn.classList.add('copied');
    btn.innerHTML = `
      <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>
      Copiato!`;
    setTimeout(() => {
      btn.classList.remove('copied');
      btn.innerHTML = `
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
          <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
        </svg>
        Copia`;
    }, 2500);
  });
}

// ── RUN PIPELINE ──────────────────────────────────────
async function runPipeline() {
  const btn   = document.getElementById('run-btn');
  const label = document.getElementById('run-label');

  // Check if already running
  const statusRes = await fetch('/api/run/status');
  const status    = await statusRes.json();
  if (status.running) {
    showToast('Scraping già in corso...', 'error');
    return;
  }

  await fetch('/api/run', { method: 'POST' });

  btn.classList.add('running');
  label.textContent = 'In corso...';
  showToast('Scraping avviato!', 'success');

  // Poll every 5s
  _runPollInterval = setInterval(async () => {
    const res = await fetch('/api/run/status');
    const s   = await res.json();
    if (!s.running) {
      clearInterval(_runPollInterval);
      btn.classList.remove('running');
      label.textContent = 'Avvia scraping';
      if (s.just_finished) {
        showToast('Completato! Ricarico i dati...', 'success');
        setTimeout(loadAll, 1200);
      }
    }
  }, 5000);
}

// ── TOAST ─────────────────────────────────────────────
function showToast(msg, type = '') {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.className = 'toast visible' + (type ? ' ' + type : '');
  clearTimeout(_toastTimer);
  _toastTimer = setTimeout(() => el.classList.remove('visible'), 3200);
}

// ── UTILS ─────────────────────────────────────────────
function setText(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}

function linkify(s) {
  return s.replace(/(https?:\/\/[^\s,]+)/g, '<a href="$1" target="_blank" rel="noopener" style="color:#4f9cf9;word-break:break-all;">$1</a>');
}

function esc(s) {
  return String(s || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ── BOOT ──────────────────────────────────────────────
async function loadAll() {
  await Promise.all([loadStats(), loadLeads()]);
}

// ── IMPOSTAZIONI ──────────────────────────────────────
async function openSettings() {
  const res = await fetch('/api/config');
  const data = await res.json();
  document.getElementById('cfg-groq-key').value = data.groq_api_key || '';
  document.getElementById('cfg-cap').value = data.cap_ricerca || '24100';
  document.getElementById('cfg-raggio').value = data.raggio_km || 30;
  document.getElementById('cfg-max-lead').value = data.max_lead_profilare || 15;
  document.getElementById('cfg-subito-pages').value = data.max_pagine_subito || 6;
  document.getElementById('cfg-autoscout-items').value = data.max_items_autoscout || 30;
  document.getElementById('settings-overlay').classList.add('open');
  document.getElementById('settings-panel').classList.add('open');
}

function closeSettings() {
  document.getElementById('settings-overlay').classList.remove('open');
  document.getElementById('settings-panel').classList.remove('open');
}

document.addEventListener('keydown', e => {
  if (e.key === 'Escape' && document.getElementById('settings-panel').classList.contains('open')) {
    closeSettings();
  }
});

function toggleKeyVisibility() {
  const input = document.getElementById('cfg-groq-key');
  input.type = input.type === 'password' ? 'text' : 'password';
}

async function saveSettings() {
  const payload = {
    groq_api_key:        document.getElementById('cfg-groq-key').value.trim(),
    cap_ricerca:         document.getElementById('cfg-cap').value.trim(),
    raggio_km:           parseInt(document.getElementById('cfg-raggio').value) || 30,
    max_lead_profilare:  parseInt(document.getElementById('cfg-max-lead').value) || 15,
    max_pagine_subito:   parseInt(document.getElementById('cfg-subito-pages').value) || 6,
    max_items_autoscout: parseInt(document.getElementById('cfg-autoscout-items').value) || 30,
  };
  const res = await fetch('/api/config', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload)
  });
  const data = await res.json();
  if (data.ok) {
    showToast('Impostazioni salvate', 'success');
    closeSettings();
  } else {
    showToast('Errore nel salvataggio', 'error');
  }
}
