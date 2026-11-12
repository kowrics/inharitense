(() => {
  const drawer = document.getElementById('appNav');
  const toggle = document.getElementById('navToggle');
  const close = document.getElementById('navClose');
  const scrim = document.getElementById('navScrim');
  if (!drawer || !toggle || !scrim) return;

  // Keep a lightweight, account-scoped trail of pages visited in this tab.
  // It survives normal page loads without changing routes or server permissions.
  const backButton = document.getElementById('backButton');
  if (backButton) {
    const account = document.body.dataset.accountId || 'session';
    const historyKey = `ecmci-page-history:${account}`;
    const currentUrl = `${window.location.pathname}${window.location.search}${window.location.hash}`;
    const fallbackUrl = backButton.dataset.fallbackUrl || '/';
    const readTrail = () => {
      try {
        const value = JSON.parse(sessionStorage.getItem(historyKey) || '[]');
        return Array.isArray(value) ? value.filter(item => typeof item === 'string' && item.startsWith('/')) : [];
      } catch (_) { return []; }
    };
    const writeTrail = trail => {
      try { sessionStorage.setItem(historyKey, JSON.stringify(trail.slice(-50))); } catch (_) { /* storage may be unavailable */ }
    };
    let trail = readTrail();
    const priorIndex = trail.lastIndexOf(currentUrl);
    if (priorIndex >= 0 && priorIndex < trail.length - 1) {
      // Reconcile when the user used the browser's own Back/Forward controls.
      trail = trail.slice(0, priorIndex + 1);
    } else if (trail[trail.length - 1] !== currentUrl) {
      trail.push(currentUrl);
    }
    writeTrail(trail);

    const previousPage = () => {
      const pages = readTrail();
      const index = pages.lastIndexOf(currentUrl);
      return index > 0 ? pages[index - 1] : fallbackUrl;
    };
    const updateBackState = () => {
      const target = previousPage();
      const isFallbackHere = target === currentUrl;
      backButton.disabled = isFallbackHere;
      backButton.setAttribute('aria-disabled', String(isFallbackHere));
      backButton.title = isFallbackHere ? 'You are on the Dashboard' : 'Go back';
    };
    updateBackState();
    window.addEventListener('pageshow', () => {
      const pages = readTrail();
      const index = pages.lastIndexOf(currentUrl);
      if (index >= 0 && index < pages.length - 1) pages.splice(index + 1);
      else if (index < 0) pages.push(currentUrl);
      writeTrail(pages);
      updateBackState();
    });
    backButton.addEventListener('click', () => {
      const pages = readTrail();
      const index = pages.lastIndexOf(currentUrl);
      let target = fallbackUrl;
      if (index > 0) {
        target = pages[index - 1];
        pages.splice(index);
      } else if (target === currentUrl) {
        updateBackState();
        return;
      } else {
        // A directly opened page has no in-app predecessor: make Dashboard the new root.
        pages.splice(0, pages.length, target);
      }
      writeTrail(pages);
      window.location.assign(target);
    });
  }

  const setOpen = (open) => {
    drawer.classList.toggle('is-open', open);
    scrim.hidden = !open;
    toggle.setAttribute('aria-expanded', String(open));
    drawer.setAttribute('aria-hidden', String(!open));
    drawer.inert = !open;
    document.body.classList.toggle('nav-open', open);
    if (open) close?.focus(); else toggle.focus();
  };
  toggle.addEventListener('click', () => setOpen(!drawer.classList.contains('is-open')));
  close?.addEventListener('click', () => setOpen(false));
  scrim.addEventListener('click', () => setOpen(false));
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && drawer.classList.contains('is-open')) setOpen(false);
  });
  drawer.querySelectorAll('a').forEach((link) => link.addEventListener('click', () => setOpen(false)));

  document.querySelectorAll('[data-ui-tabs]').forEach((tabset) => {
    const buttons = [...tabset.querySelectorAll('[data-tab-target]')];
    const panels = [...document.querySelectorAll(`[data-tab-panel][data-tabset="${tabset.dataset.uiTabs}"]`)];
    const activate = (name) => {
      buttons.forEach((button) => {
        const selected = button.dataset.tabTarget === name;
        button.classList.toggle('is-active', selected);
        button.setAttribute('aria-selected', String(selected));
        button.tabIndex = selected ? 0 : -1;
      });
      panels.forEach((panel) => { panel.hidden = panel.dataset.tabPanel !== name; });
    };
    buttons.forEach((button, index) => {
      button.addEventListener('click', () => activate(button.dataset.tabTarget));
      button.addEventListener('keydown', (event) => {
        if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
        event.preventDefault();
        const next = event.key === 'Home' ? 0 : event.key === 'End' ? buttons.length - 1 : (index + (event.key === 'ArrowRight' ? 1 : -1) + buttons.length) % buttons.length;
        buttons[next].focus();
        activate(buttons[next].dataset.tabTarget);
      });
    });
    const initial = buttons.find((button) => button.classList.contains('is-active')) || buttons[0];
    if (initial) activate(initial.dataset.tabTarget);
  });

  document.querySelectorAll('[data-modal-open]').forEach((button) => {
    button.addEventListener('click', () => {
      const modal = document.getElementById(button.dataset.modalOpen);
      if (modal && typeof modal.showModal === 'function') modal.showModal();
    });
  });
  document.querySelectorAll('dialog[data-ui-modal]').forEach((dialog) => {
    dialog.querySelectorAll('[data-modal-close]').forEach((button) => button.addEventListener('click', () => dialog.close()));
    dialog.addEventListener('click', (event) => {
      if (event.target === dialog) dialog.close();
    });
  });
})();
