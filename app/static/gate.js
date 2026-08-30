/* The first-run gate.

   The project used to ship with a password written into its defaults. It was
   in the README, in every copy of the source and in search results, which
   makes it a published key rather than a password. Now the settings start
   empty, the remote refuses every command until one exists, and the sign-in
   box turns into a box that creates one.

   Both pages show the same thing here; only what happens after a success
   differs, and that stays with them. */

(function () {
  const $ = (id) => document.getElementById(id);
  const state = { setup: $('lock').dataset.setup === '1' };

  function paint() {
    $('view-setup').hidden = !state.setup;
    $('view-signin').hidden = state.setup;
    $('field-repeat').hidden = !state.setup;
    $('label-create').hidden = !state.setup;
    $('label-signin').hidden = state.setup;
    $('pwd').autocomplete = state.setup ? 'new-password' : 'current-password';
  }

  /* Resolves with the accepted password, or null when the box should stay
     open — by then the reason is already on screen. */
  async function create() {
    const value = $('pwd').value.trim();

    if (value.length < 4) {
      $('lockmsg').textContent = window.I18n.s('At least 4 characters');
      return null;
    }
    if (value !== $('pwd2').value.trim()) {
      $('lockmsg').textContent = window.I18n.s('The two passwords do not match');
      return null;
    }

    $('unlock').disabled = true;
    $('lockmsg').textContent = window.I18n.s('Checking…');
    try {
      const res = await fetch('/setup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password: value, lang: window.I18n.lang }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        // 409 means somebody claimed the remote from another device while
        // this page sat open: the box becomes a sign-in box on the spot
        if (res.status === 409) {
          state.setup = false;
          paint();
        }
        $('pwd2').value = '';
        $('lockmsg').textContent = data.error || window.I18n.s('Error');
        return null;
      }
      state.setup = false;
      paint();
      $('lockmsg').textContent = '';
      return value;
    } catch (e) {
      $('lockmsg').textContent = e.message;
      return null;
    } finally {
      $('unlock').disabled = false;
    }
  }

  window.Gate = {
    /** True while the remote has never been given a password. */
    get needed() { return state.setup; },
    paint,
    create,
  };
}());
