/* Dialogs that belong to the interface.

   The browser's own confirm() and prompt() ignore the theme, cannot be
   translated, and in the case of a freshly issued token put the one string
   that has to be copied into a box that is awkward to copy from.

   Built on <dialog>: the focus trap, Esc, an inert background and top-layer
   stacking come from the platform rather than from code here.

   Everything returns a promise, so a caller reads top to bottom:

     if (!await Dialog.confirm({ title: '…', danger: true })) return; */

(function () {
  const REDUCED = window.matchMedia('(prefers-reduced-motion: reduce)');

  function t(text, ...args) {
    return window.I18n ? window.I18n.s(text, ...args) : text;
  }

  function esc(v) {
    return String(v ?? '').replace(/[&<>"]/g, (c) =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  }

  /* Works on plain HTTP too. The clipboard API needs a secure context, and
     the remote is normally opened by address rather than through localhost,
     so the old selection trick has to stay as a fallback. */
  async function copy(text) {
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(text);
        return true;
      }
    } catch { /* fall through */ }
    const box = document.createElement('textarea');
    box.value = text;
    box.setAttribute('readonly', '');
    box.style.cssText = 'position:fixed;top:-1000px;opacity:0';
    document.body.appendChild(box);
    box.select();
    let ok = false;
    try { ok = document.execCommand('copy'); } catch { ok = false; }
    box.remove();
    return ok;
  }

  function show(spec) {
    return new Promise((resolve) => {
      const opener = document.activeElement;
      const dlg = document.createElement('dialog');
      dlg.className = 'sheet';

      const cancel = spec.cancel !== false;
      dlg.innerHTML =
        `<div class="sheet-body">` +
          `<h2 class="sheet-title">${esc(t(spec.title))}</h2>` +
          (spec.body ? `<p class="sheet-text">${esc(t(spec.body, ...(spec.args || [])))}</p>` : '') +
          (spec.secret
            ? `<div class="sheet-secret"><code>${esc(spec.secret)}</code></div>` +
              `<button type="button" class="btn ghost" data-copy>${esc(t('Copy'))}</button>`
            : '') +
          `<div class="sheet-actions">` +
            (cancel ? `<button type="button" class="btn" data-no>${esc(t('Cancel'))}</button>` : '') +
            `<button type="button" class="btn ${spec.danger ? 'danger' : 'primary'}" data-yes>` +
              `${esc(t(spec.ok))}</button>` +
          `</div>` +
        `</div>`;

      document.body.appendChild(dlg);

      let leaving = false;
      function close(value) {
        if (leaving) return;
        leaving = true;
        dlg.classList.remove('in');
        let done = false;
        const finish = () => {
          if (done) return;
          done = true;
          dlg.removeEventListener('transitionend', finish);
          dlg.close();
          dlg.remove();
          if (opener && opener.focus) opener.focus();
          resolve(value);
        };
        if (REDUCED.matches) finish();
        else {
          dlg.addEventListener('transitionend', finish);
          // A dropped transition would leave the page stuck behind a modal
          setTimeout(finish, 400);
        }
      }

      dlg.querySelector('[data-yes]').onclick = () => close(true);
      const no = dlg.querySelector('[data-no]');
      if (no) no.onclick = () => close(false);

      const copyBtn = dlg.querySelector('[data-copy]');
      if (copyBtn) {
        copyBtn.onclick = async () => {
          const ok = await copy(spec.secret);
          copyBtn.textContent = ok ? t('Copied') : t('Select it and copy by hand');
          copyBtn.disabled = ok;
        };
      }

      // Esc: the platform would close the dialog outright, skipping the
      // animation and the promise
      dlg.addEventListener('cancel', (e) => { e.preventDefault(); close(false); });
      // A click that lands on the element itself landed on the backdrop
      dlg.addEventListener('click', (e) => { if (e.target === dlg) close(false); });

      dlg.showModal();
      // Enter confirms, so the safe button is the one holding focus when
      // the action cannot be undone
      const focus = spec.danger && no ? no : dlg.querySelector('[data-yes]');
      focus.focus();

      if (REDUCED.matches) dlg.classList.add('in');
      else requestAnimationFrame(() => dlg.classList.add('in'));
    });
  }

  window.Dialog = {
    /** Resolves true if confirmed. `args` fill %s in the body. */
    confirm(spec) { return show({ ok: 'OK', ...spec }); },
    /** One button and a value to copy; resolves when dismissed. */
    reveal(spec) { return show({ ok: 'Done', ...spec, cancel: false }); },
  };
}());
