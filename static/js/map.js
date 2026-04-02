/* ════════════════════════════════════════════════════
   AUTO LEAD BERGAMO — Map Module
   ════════════════════════════════════════════════════ */

const MapModule = (() => {
  let _map     = null;
  let _markers = null;
  const _cache = new Map();

  function init() {
    if (_map) { setTimeout(() => _map.invalidateSize(), 50); return; }
    _map = L.map('leaflet-map', { zoomControl: true }).setView([45.6983, 9.6773], 11);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© <a href="https://openstreetmap.org">OpenStreetMap</a>',
      maxZoom: 18,
    }).addTo(_map);
    _markers = L.layerGroup().addTo(_map);
    setTimeout(() => _map.invalidateSize(), 120);
  }

  async function geocode(location) {
    if (!location) return null;
    const key = location.trim().toLowerCase();
    if (_cache.has(key)) return _cache.get(key);

    const hasBG = /\bbg\b|bergamo/i.test(location);
    const q = hasBG ? location : location + ', Italia';

    try {
      const res  = await fetch(
        `https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(q)}&format=json&limit=1`,
        { headers: { 'Accept-Language': 'it' } }
      );
      const data = await res.json();
      if (data && data[0]) {
        const coords = { lat: parseFloat(data[0].lat), lng: parseFloat(data[0].lon) };
        _cache.set(key, coords);
        return coords;
      }
    } catch (_) {}

    _cache.set(key, null);
    return null;
  }

  function scoreColor(score) {
    if (score >= 7) return '#0FD488';
    if (score >= 5) return '#F0A030';
    return '#E8472F';
  }

  function makeIcon(score) {
    const c = scoreColor(score);
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="30" height="36" viewBox="0 0 30 36">
      <circle cx="15" cy="13" r="12" fill="${c}" stroke="#08090E" stroke-width="2"/>
      <text x="15" y="18" text-anchor="middle"
            font-family="'JetBrains Mono',monospace"
            font-size="11" font-weight="700" fill="#fff">${score}</text>
      <path d="M15 36 L9 23 Q15 27 21 23 Z" fill="${c}"/>
    </svg>`;
    return L.divIcon({
      html: svg,
      className: '',
      iconSize:   [30, 36],
      iconAnchor: [15, 36],
      popupAnchor:[0, -38],
    });
  }

  function makePopup(l) {
    const score = l.ai_score || 0;
    const c = scoreColor(score);
    const e = s => String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
    return `
    <div style="padding:12px;font-family:'Barlow',sans-serif;">
      <div style="font-size:13px;font-weight:600;color:#DDE2F0;margin-bottom:8px;line-height:1.35">
        ${e(l.title)}
      </div>
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:7px">
        <span style="font-family:'JetBrains Mono',monospace;font-size:18px;font-weight:700;color:${c}">
          ${score}<small style="font-size:8px;color:#3A4060">/10</small>
        </span>
        ${l.location ? `<span style="font-size:11px;color:#6E7898">📍 ${e(l.location)}</span>` : ''}
      </div>
      ${l.price_raw ? `<div style="font-family:'JetBrains Mono',monospace;font-size:16px;font-weight:700;color:#DDE2F0;margin-bottom:7px">${e(l.price_raw)}</div>` : ''}
      ${l.ai_messaggio ? `
      <div style="font-size:11px;color:#6E7898;font-style:italic;line-height:1.5;border-top:1px dashed #252838;padding-top:7px;margin-bottom:8px">
        ${e(l.ai_messaggio.substring(0, 100))}${l.ai_messaggio.length > 100 ? '…' : ''}
      </div>` : ''}
      ${l.url ? `<a href="${e(l.url)}" target="_blank" style="font-size:11px;color:#E8472F;font-weight:600;text-decoration:none">
        Apri annuncio ↗
      </a>` : ''}
    </div>`;
  }

  async function render(leads) {
    if (!_map || !_markers) return;
    _markers.clearLayers();
    if (!leads.length) return;

    const bar    = document.getElementById('geo-bar');
    const status = document.getElementById('geo-status');
    bar.classList.add('visible');

    let done = 0;
    for (const l of leads) {
      if (!l.location) { done++; continue; }
      status.textContent = `Posiziono ${done + 1} / ${leads.length}…`;

      const coords = await geocode(l.location);
      if (coords) {
        const marker = L.marker([coords.lat, coords.lng], {
          icon: makeIcon(l.ai_score || 0),
        });
        marker.bindPopup(makePopup(l), { maxWidth: 260, minWidth: 240 });
        _markers.addLayer(marker);
      }

      done++;
      await new Promise(r => setTimeout(r, 250));
    }

    bar.classList.remove('visible');

    const pts = [];
    _markers.eachLayer(m => pts.push(m.getLatLng()));
    if (pts.length > 1)     _map.fitBounds(L.latLngBounds(pts).pad(0.15));
    else if (pts.length === 1) _map.setView(pts[0], 13);
  }

  return { init, render };
})();
