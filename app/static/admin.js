/* pc-remote — settings.
   Sections live on tabs; edits accumulate and are saved in one go. */

const $ = (id) => document.getElementById(id);
const pwd = {
  get v() { try { return localStorage.getItem('pcr_pwd') || ''; } catch { return ''; } },
  set v(x) { try { localStorage.setItem('pcr_pwd', x); } catch {} },
};

let cfg = null;      // working copy
let catalog = [];
let groups = [];
let dirty = false;

/* ---------------- helpers ---------------- */

let toastTimer;
function toast(text, kind) {
  const el = $('toast');
  el.textContent = window.I18n.s(text);
  el.className = 'toast show' + (kind ? ' ' + kind : '');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (el.className = 'toast'), 3200);
}

function markDirty() {
  dirty = true;
  $('savebar').classList.add('show');
}

function esc(s) {
  return String(s ?? '').replace(/[&<>"]/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
}

async function api(op, extra) {
  const res = await fetch('/admin/api', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(Object.assign(
      { op, password: pwd.v, lang: window.I18n.lang }, extra || {})),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw Object.assign(new Error(data.error || 'Error'), { status: res.status });
  return data;
}

/* ---------------- tabs ---------------- */

function showTab(name) {
  document.querySelectorAll('#tabs button').forEach((b) =>
    b.setAttribute('aria-selected', String(b.dataset.tab === name)));
  document.querySelectorAll('.panel').forEach((p) =>
    p.classList.toggle('active', p.dataset.panel === name));
  // Keep the tab in the URL so a reload does not jump back to the start
  if (location.hash.slice(1) !== name) history.replaceState(null, '', '#' + name);
  document.querySelector('.content')?.scrollTo({ top: 0 });
}

document.querySelectorAll('#tabs button').forEach((b) => {
  b.onclick = () => showTab(b.dataset.tab);
});

/* ---------------- sign-in ---------------- */

async function tryUnlock() {
  const v = $('pwd').value.trim();
  if (!v) { $('lockmsg').textContent = window.I18n.s('Enter the password'); return; }
  pwd.v = v;
  $('unlock').disabled = true;
  $('lockmsg').textContent = window.I18n.s('Checking…');
  try {
    await boot();
    $('lock').classList.remove('show');
  } catch (e) {
    $('lockmsg').textContent = e.status === 429
      ? e.message : window.I18n.s('Wrong password');
  } finally {
    $('unlock').disabled = false;
  }
}

/* ---------------- overview ---------------- */

function renderOverview(d) {
  const s = d.system;
  $('brand_addr').textContent = s.address;
  $('stats').innerHTML = [
    ['Address', s.address, true],
    ['Uptime', s.uptime],
    ['Version', d.version],
    ['Actions enabled',
     `${s.actions_enabled} ${window.I18n.s('of')} ${s.actions_total}`],
    ['Computer', s.hostname, true],
    ['Python', s.python],
  ].map(([k, v, small]) =>
    `<div class="stat"><div class="k">${esc(k)}</div>` +
    `<div class="v${small ? ' small' : ''}">${esc(v)}</div></div>`).join('');

  const a = d.autostart;
  $('ov_autostart').innerHTML = a.installed
    ? (a.stale ? `<span class="pill bad">${window.I18n.s('the task points elsewhere')}</span>`
               : `<span class="pill ok">${window.I18n.s('on')}</span>`)
    : `<span class="pill bad">${window.I18n.s('off')}</span>`;

  const m = d.mqtt;
  $('ov_mqtt').innerHTML = !m.enabled
    ? `<span class="pill">${window.I18n.s('off')}</span>`
    : (m.connected
        ? `<span class="pill ok">${window.I18n.s('connected')} · ${esc(m.node_id)}</span>`
        : `<span class="pill bad">${esc(m.error || window.I18n.s('no connection'))}</span>`);

  $('ov_tray').innerHTML = cfg.tray !== false
    ? `<span class="pill ok">${window.I18n.s('shown')}</span>`
    : `<span class="pill">${window.I18n.s('off')}</span>`;

  const b = d.backups;
  $('ov_backup').innerHTML = b.auto_enabled
    ? `<span class="pill ok">${window.I18n.s('on a schedule')} · ${b.targets} `
      + `${window.I18n.s('target(s)')}</span>`
    : `<span class="pill">${window.I18n.s('manual only')}</span>`;
}

/* ---------------- actions ---------------- */

function renderActions() {
  const host = $('actions_list');
  host.innerHTML = '';
  groups.forEach((g) => {
    const items = catalog.filter((a) => a.group === g.id);
    if (!items.length) return;

    const cap = document.createElement('div');
    cap.className = 'grouptitle';
    cap.style.margin = '4px 0 2px';
    cap.textContent = g.title;
    host.appendChild(cap);

    items.forEach((a) => {
      const row = document.createElement('div');
      row.className = 'row';
      row.innerHTML =
        `<svg class="lead"><use href="#i-${esc(a.icon)}"></use></svg>` +
        `<div class="grow"><div class="t">${esc(a.label)}</div>` +
        `<div class="d">${a.locked ? 'used by integrations — cannot be disabled' : esc(a.hint)}</div></div>` +
        `<label class="sw"><input type="checkbox"${a.enabled ? ' checked' : ''}` +
        `${a.locked ? ' disabled' : ''}><span></span></label>`;
      row.querySelector('input').onchange = (e) => {
        cfg.actions[a.id] = { enabled: e.target.checked };
        markDirty();
      };
      host.appendChild(row);
    });
  });
  window.I18n.apply(host);
}

function renderLaunchers() {
  const host = $('launchers');
  host.innerHTML = '';
  if (!cfg.launchers.length) {
    host.innerHTML = '<div class="hintline" style="margin:0">Nothing yet.</div>';
    return;
  }
  cfg.launchers.forEach((l, i) => {
    const row = document.createElement('div');
    row.className = 'row';
    row.innerHTML =
      `<svg class="lead"><use href="#i-app"></use></svg>` +
      `<div class="grow"><div class="t">${esc(l.name)}</div>` +
      `<div class="d" style="word-break:break-all">${esc(l.target)}</div></div>`;
    const del = document.createElement('button');
    del.className = 'iconbtn';
    del.textContent = '×';
    del.onclick = () => { cfg.launchers.splice(i, 1); renderLaunchers(); markDirty(); };
    row.appendChild(del);
    host.appendChild(row);
  });
  window.I18n.apply(host);
}

$('l_add').onclick = () => {
  const name = $('l_name').value.trim();
  const target = $('l_target').value.trim();
  if (!name || !target) { toast('Fill in the name and the target', 'err'); return; }
  cfg.launchers.push({ name, target });
  $('l_name').value = $('l_target').value = '';
  renderLaunchers();
  markDirty();
};

/* ---------------- MQTT ---------------- */

function renderMqtt(m, st) {
  $('mq_enabled').checked = !!m.enabled;
  $('mq_fields').style.display = m.enabled ? '' : 'none';
  $('mq_host').value = m.host || '';
  $('mq_port').value = m.port || 1883;
  $('mq_username').value = m.username || '';
  $('mq_password').value = '';
  $('mq_password').placeholder = m.password_set
    ? 'set — leave empty to keep it' : 'broker password';
  $('mq_device').value = m.device_name || '';

  const el = $('mq_state');
  if (!m.enabled) { el.textContent = 'off'; el.className = 'd'; }
  else if (st.connected) {
    el.textContent = `${window.I18n.s('connected')} · ${st.node_id}`;
    el.className = 'd state-ok';
  } else {
    el.textContent = st.error
      ? `${window.I18n.s('no connection')}: ${st.error}` : window.I18n.s('connecting…');
    el.className = 'd state-bad';
  }
  $('mq_topics').textContent = st.topics
    ? `${window.I18n.s('topics')}: ${st.topics.base}/…` : '';
}

$('mq_enabled').onchange = (e) => {
  $('mq_fields').style.display = e.target.checked ? '' : 'none';
  markDirty();
};
['mq_host', 'mq_port', 'mq_username', 'mq_password', 'mq_device']
  .forEach((id) => { $(id).oninput = markDirty; });

$('mq_test').onclick = async () => {
  if (dirty) { toast('Save your changes first', 'err'); return; }
  $('mq_test').disabled = true;
  try {
    const r = await api('mqtt_reconnect');
    renderMqtt(cfg.mqtt, r.mqtt);
    toast(r.result, r.mqtt.connected ? 'good' : 'err');
  } catch (e) { toast(e.message, 'err'); }
  finally { $('mq_test').disabled = false; }
};

/* ---------------- tokens ---------------- */

function renderTokens(list) {
  const host = $('tokens');
  host.innerHTML = '';
  if (!list.length) {
    host.innerHTML = '<div class="hintline" style="margin:0">No tokens yet.</div>';
    return;
  }
  list.forEach((t) => {
    const row = document.createElement('div');
    row.className = 'row';
    row.innerHTML =
      `<svg class="lead"><use href="#i-key"></use></svg>` +
      `<div class="grow"><div class="t">${esc(t.name)}</div>` +
      `<div class="d">${esc(t.hint)} · ${window.I18n.s('created')} ${esc(t.created)}` +
      `${t.last_used
          ? ' · ' + window.I18n.s('last used') + ' ' + esc(t.last_used)
          : ' · ' + window.I18n.s('never used')}</div></div>`;
    const del = document.createElement('button');
    del.className = 'iconbtn';
    del.textContent = '×';
    del.title = 'Revoke';
    del.onclick = async () => {
      if (!confirm(window.I18n.s(
        `Revoke the token "${t.name}"? Anything using it stops working.`))) return;
      try {
        const r = await api('token_revoke', { id: t.id });
        renderTokens(r.tokens);
        toast(r.result, 'good');
      } catch (e) { toast(e.message, 'err'); }
    };
    row.appendChild(del);
    host.appendChild(row);
  });
  window.I18n.apply(host);
}

$('tok_add').onclick = async () => {
  const name = $('tok_name').value.trim();
  if (!name) { toast('Describe what the token is for', 'err'); return; }
  try {
    const r = await api('token_issue', { name });
    $('tok_name').value = '';
    renderTokens(r.tokens);
    // Shown exactly once; there is no way to retrieve it later
    prompt('Copy the token — it will not be shown again:', r.token);
    toast(r.result, 'good');
  } catch (e) { toast(e.message, 'err'); }
};

/* ---------------- backups ---------------- */

function renderBackups(b) {
  $('bk_auto').checked = !!b.auto_enabled;
  $('bk_interval').value = b.interval_hours || 24;
  $('bk_secrets').checked = !!b.include_secrets;
  $('bk_last').textContent = b.last_run
    ? `${window.I18n.s('last')}: ${b.last_run.replace('T', ' ')} — ${b.last_result || ''}`
    : window.I18n.s('never sent yet');
  renderHooks();
}

function renderHooks() {
  const host = $('hooks');
  host.innerHTML = '';
  const hooks = cfg.backups.webhooks || [];
  if (!hooks.length) {
    host.innerHTML = '<div class="hintline" style="margin:0">No targets yet.</div>';
    return;
  }
  hooks.forEach((h, i) => {
    const row = document.createElement('div');
    row.className = 'row';
    row.innerHTML =
      `<svg class="lead"><use href="#i-backup"></use></svg>` +
      `<div class="grow"><div class="t">${esc(h.name || h.url)}</div>` +
      `<div class="d" style="word-break:break-all">${esc(h.url)}</div></div>` +
      `<label class="sw"><input type="checkbox"${h.enabled ? ' checked' : ''}><span></span></label>`;
    row.querySelector('input').onchange = (e) => { h.enabled = e.target.checked; markDirty(); };
    const del = document.createElement('button');
    del.className = 'iconbtn';
    del.textContent = '×';
    del.onclick = () => { hooks.splice(i, 1); renderHooks(); markDirty(); };
    row.insertBefore(del, row.querySelector('label'));
    host.appendChild(row);
  });
  window.I18n.apply(host);
}

$('hk_add').onclick = () => {
  const name = $('hk_name').value.trim();
  const url = $('hk_url').value.trim();
  if (!url) { toast('A URL is required', 'err'); return; }
  cfg.backups.webhooks.push({ name: name || url, url, enabled: true, auth_header: '' });
  $('hk_name').value = $('hk_url').value = '';
  renderHooks();
  markDirty();
};

['bk_auto', 'bk_secrets'].forEach((id) => { $(id).onchange = markDirty; });
$('bk_interval').oninput = markDirty;

$('bk_download').onclick = async () => {
  try {
    const r = await api('backup_export', { include_secrets: $('bk_secrets').checked });
    const blob = new Blob([JSON.stringify(r.payload, null, 2)], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = r.filename;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 5000);
    toast('Backup downloaded', 'good');
  } catch (e) { toast(e.message, 'err'); }
};

$('bk_file').onchange = async (e) => {
  const file = e.target.files[0];
  if (!file) return;
  if (!confirm(window.I18n.s('Restore settings from this file? The current ones will be replaced.'))) {
    e.target.value = '';
    return;
  }
  try {
    const payload = JSON.parse(await file.text());
    const r = await api('backup_import', { payload });
    toast(r.result, 'good');
    dirty = false;
    $('savebar').classList.remove('show');
    await boot();
  } catch (err) {
    toast(err.message || 'Could not read the file', 'err');
  } finally {
    e.target.value = '';
  }
};

$('bk_push').onclick = async () => {
  if (dirty) { toast('Save your changes first', 'err'); return; }
  $('bk_push').disabled = true;
  try {
    const r = await api('backup_push');
    renderBackups(r.backups);
    const bad = (r.targets || []).filter((t) => !t.ok);
    toast(bad.length ? `${r.result}: ${bad[0].name} — ${bad[0].detail}` : r.result,
          bad.length ? 'err' : 'good');
  } catch (e) { toast(e.message, 'err'); }
  finally { $('bk_push').disabled = false; }
};

/* ---------------- log ---------------- */

function renderLog(lines) {
  const box = $('log');
  box.innerHTML = '';
  if (!lines.length) { box.textContent = 'the log is empty'; return; }
  lines.forEach((line) => {
    const div = document.createElement('div');
    if (line.includes('[ERROR]') || line.includes('[CRITICAL]')) div.className = 'err';
    else if (line.includes('[WARNING]')) div.className = 'warn';
    div.textContent = line;
    box.appendChild(div);
  });
  box.scrollTop = box.scrollHeight;
}

$('logrefresh').onclick = async () => {
  try { renderLog((await api('log')).lines); } catch (e) { toast(e.message, 'err'); }
};

/* ---------------- system ---------------- */

function renderAutostart(a) {
  $('as_toggle').checked = a.installed && a.enabled;
  $('as_state').textContent = a.installed
    ? `${window.I18n.s('task')} «${a.task}» `
      + window.I18n.s(a.enabled ? 'registered' : 'disabled')
    : 'off — the remote will not come back after a reboot';
  $('as_cmd').textContent = a.command || '';
  $('as_stale').style.display = a.installed && a.stale ? '' : 'none';
}

async function setAutostart(enabled) {
  $('as_toggle').disabled = true;
  try {
    const r = await api('autostart', { enabled });
    renderAutostart(r.autostart);
    toast(r.result, 'good');
  } catch (e) {
    toast(e.message, 'err');
    $('as_toggle').checked = !enabled;
  } finally { $('as_toggle').disabled = false; }
}

$('as_toggle').onchange = (e) => setAutostart(e.target.checked);
$('as_fix').onclick = () => setAutostart(true);
$('tray_toggle').onchange = markDirty;

$('setpwd').onclick = async () => {
  const v = $('newpwd').value.trim();
  if (v.length < 4) { toast('At least 4 characters', 'err'); return; }
  try {
    const r = await api('password', { new_password: v });
    pwd.v = v;  // otherwise the very next request would use the old one
    $('newpwd').value = '';
    toast(r.result, 'good');
  } catch (e) { toast(e.message, 'err'); }
};

$('restart').onclick = async () => {
  if (dirty && !confirm(window.I18n.s('There are unsaved changes and they will be lost. Restart anyway?'))) return;
  try { toast((await api('restart')).result, 'good'); }
  catch (e) { toast(e.message, 'err'); }
};

/* ---------------- saving ---------------- */

function renderFields() {
  $('pc_name').value = cfg.pc_name || '';
  $('default_delay').value = cfg.default_delay;
  $('delay_choices').value = cfg.delay_choices.join(', ');
  $('allowed_networks').value = cfg.allowed_networks.join('\n');
  $('max_fails').value = cfg.max_fails;
  $('lockout_sec').value = cfg.lockout_sec;
  ['pc_name', 'default_delay', 'delay_choices', 'allowed_networks',
   'max_fails', 'lockout_sec'].forEach((id) => { $(id).oninput = markDirty; });
}

function collect() {
  const nums = (s) => s.split(/[,\s]+/).filter(Boolean).map(Number).filter((n) => !isNaN(n));
  return {
    pc_name: $('pc_name').value.trim(),
    default_delay: Math.max(0, Math.min(600, +$('default_delay').value || 0)),
    delay_choices: nums($('delay_choices').value).slice(0, 6),
    allowed_networks: $('allowed_networks').value.split('\n').map((s) => s.trim()).filter(Boolean),
    max_fails: Math.max(1, +$('max_fails').value || 5),
    lockout_sec: Math.max(10, +$('lockout_sec').value || 300),
    actions: cfg.actions,
    launchers: cfg.launchers,
    tray: $('tray_toggle').checked,
    mqtt: {
      enabled: $('mq_enabled').checked,
      host: $('mq_host').value.trim(),
      port: Math.max(1, +$('mq_port').value || 1883),
      username: $('mq_username').value.trim(),
      // Empty means keep the current one: the server fills it back in
      password: $('mq_password').value,
      device_name: $('mq_device').value.trim(),
      discovery_prefix: cfg.mqtt.discovery_prefix || 'homeassistant',
    },
    backups: Object.assign({}, cfg.backups, {
      auto_enabled: $('bk_auto').checked,
      interval_hours: Math.max(1, +$('bk_interval').value || 24),
      include_secrets: $('bk_secrets').checked,
    }),
  };
}

$('save').onclick = async () => {
  const patch = collect();
  if (!patch.delay_choices.length) { toast('At least one delay option is required', 'err'); return; }
  if (!patch.allowed_networks.length) { toast('The network list cannot be empty', 'err'); return; }
  $('save').disabled = true;
  try {
    const r = await api('save', { config: patch });
    dirty = false;
    $('savebar').classList.remove('show');
    toast(r.restart_required ? 'Saved. A restart is required.' : r.result, 'good');
    await boot();
  } catch (e) { toast(e.message, 'err'); }
  finally { $('save').disabled = false; }
};

/* ---------------- loading ---------------- */

async function boot() {
  const d = await api('get');
  cfg = d.config;
  catalog = d.catalog;
  groups = d.groups;
  $('body').style.display = '';
  $('envnote').style.display = d.env_password ? '' : 'none';
  $('logpath').textContent = d.log_file;

  renderOverview(d);
  renderActions();
  renderLaunchers();
  renderFields();
  renderMqtt(cfg.mqtt || {}, d.mqtt || {});
  renderTokens(d.tokens || []);
  renderBackups(d.backups || {});
  $('tray_toggle').checked = cfg.tray !== false;
  renderAutostart(d.autostart);
  window.I18n.apply();   // the markup was just rebuilt
  try { renderLog((await api('log')).lines); } catch {}
}

// In the sidebar the buttons carry a label, not just an icon
window.Theme.bindButton($('theme'), (mode, label) => {
  $('theme').innerHTML += ` ${window.I18n.s('Theme')}: ${window.I18n.s(label)}`;
});
window.I18n.bindButton($('lang'), (lang, name) => {
  $('lang').innerHTML += ` ${window.I18n.s('Language')}: ${name}`;
});

// The action catalog comes from the server, so refetch after a change
window.addEventListener('langchange', () => { if (cfg) boot(); });

$('unlock').onclick = tryUnlock;
$('pwd').addEventListener('keydown', (e) => { if (e.key === 'Enter') tryUnlock(); });

window.addEventListener('beforeunload', (e) => {
  if (dirty) { e.preventDefault(); e.returnValue = ''; }
});

const startTab = location.hash.slice(1);
if (startTab && document.querySelector(`[data-panel="${startTab}"]`)) showTab(startTab);

if (pwd.v) {
  boot().catch(() => { $('lock').classList.add('show'); $('pwd').value = pwd.v; });
} else {
  $('lock').classList.add('show');
}
