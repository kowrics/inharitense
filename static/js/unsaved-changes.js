/* Consistent unsaved-change protection for editable forms and modal workflows. */
(() => {
    'use strict';

    const MESSAGE = 'You have unsaved changes. Are you sure you want to leave? Any information you entered will not be saved.';
    const guarded = new Map();
    let bypass = false;
    let pending = null;

    const ignored = (form) => form.matches('[data-unsaved-ignore], #auditForm')
        || form.method.toLowerCase() === 'get'
        || form.dataset.confirmedSubmit === 'true';

    function snapshot(form) {
        return [...form.querySelectorAll('input,select,textarea')]
            .filter((el) => el.name && !['_csrf', 'csrf_token'].includes(el.name)
                && !['hidden', 'submit', 'button', 'reset', 'file'].includes(el.type))
            .map((el) => [el.name, el.type === 'checkbox' || el.type === 'radio' ? el.checked : el.value]);
    }

    function register(form) {
        if (!(form instanceof HTMLFormElement) || ignored(form) || guarded.has(form)) return;
        const state = { initial: JSON.stringify(snapshot(form)), dirty: false, submitting: false, resetting: false };
        guarded.set(form, state);

        const update = () => { state.dirty = JSON.stringify(snapshot(form)) !== state.initial; };
        form.addEventListener('input', update);
        form.addEventListener('change', update);
        form.addEventListener('submit', (event) => {
            // AJAX forms call preventDefault in their own submit handler. Only leave the
            // form marked as submitting when the browser is actually navigating away.
            queueMicrotask(() => { state.submitting = !event.defaultPrevented; });
        }, true);
        const markClean = () => {
            state.initial = JSON.stringify(snapshot(form));
            state.dirty = false;
            state.submitting = false;
        };
        form.addEventListener('ecmci:submit-failed', () => { state.submitting = false; update(); });
        form.addEventListener('ecmci:mark-saved', markClean);
        // An AJAX form can report its save through the same event used by local drafts.
        form.addEventListener('ecmci:draft-submitted', markClean);
        form.addEventListener('reset', async (event) => {
            if (state.resetting) { queueMicrotask(markClean); return; }
            if (!state.dirty) { queueMicrotask(markClean); return; }
            event.preventDefault();
            event.stopImmediatePropagation();
            if (!await ask()) return;
            state.resetting = true;
            form.reset();
            state.resetting = false;
            markClean();
        }, true);
    }

    function dirtyForm(scope) {
        if (!scope) return null;
        for (const form of scope.querySelectorAll('form')) {
            const state = guarded.get(form);
            if (state?.dirty && !state.submitting) return form;
        }
        return null;
    }

    async function ask() {
        if (pending) return pending;
        const dialog = document.getElementById('unsavedChangesDialog');
        if (!dialog || typeof dialog.showModal !== 'function') return window.confirm(MESSAGE);

        pending = new Promise((resolve) => {
            const continueButton = dialog.querySelector('[data-unsaved-continue]');
            const discardButton = dialog.querySelector('[data-unsaved-discard]');
            const cleanup = () => {
                dialog.removeEventListener('close', onClose);
                continueButton?.removeEventListener('click', onContinue);
                discardButton?.removeEventListener('click', onDiscard);
            };
            const finish = (discard) => {
                cleanup();
                if (dialog.open) dialog.close();
                pending = null;
                resolve(discard);
            };
            const onClose = () => finish(false);
            const onContinue = () => finish(false);
            const onDiscard = () => finish(true);
            dialog.addEventListener('close', onClose, { once: true });
            continueButton?.addEventListener('click', onContinue, { once: true });
            discardButton?.addEventListener('click', onDiscard, { once: true });
            dialog.showModal();
        });
        return pending;
    }

    function closeModal(modal) {
        if (!modal) return;
        // Discard means the modal's current edits are thrown away before it closes.
        // Explicitly clean the guard state so reopening the same modal starts fresh.
        modal.querySelectorAll('form').forEach((form) => {
            const state = guarded.get(form);
            if (!state?.dirty) return;
            state.resetting = true;
            form.reset();
            state.resetting = false;
            state.initial = JSON.stringify(snapshot(form));
            state.dirty = false;
            state.submitting = false;
        });
        if (modal.tagName === 'DIALOG' && modal.open) modal.close();
        else if (modal.classList.contains('modal') && typeof window.closeUiModal === 'function') window.closeUiModal(modal.id);
        else if (modal.classList.contains('modal')) { modal.classList.remove('open'); modal.setAttribute('aria-hidden', 'true'); }
        else if (modal.id && typeof window.closeUiModal === 'function') window.closeUiModal(modal.id);
    }

    function install() {
        document.querySelectorAll('form').forEach(register);

        // Forms injected into a page after load receive the same protection.
        const observer = new MutationObserver((records) => {
            for (const record of records) {
                for (const node of record.addedNodes) {
                    if (!(node instanceof Element)) continue;
                    if (node.matches('form')) register(node);
                    node.querySelectorAll?.('form').forEach(register);
                }
            }
        });
        observer.observe(document.body, { childList: true, subtree: true });

        document.addEventListener('submit', (event) => {
            const form = event.target;
            if (!(form instanceof HTMLFormElement) || !form.dataset.confirm) return;
            if (!window.confirm(form.dataset.confirm)) { event.preventDefault(); event.stopImmediatePropagation(); }
        }, true);

        // Protect links that navigate away from the current page while a form is dirty.
        document.addEventListener('click', async (event) => {
            if (bypass || event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
            const link = event.target.closest('a[href]');
            if (!link || link.target === '_blank' || link.hasAttribute('download') || link.origin !== location.origin) return;
            if (link.pathname === location.pathname && link.search === location.search && link.hash) return;
            const form = [...guarded].find(([candidate, state]) => state.dirty && !state.submitting && candidate.isConnected)?.[0];
            if (!form) return;
            event.preventDefault();
            event.stopImmediatePropagation();
            if (await ask()) { bypass = true; location.assign(link.href); }
        }, true);

        // Protect explicit close/cancel buttons and backdrop clicks for dirty modals.
        document.addEventListener('click', async (event) => {
            if (bypass || event.defaultPrevented) return;
            const modal = event.target.closest('dialog, .modal');
            if (!modal) return;
            const isBackdrop = event.target === modal;
            const closeControl = event.target.closest('[data-unsaved-close], [data-modal-close], [data-ui-modal-close], [data-close-vendor-modal], .modal-close, button[aria-label="Close"]');
            if (!isBackdrop && !closeControl) return;

            // Inventory modals use this explicit close control so the shared guard
            // owns the entire close action. Do not rely on an inline onclick that
            // can close the modal before the asynchronous confirmation resolves.
            const managedClose = closeControl?.hasAttribute('data-ui-modal-close');
            const dirty = dirtyForm(modal);
            if (!dirty && !managedClose) return;

            event.preventDefault();
            event.stopImmediatePropagation();
            if (!dirty) { closeModal(modal); return; }
            if (await ask()) closeModal(modal);
        }, true);

        // Escape on legacy overlays must not bypass the dirty-form guard.
        document.addEventListener('keydown', async (event) => {
            if (event.key !== 'Escape' || bypass) return;
            const modal = [...document.querySelectorAll('.modal.open')].reverse().find((candidate) => dirtyForm(candidate));
            if (!modal) return;
            event.preventDefault();
            event.stopImmediatePropagation();
            if (await ask()) closeModal(modal);
        }, true);

        // Escape/cancel on native dialogs must also respect dirty form contents.
        document.addEventListener('cancel', async (event) => {
            const dialog = event.target;
            if (!(dialog instanceof HTMLDialogElement) || !dirtyForm(dialog)) return;
            event.preventDefault();
            if (await ask()) closeModal(dialog);
        }, true);

        window.addEventListener('beforeunload', (event) => {
            const hasDirty = [...guarded.values()].some((state) => state.dirty && !state.submitting);
            if (hasDirty && !bypass) { event.preventDefault(); event.returnValue = MESSAGE; }
        });
    }

    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', install, { once: true });
    else install();
})();
