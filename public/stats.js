// Stats page: read code and key from the address, load stats from the API, draw the page.
// Address looks like /stats?code=a7Kx2q#key=... (the key is after "#", so it never reaches server logs)

const page = document.getElementById('page');
const code = new URLSearchParams(location.search).get('code') || '';
const key = new URLSearchParams(location.hash.slice(1)).get('key') || '';

let stats = null;
let chartMode = 'day'; // 'day' or 'hour'

// --- small helpers ---

// Escape text before putting it into HTML (the long URL comes from users)
function esc(text) {
  return String(text ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
}

const regionNames = new Intl.DisplayNames(['en'], { type: 'region' });
function countryName(cc) {
  if (!cc || cc === 'XX') return 'Unknown';
  if (cc === 'T1') return 'Tor network';
  try { return regionNames.of(cc); } catch { return cc; }
}

function sourceName(source) {
  return source || 'Direct or unknown';
}

function formatDate(iso) {
  return new Date(iso).toLocaleString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function formatDay(day, long) {
  const options = long ? { weekday: 'short', day: 'numeric', month: 'short' } : { day: 'numeric', month: 'short' };
  return new Date(day + 'T00:00:00Z').toLocaleDateString('en-GB', { ...options, timeZone: 'UTC' });
}

function timeAgo(iso) {
  if (!iso) return 'never';
  const minutes = Math.round((Date.now() - new Date(iso)) / 60000);
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 48) return `${hours} h ago`;
  return `${Math.round(hours / 24)} days ago`;
}

function percent(n, total) {
  const p = (n / total) * 100;
  return p >= 10 ? `${Math.round(p)}%` : `${p.toFixed(1)}%`;
}

async function api(path, method = 'GET') {
  const response = await fetch(path, { method, headers: { authorization: `Bearer ${key}` } });
  const data = response.status === 204 ? null : await response.json();
  return { status: response.status, data };
}

// --- simple states ---

function showMessage(title, text) {
  document.title = 'Stats unavailable, Klik';
  page.innerHTML = `
    <div class="message">
      <h1>${esc(title)}</h1>
      <p>${esc(text)}</p>
      <div class="actions"><a class="btn" href="/">Shorten a new link</a></div>
    </div>`;
}

// --- chart (plain SVG) ---

function chartPoints() {
  if (chartMode === 'hour') {
    return stats.by_hour.map((h) => {
      const hh = String(h.hour).padStart(2, '0');
      return { label: `${hh}:00`, long: `${hh}:00 to ${hh}:59 UTC`, value: h.clicks, tick: h.hour % 6 === 0 || h.hour === 23 };
    });
  }
  return stats.by_day.map((d, i) => ({
    label: formatDay(d.day),
    long: formatDay(d.day, true),
    value: d.clicks,
    tick: (29 - i) % 7 === 0, // a label every 7 days, counting back from today
  }));
}

// Top of the y axis: a round even number, so the middle line is a whole number too
function axisMax(max) {
  for (const top of [4, 6, 8, 10, 12, 16, 20, 30, 40, 50, 60, 80, 100]) {
    if (top >= max) return top;
  }
  return Math.ceil(max / 100) * 100;
}

function drawChart() {
  const box = document.getElementById('chart');
  const points = chartPoints();
  const width = Math.max(box.clientWidth, 280);
  const height = 280;
  const left = 36, right = 12, top = 28, bottom = 28;
  const plotW = width - left - right;
  const plotH = height - top - bottom;
  const max = axisMax(Math.max(...points.map((p) => p.value)));
  const x = (i) => left + (i * plotW) / (points.length - 1);
  const y = (v) => top + plotH - (v / max) * plotH;

  let svg = '';

  // grid lines and y labels: 0, half, max
  for (const v of [0, max / 2, max]) {
    svg += `<line class="grid" x1="${left}" x2="${width - right}" y1="${y(v)}" y2="${y(v)}"/>`;
    svg += `<text class="axis" x="${left - 8}" y="${y(v) + 4}" text-anchor="end">${v}</text>`;
  }

  // x labels, skipping any that would be too close to the previous one
  let lastX = Infinity;
  for (let i = points.length - 1; i >= 0; i--) {
    if (!points[i].tick || lastX - x(i) < 64) continue;
    lastX = x(i);
    const anchor = i === 0 ? 'start' : i === points.length - 1 ? 'end' : 'middle';
    svg += `<text class="axis" x="${x(i)}" y="${height - 6}" text-anchor="${anchor}">${points[i].label}</text>`;
  }

  // the line itself
  const path = points.map((p, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(p.value).toFixed(1)}`).join(' ');
  svg += `<path class="line" d="${path}"/>`;

  // label the highest point
  let peak = 0;
  points.forEach((p, i) => { if (p.value > points[peak].value) peak = i; });
  if (points[peak].value > 0) {
    const anchor = peak < 3 ? 'start' : peak > points.length - 4 ? 'end' : 'middle';
    const word = chartMode === 'hour' ? 'at' : 'on';
    svg += `<circle class="dot" cx="${x(peak)}" cy="${y(points[peak].value)}" r="4"/>`;
    svg += `<text class="peak" x="${x(peak)}" y="${y(points[peak].value) - 10}" text-anchor="${anchor}">${points[peak].value} ${word} ${points[peak].label}</text>`;
  }

  // invisible columns with a tooltip (<title>) for each point
  const step = plotW / (points.length - 1);
  points.forEach((p, i) => {
    svg += `<rect class="hit" x="${x(i) - step / 2}" y="${top}" width="${step}" height="${plotH}"><title>${p.long}: ${p.value} ${p.value === 1 ? 'click' : 'clicks'}</title></rect>`;
  });

  const title = chartMode === 'hour' ? 'Clicks by hour of day, UTC' : 'Clicks per day, last 30 days';
  box.innerHTML = `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${title}">${svg}</svg>`;
  document.getElementById('chart-title').textContent = chartMode === 'hour' ? 'Clicks by hour of day (UTC)' : 'Clicks per day, last 30 days';
  document.getElementById('chart-rows').innerHTML = points.map((p) => `<tr><td>${p.long}</td><td class="num">${p.value}</td></tr>`).join('');
}

// --- full page ---

function tableRows(rows, nameOf) {
  return rows.map((r) => `
    <tr>
      <td class="wrap">${esc(nameOf(r))}</td>
      <td class="num">${r.clicks}</td>
      <td class="num">${percent(r.clicks, stats.total)}</td>
    </tr>`).join('');
}

function showStats() {
  const s = stats;
  const shortUrl = `${location.origin}/${s.code}`;
  const last7 = s.by_day.slice(-7).reduce((sum, d) => sum + d.clicks, 0);
  document.title = `/${s.code} stats, Klik`;

  let html = `
    <div class="head">
      <div>
        <h1>Clicks on /${esc(s.code)}</h1>
        <dl>
          <dt>Goes to</dt><dd><a href="${esc(s.url)}" target="_blank" rel="noopener noreferrer">${esc(s.url)}</a></dd>
          <dt>Short link</dt><dd class="mono">${esc(shortUrl.replace(/^https?:\/\//, ''))}</dd>
          <dt>Created</dt><dd>${formatDate(s.created_at)}</dd>
        </dl>
      </div>
      <div class="head__buttons">
        <button class="btn" type="button" id="copy">Copy short link</button>
        <button class="btn" type="button" id="refresh">Refresh</button>
        <button class="btn btn--danger" type="button" id="delete" aria-expanded="false" aria-controls="confirm">Delete link</button>
      </div>
    </div>

    <div class="confirm" id="confirm" hidden>
      <p>Delete /${esc(s.code)} and its ${s.total} recorded ${s.total === 1 ? 'click' : 'clicks'}? This can't be undone.</p>
      <div class="actions">
        <button class="btn btn--danger" type="button" id="delete-yes">Delete for good</button>
        <button class="btn" type="button" id="delete-no">Keep it</button>
      </div>
      <p class="help is-error" id="delete-error" aria-live="polite"></p>
    </div>

    <div class="numbers">
      <div><b>${s.total}</b><span>clicks in total</span></div>
      <div><b>${last7}</b><span>in the last 7 days</span></div>
      <div><b>${s.by_country.length}</b><span>${s.by_country.length === 1 ? 'country' : 'countries'}</span></div>
      <div><b>${timeAgo(s.last_click)}</b><span>last click</span></div>
    </div>`;

  if (s.total === 0) {
    html += `
      <section class="sheet">
        <div class="message">
          <h2>No clicks yet</h2>
          <p>Share the short link or open it once in another tab. Each click shows up here after a refresh.</p>
          <div class="actions">
            <a class="btn" href="${esc(shortUrl)}" target="_blank" rel="noopener">Open the short link</a>
          </div>
        </div>
      </section>`;
  } else {
    html += `
      <section class="sheet">
        <div class="sheet__head">
          <h2 id="chart-title"></h2>
          <fieldset class="switch">
            <legend class="visually-hidden">Chart view</legend>
            <input type="radio" name="mode" id="mode-day" value="day" ${chartMode === 'day' ? 'checked' : ''}><label for="mode-day">Per day</label>
            <input type="radio" name="mode" id="mode-hour" value="hour" ${chartMode === 'hour' ? 'checked' : ''}><label for="mode-hour">Hour of day</label>
          </fieldset>
        </div>
        <div class="chart" id="chart"></div>
        <details class="chart-table">
          <summary>Show the numbers</summary>
          <table class="table"><thead><tr><th>When</th><th class="num">Clicks</th></tr></thead><tbody id="chart-rows"></tbody></table>
        </details>
      </section>

      <div class="two-cols">
        <section class="sheet">
          <div class="sheet__head"><h2>Countries</h2></div>
          <table class="table">
            <thead><tr><th>Country</th><th class="num">Clicks</th><th class="num">Share</th></tr></thead>
            <tbody>${tableRows(s.by_country, (r) => countryName(r.country))}</tbody>
          </table>
        </section>
        <section class="sheet">
          <div class="sheet__head"><h2>Sources</h2></div>
          <table class="table">
            <thead><tr><th>Source</th><th class="num">Clicks</th><th class="num">Share</th></tr></thead>
            <tbody>${tableRows(s.by_source, (r) => sourceName(r.source))}</tbody>
          </table>
        </section>
      </div>

      <section class="sheet mt">
        <div class="sheet__head">
          <h2>Latest clicks</h2>
          <p class="small muted">${s.recent.length} most recent</p>
        </div>
        <table class="table table--stack">
          <thead><tr><th>Time</th><th>Country</th><th>Source</th></tr></thead>
          <tbody>${s.recent.map((r) => `
            <tr>
              <td data-label="Time" class="mono" title="${esc(r.clicked_at)}">${formatDate(r.clicked_at)}</td>
              <td data-label="Country">${esc(countryName(r.country))}</td>
              <td data-label="Source" class="wrap">${esc(sourceName(r.source))}</td>
            </tr>`).join('')}
          </tbody>
        </table>
      </section>`;
  }

  page.innerHTML = html;
  if (s.total > 0) drawChart();

  // buttons
  document.getElementById('copy').onclick = async (e) => {
    await navigator.clipboard.writeText(shortUrl);
    e.target.textContent = 'Copied';
    setTimeout(() => { e.target.textContent = 'Copy short link'; }, 1800);
  };
  document.getElementById('refresh').onclick = load;

  const confirmBox = document.getElementById('confirm');
  const deleteButton = document.getElementById('delete');
  deleteButton.onclick = () => {
    confirmBox.hidden = !confirmBox.hidden;
    deleteButton.setAttribute('aria-expanded', String(!confirmBox.hidden));
  };
  document.getElementById('delete-no').onclick = () => {
    confirmBox.hidden = true;
    deleteButton.setAttribute('aria-expanded', 'false');
  };
  document.getElementById('delete-yes').onclick = deleteLink;

  const modeSwitch = page.querySelector('.switch');
  if (modeSwitch) {
    modeSwitch.onchange = (e) => { chartMode = e.target.value; drawChart(); };
  }
}

async function deleteLink() {
  const errorLine = document.getElementById('delete-error');
  try {
    const { status, data } = await api(`/api/links/${encodeURIComponent(code)}`, 'DELETE');
    if (status === 204) {
      document.title = 'Link deleted, Klik';
      page.innerHTML = `
        <div class="message">
          <h1>/${esc(code)} is deleted</h1>
          <p>The short link no longer redirects, and all of its recorded clicks are gone.</p>
          <div class="actions"><a class="btn" href="/">Shorten a new link</a></div>
        </div>`;
    } else {
      errorLine.textContent = data.error;
    }
  } catch {
    errorLine.textContent = 'No connection to the server. Try again.';
  }
}

async function load() {
  if (!code || !key) {
    showMessage('This page needs a private stats link', 'Open the private link you got when you created the short link. It ends with #key= and a long key.');
    return;
  }
  try {
    const { status, data } = await api(`/api/links/${encodeURIComponent(code)}/stats`);
    if (status === 200) {
      stats = data;
      showStats();
    } else if (status === 404) {
      showMessage(`No link at /${code}`, 'It was never created, or its owner deleted it.');
    } else if (status === 403) {
      showMessage('This key does not open these stats', 'Check that you copied the whole private link, including the part after #key=.');
    } else {
      showMessage('The stats did not load', data.error);
    }
  } catch {
    showMessage('The stats did not load', 'No connection to the server. Check your internet and refresh the page.');
  }
}

// redraw the chart when the window size changes
window.addEventListener('resize', () => { if (stats && stats.total > 0) drawChart(); });

load();
