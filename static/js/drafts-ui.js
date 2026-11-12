/* Simple account-specific local drafts for the capstone demo.
 * Drafts stay in this browser/device; passwords, CSRF tokens, and file inputs are never stored.
 */
(() => {
    const accountId = document.body?.dataset.accountId || 'anonymous';
    const prefix = `ecmci:form-draft:v1:${accountId}:`;
    const safeKey = (form) => prefix + (form.dataset.draftForm || form.action || form.id || 'form');
    const fieldsFor = (form) => [...form.querySelectorAll('input,select,textarea')]
        .filter((el) => el.name && !['_csrf', 'password', 'current_password', 'new_password', 'confirm_password'].includes(el.name)
            && !['hidden', 'password', 'file', 'submit', 'button', 'reset'].includes(el.type));

    function restore(form, record) {
        const values = record?.values || {};
        fieldsFor(form).forEach((el) => {
            if (!(el.name in values)) return;
            const value = values[el.name];
            if (el.type === 'checkbox') el.checked = Boolean(value);
            else if (el.type === 'radio') el.checked = el.value === value;
            else if (el.tagName === 'SELECT' && el.multiple) {
                [...el.options].forEach((option) => { option.selected = Array.isArray(value) && value.includes(option.value); });
            } else el.value = value ?? '';
        });
    }

    function init(form) {
        const key = safeKey(form);
        let saved = null;
        try { saved = JSON.parse(localStorage.getItem(key) || 'null'); } catch (_) { saved = null; }

        const status = document.createElement('div');
        status.className = 'draft-status form-hint';
        status.setAttribute('role', 'status');
        status.hidden = true;
        form.parentNode.insertBefore(status, form);

        const restoreSaved = () => {
            try { saved = JSON.parse(localStorage.getItem(key) || 'null'); } catch (_) { saved = null; }
            if (saved?.values) {
                restore(form, saved);
                form.dispatchEvent(new Event('ecmci:mark-saved'));
                status.hidden = false;
                status.textContent = `Restored saved draft from ${new Date(saved.savedAt).toLocaleString()}. Draft is stored in this browser for this account.`;
                return true;
            }
            return false;
        };
        restoreSaved();
        form.addEventListener('ecmci:restore-draft', restoreSaved);
        form.addEventListener('ecmci:draft-submitted', () => {
            localStorage.removeItem(key);
            saved = null;
            status.hidden = false;
            status.textContent = 'Draft cleared after successful save.';
        });

        let actionRow = form.querySelector('.figma-form-actions, .form-actions, .modal-actions');
        if (!actionRow) { actionRow = document.createElement('div'); actionRow.className = 'figma-form-actions draft-actions'; form.appendChild(actionRow); }
        const draftActions = document.createElement('div');
        draftActions.className = 'draft-action-group';
        draftActions.setAttribute('aria-label', 'Draft actions');
        actionRow.appendChild(draftActions);
        const save = document.createElement('button');
        save.type = 'button';
        save.className = 'secondary draft-save-button';
        save.textContent = 'Save as Draft';
        save.addEventListener('click', () => {
            const values = {};
            fieldsFor(form).forEach((el) => {
                if (el.type === 'checkbox') values[el.name] = el.checked;
                else if (el.type === 'radio') { if (el.checked) values[el.name] = el.value; }
                else if (el.tagName === 'SELECT' && el.multiple) values[el.name] = [...el.selectedOptions].map((o) => o.value);
                else values[el.name] = el.value;
            });
            const record = { values, savedAt: new Date().toISOString() };
            try {
                localStorage.setItem(key, JSON.stringify(record));
                status.hidden = false;
                status.textContent = `Draft saved ${new Date(record.savedAt).toLocaleString()}. You can return to this form in this browser.`;
                form.dispatchEvent(new Event('ecmci:mark-saved'));
                if (window.toast) window.toast('Draft saved in this browser.', 'success');
            } catch (_) {
                status.hidden = false;
                status.textContent = 'Draft could not be saved. Browser storage may be full or disabled.';
            }
        });
        draftActions.appendChild(save);

        const clear = document.createElement('button');
        clear.type = 'button';
        clear.className = 'secondary draft-clear-button';
        clear.textContent = 'Clear Draft';
        clear.addEventListener('click', () => {
            if (!window.confirm('Clear this saved draft? This action cannot be undone.')) return;
            localStorage.removeItem(key);
            saved = null;
            status.hidden = false;
            status.textContent = 'Saved draft cleared.';
        });
        draftActions.appendChild(clear);

        form.addEventListener('submit', () => {
            try { sessionStorage.setItem('ecmci:draft-submitted', key); } catch (_) { /* ignore */ }
        });
    }

    document.addEventListener('DOMContentLoaded', () => {
        const submittedKey = sessionStorage.getItem('ecmci:draft-submitted');
        if (submittedKey) {
            sessionStorage.removeItem('ecmci:draft-submitted');
            if (document.querySelector('.flash.success')) localStorage.removeItem(submittedKey);
        }
        document.querySelectorAll('form[data-draft-form]').forEach(init);
    });
})();
