(() => {
  'use strict';

  // Accessible show/hide behavior shared by the sign-in and account settings forms.
  document.addEventListener('click', (event) => {
    const toggle = event.target.closest('[data-toggle-password]');
    if (!toggle) return;
    const wrapper = toggle.closest('.password-input-wrap');
    const input = wrapper?.querySelector('input');
    if (!input) return;
    const reveal = input.type === 'password';
    input.type = reveal ? 'text' : 'password';
    toggle.textContent = reveal ? 'Hide' : 'Show';
    toggle.setAttribute('aria-label', `${reveal ? 'Hide' : 'Show'} ${input.name.replaceAll('_', ' ')}`);
  });

  // Validate mismatched passwords before a request is sent. The current password
  // remains in the form control because the browser does not submit/re-render the form.
  const settingsForm = document.querySelector('[data-settings-form]');
  if (settingsForm) {
    const current = settingsForm.querySelector('[data-current-password]');
    const next = settingsForm.querySelector('[data-new-password]');
    const confirm = settingsForm.querySelector('[data-confirm-password]');
    const passwordSubmit = settingsForm.querySelector('[data-password-submit]');

    settingsForm.addEventListener('input', () => {
      if (confirm) confirm.setCustomValidity('');
      if (next) next.setCustomValidity('');
      if (current) current.setCustomValidity('');
    });

    settingsForm.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' && event.target.matches('[data-current-password], [data-new-password], [data-confirm-password]')) {
        event.preventDefault();
        passwordSubmit?.click();
      }
    });

    settingsForm.addEventListener('submit', (event) => {
      const passwordSubmitRequested = event.submitter === passwordSubmit ||
        (!event.submitter && Boolean(current?.value || next?.value || confirm?.value));
      if (!passwordSubmitRequested) return;
      let invalid = false;
      if (!current?.value) {
        current?.setCustomValidity('Enter your current password.');
        invalid = true;
      }
      if (!next?.value || next.value.length < 10 || next.value.length > 128 || !/[A-Za-z]/.test(next.value) || !/[0-9]/.test(next.value)) {
        next?.setCustomValidity('Use 10–128 characters with at least one letter and one number.');
        invalid = true;
      }
      if (!confirm?.value || next?.value !== confirm.value) {
        confirm?.setCustomValidity('New passwords do not match.');
        invalid = true;
      }
      if (invalid) {
        event.preventDefault();
        settingsForm.querySelector(':invalid')?.reportValidity();
      }
    });
  }

  // The temporary credential is only present in the immediate account-creation response.
  const copyButton = document.querySelector('[data-copy-temp-password]');
  if (copyButton) {
    copyButton.addEventListener('click', async () => {
      const value = document.getElementById('generatedTemporaryPassword')?.textContent?.trim();
      if (!value) return;
      try {
        await navigator.clipboard.writeText(value);
        copyButton.textContent = 'Copied';
      } catch (_) {
        copyButton.textContent = 'Select the password to copy';
      }
    });
  }

  // Client warning improves the experience; the signed, permanent Flask session
  // independently expires after 30 minutes without a request.
  const timeoutMs = Number(document.body.dataset.sessionTimeoutMs || 0);
  if (timeoutMs > 0) {
    const warningMs = Math.min(Number(document.body.dataset.sessionWarningMs || 120000), timeoutMs - 1000);
    let warningTimer;
    let logoutTimer;
    const logout = () => { window.location.assign('/logout'); };
    let lastActivityAt = Date.now();
    let lastKeepaliveAt = Date.now();
    const keepaliveUrl = document.body.dataset.sessionKeepaliveUrl;
    // An authenticated page load follows a user navigation/refresh. Establish the
    // server marker here so the browser warning and server-side timeout share a
    // consistent starting point; background API polling remains excluded.
    if (keepaliveUrl) {
      fetch(keepaliveUrl, { credentials: 'same-origin', cache: 'no-store' }).catch(() => {});
    }
    const noteActivity = () => {
      lastActivityAt = Date.now();
      resetTimers();
      if (keepaliveUrl && lastActivityAt - lastKeepaliveAt >= 60000) {
        lastKeepaliveAt = lastActivityAt;
        fetch(keepaliveUrl, { credentials: 'same-origin', cache: 'no-store' }).catch(() => {});
      }
    };
    const resetTimers = () => {
      window.clearTimeout(warningTimer);
      window.clearTimeout(logoutTimer);
      warningTimer = window.setTimeout(() => {
        const keepWorking = window.confirm('Your ECMCI session will expire soon because of inactivity. Select OK to continue working, or Cancel to sign out.');
        if (keepWorking && keepaliveUrl) {
          // Only explicit confirmation refreshes the server-side activity marker.
          fetch(keepaliveUrl, { credentials: 'same-origin', cache: 'no-store' })
            .then((response) => { if (response.ok) window.location.reload(); else logout(); })
            .catch(logout);
        } else if (keepWorking) window.location.reload();
        else logout();
      }, timeoutMs - warningMs);
      logoutTimer = window.setTimeout(logout, timeoutMs);
    };
    ['pointerdown', 'pointermove', 'keydown', 'scroll', 'touchstart'].forEach((name) => {
      document.addEventListener(name, noteActivity, { passive: true });
    });
    resetTimers();
  }
})();
