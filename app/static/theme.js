/* Theme switch: follow system -> light -> dark.

   Applied before paint (the script sits in <head>), otherwise a dark
   page would flash white first.

   "Follow system" is not the same as light: it tracks the OS setting,
   which is what most people want, so it comes first. */

(function () {
  const KEY = 'pcr_theme';
  const ORDER = ['auto', 'light', 'dark'];
  const LABEL = { auto: 'follow system', light: 'light', dark: 'dark' };

  function read() {
    try { return localStorage.getItem(KEY) || 'auto'; } catch { return 'auto'; }
  }

  function apply(mode) {
    const root = document.documentElement;
    if (mode === 'auto') root.removeAttribute('data-theme');
    else root.setAttribute('data-theme', mode);

    // The browser status bar colour has to follow the theme too
    const dark = mode === 'dark' ||
      (mode === 'auto' && window.matchMedia('(prefers-color-scheme: dark)').matches);
    document.querySelectorAll('meta[name="theme-color"]').forEach((m) => {
      if (!m.media) m.content = dark ? '#000000' : '#f5f5f7';
    });
  }

  apply(read());

  window.Theme = {
    get current() { return read(); },
    get label() { return LABEL[read()]; },
    set(mode) {
      try { localStorage.setItem(KEY, mode); } catch {}
      apply(mode);
      window.dispatchEvent(new CustomEvent('themechange', { detail: mode }));
    },
    next() {
      const mode = ORDER[(ORDER.indexOf(read()) + 1) % ORDER.length];
      this.set(mode);
      return mode;
    },
    /** Cycling button: draws its own icon and label. */
    bindButton(el, onChange) {
      const paint = () => {
        const mode = read();
        el.innerHTML = `<svg><use href="#i-theme-${mode}"></use></svg>`;
        el.title = `Theme: ${LABEL[mode]}`;
        el.setAttribute('aria-label', el.title);
        if (onChange) onChange(mode, LABEL[mode]);
      };
      el.onclick = () => { this.next(); paint(); };
      paint();
    },
  };

  // The system theme may change while the tab is open
  window.matchMedia('(prefers-color-scheme: dark)')
    .addEventListener('change', () => { if (read() === 'auto') apply('auto'); });
})();
