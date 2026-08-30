/* pc-remote — the remote itself.
   A single screen, no navigation: everything needed is in view. */

const $ = (id) => document.getElementById(id);
const store = {
  get pwd() { try { return localStorage.getItem('pcr_pwd') || ''; } catch { return ''; } },
  set pwd(v) { try { localStorage.setItem('pcr_pwd', v); } catch {} },
  get delay() {
    try { const v = localStorage.getItem('pcr_delay'); return v === null ? null : +v; }
    catch { return null; }
  },
  set delay(v) { try { localStorage.setItem('pcr_delay', v); } catch {} },
};

let delay = store.delay ?? window.PC.defaultDelay;
let left = 0;          // seconds until shutdown
let pendingLabel = ''; // "Shutting down in" / "Restarting in"
let online = false;
let catalog = null;

/* ---------------- small UI helpers ---------------- */

let toastTimer;
function toast(text, kind) {
  const el = $('toast');
  el.textContent = window.I18n.s(text);
  el.className = 'toast show' + (kind ? ' ' + kind : '');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (el.className = 'toast'), 2600);
}

function buzz(ms) {
  // Haptics confirm the tap sooner than any reply could arrive.
  try { navigator.vibrate && navigator.vibrate(ms); } catch {}
}

function icon(name) {
  return `<svg aria-hidden="true"><use href="#i-${name}"></use></svg>`;
}

/* ---------------- network ---------------- */

async function call(action, extra) {
  // Tell the server the language: labels and replies arrive translated
  const body = Object.assign(
    { action, password: store.pwd, delay, lang: window.I18n.lang }, extra || {});
  const res = await fetch('/api', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw Object.assign(new Error(data.error || window.I18n.s('Error')), { status: res.status });
  return data;
}

/* ---------------- lock screen ---------------- */

function showLock(msg) {
  $('lock').classList.add('show');
  $('lockmsg').textContent = msg || '';
  $('pwd').value = store.pwd;
  setTimeout(() => $('pwd').focus(), 60);
}

function hideLock() { $('lock').classList.remove('show'); }

async function tryUnlock() {
  const value = $('pwd').value.trim();
  if (!value) { $('lockmsg').textContent = window.I18n.s('Enter the password'); return; }
  store.pwd = value;
  $('unlock').disabled = true;
  $('lockmsg').textContent = window.I18n.s('Checking…');
  try {
    // cancel is harmless with no timer running, and it is an honest
    // password check against a real endpoint.
    await call('cancel');
    hideLock();
    $('lockmsg').textContent = '';
    await loadCatalog();
    poll();
  } catch (e) {
    $('lockmsg').textContent = e.status === 429
      ? e.message : window.I18n.s('Wrong password');
  } finally {
    $('unlock').disabled = false;
  }
}

/* ---------------- action catalog ---------------- */

async function loadCatalog() {
  if (catalog) return;
  const res = await fetch('/actions?lang=' + window.I18n.lang);
  catalog = await res.json();
  renderDelays();
  renderGroups();
}

function renderDelays() {
  const seg = $('seg');
  seg.innerHTML = '';
  window.PC.delays.forEach((d) => {
    const b = document.createElement('button');
    b.textContent = d === 0
      ? window.I18n.s('now') : d + ' ' + window.I18n.s('s');
    b.setAttribute('aria-pressed', String(d === delay));
    b.onclick = () => {
      delay = d;
      store.delay = d;
      renderDelays();
      buzz(8);
    };
    seg.appendChild(b);
  });
}

function renderGroups() {
  const host = $('groups');
  host.innerHTML = '';
  catalog.groups.forEach((g) => {
    // Cancel always comes last in its group: it spans the full width
    // and would look like a gap in the middle of the grid.
    const items = catalog.actions
      .filter((a) => a.group === g.id)
      .sort((a, b) => (a.id === 'cancel') - (b.id === 'cancel'));
    if (!items.length) return;

    const title = document.createElement('div');
    title.className = 'grouptitle';
    title.textContent = g.title;
    host.appendChild(title);

    const grid = document.createElement('div');
    grid.className = 'grid';
    items.forEach((a) => grid.appendChild(actionButton(a)));
    host.appendChild(grid);
  });
  window.I18n.apply(host);
  paintCountdown(); // buttons just appeared, set their visibility
}

function actionButton(a) {
  const b = document.createElement('button');
  // Full width: this is the emergency button and must be easy to hit.
  b.className = 'act' + (a.id === 'cancel' ? ' wide' : '');
  b.dataset.tone = a.tone;
  b.dataset.action = a.id;
  b.innerHTML = `${icon(a.icon)}<span class="lbl">${a.label}</span>` +
                `<span class="hint">${a.hint}</span>`;

  let armed = false, armTimer;
  const disarm = () => {
    armed = false;
    clearTimeout(armTimer);
    b.classList.remove('arm');
    b.querySelector('.lbl').textContent = a.label;
  };

  b.onclick = async () => {
    // Confirmation inside the button: on a phone that is faster and more
    // accurate than a modal, and it does not cover the rest of the screen.
    if (a.confirm && !armed) {
      armed = true;
      b.classList.add('arm');
      b.querySelector('.lbl').textContent = window.I18n.s('Sure?');
      buzz(12);
      armTimer = setTimeout(disarm, 3000);
      return;
    }
    disarm();
    b.disabled = true;
    buzz(20);
    try {
      const data = await call(a.id);
      toast(data.result, 'good');
      if (data.pending_left) {
        left = data.pending_left;
        pendingLabel = window.I18n.s(
        a.id === 'reboot' ? 'Restarting in' : 'Shutting down in');
        paintCountdown();
      }
      if (a.id === 'cancel') { left = 0; paintCountdown(); }
    } catch (e) {
      toast(e.message, 'err');
      if (e.status === 403) showLock(window.I18n.s('The password did not work'));
    } finally {
      b.disabled = false;
    }
  };
  return b;
}

/* ---------------- countdown ---------------- */

function paintCountdown() {
  const on = left > 0;
  $('cd').classList.toggle('show', on);
  $('cdnum').textContent = left;
  $('cdwhat').textContent = pendingLabel || window.I18n.s('Shutting down in');
  $('delaycard').style.display = on ? 'none' : '';

  // Cancel is always available, and in exactly one place: in the countdown
  // panel while it runs, as a button in the list otherwise. Without this
  // there was nothing to cancel with precisely when a timer had been
  // started elsewhere and the remote had not learned about it yet.
  const gridCancel = document.querySelector('.act[data-action="cancel"]');
  if (gridCancel) gridCancel.style.display = on ? 'none' : '';

  if (on) $('dot').className = 'dot busy';
}

setInterval(() => {
  if (left > 0) { left--; paintCountdown(); }
}, 1000);

$('cdcancel').onclick = async () => {
  buzz(20);
  try {
    const data = await call('cancel');
    left = 0;
    paintCountdown();
    toast(data.result, 'good');
  } catch (e) {
    toast(e.message, 'err');
  }
};

/* ---------------- status polling ---------------- */

let lastSeen = null;

async function poll() {
  try {
    const res = await fetch('/healthz?lang=' + window.I18n.lang,
                            { cache: 'no-store' });
    const d = await res.json();
    online = true;
    lastSeen = Date.now();
    document.body.classList.remove('is-offline');
    $('offline').classList.remove('show');
    $('sub').textContent = window.I18n.s('online') + ' · '
      + window.I18n.s('uptime') + ' ' + d.uptime;
    $('dot').className = 'dot ' + (d.pending_left ? 'busy' : 'on');

    // The server is the source of truth: it also knows about timers
    // started from the smart home, by voice or from another device.
    if (d.pending_left) {
      left = d.pending_left;
      pendingLabel = window.I18n.s(
        d.pending === 'reboot' ? 'Restarting in' : 'Shutting down in');
    } else if (left > 0 && d.pending === null) {
      left = 0;
    }
    paintCountdown();
  } catch {
    online = false;
    document.body.classList.add('is-offline');
    $('offline').classList.add('show');
    $('offlinesub').textContent = lastSeen
      ? window.I18n.s('last reply') + ' '
        + new Date(lastSeen).toLocaleTimeString()
      : window.I18n.s('check that the computer is on and online');
    $('sub').textContent = window.I18n.s('no connection');
    $('dot').className = 'dot off';
  }
}

/* ---------------- startup ---------------- */

window.Theme.bindButton($('theme'));
window.I18n.bindButton($('lang'));

// On a language change the catalog has to be fetched again
window.addEventListener('langchange', async () => {
  catalog = null;
  await loadCatalog();
  window.I18n.apply();
  poll();
});

$('unlock').onclick = tryUnlock;
$('pwd').addEventListener('keydown', (e) => { if (e.key === 'Enter') tryUnlock(); });

// Refresh as soon as the tab is visible again: a phone may have slept.
document.addEventListener('visibilitychange', () => { if (!document.hidden) poll(); });

paintCountdown();
if (store.pwd) {
  loadCatalog();
  poll();
} else {
  showLock();
}
setInterval(poll, 5000);
