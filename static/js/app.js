const CSRF =
    document.querySelector('meta[name=csrf-token]')?.content ||
    document.querySelector('input[name=_csrf]')?.value ||
    '';

function secureFetch(url, opts = {}) {
    opts.headers = {
        ...(opts.headers || {}),
        ...(CSRF ? { 'X-CSRFToken': CSRF } : {})
    };

    return fetch(url, opts);
}

const $ = (selector) => document.querySelector(selector);

let toastTimer;


/* =========================================================
   GENERAL HELPERS
   ========================================================= */

function toast(message, kind = '') {
    const el = $('#toast');

    if (!el) {
        return;
    }

    el.textContent = message;
    el.className = 'toast show ' + kind;

    clearTimeout(toastTimer);

    toastTimer = setTimeout(() => {
        el.className = 'toast';
    }, 2600);
}


function fmt(number) {
    return Number(number || 0).toLocaleString();
}


function escapeHtml(value) {
    return String(value ?? '').replace(
        /[&<>'"]/g,
        (char) => ({
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            "'": '&#39;',
            '"': '&quot;'
        }[char])
    );
}


/* =========================================================
   THEME
   ========================================================= */

function initTheme() {
    const saved = localStorage.getItem('inharitense-theme');
    const useDark = saved ? saved === 'dark' : false; // Figma reference defaults to White Mode

    document.body.classList.toggle('dark', useDark);

    const button = $('#themeBtn');

    function syncThemeButton() {
        if (!button) return;
        const dark = document.body.classList.contains('dark');
        button.classList.toggle('is-dark', dark);
        button.title = dark ? 'Switch to light mode' : 'Switch to dark mode';
        button.setAttribute('aria-label', button.title);
    }

    syncThemeButton();

    button?.addEventListener('click', () => {
        document.body.classList.toggle('dark');
        localStorage.setItem(
            'inharitense-theme',
            document.body.classList.contains('dark') ? 'dark' : 'light'
        );
        syncThemeButton();

        if (window.__redrawDashboard) {
            window.__redrawDashboard(window.DASH);
        }
    });
}



/* =========================================================
   NOTIFICATIONS
   ========================================================= */

function initNotifications() {
    const button = $('#notifBtn');
    const panel = $('#notifPanel');

    button?.addEventListener(
        'click',
        () => {
            panel.classList.toggle('open');
            loadNotifications();
        }
    );

    loadNotifications();

    setInterval(
        loadNotifications,
        10000
    );
}


function loadNotifications() {
    secureFetch('/api/notifications')
        .then((response) => {
            if (!response.ok) throw new Error('Unable to load notifications');
            return response.json();
        })
        .then((payload) => {
            const list = Array.isArray(payload) ? payload : (payload.items || []);
            const badge = $('#notifBadge');
            const unread = Number(payload.unread_count ?? list.filter(item => !item.read_flag).length);
            if (badge) {
                badge.textContent = unread > 99 ? '99+' : String(unread);
                badge.style.display = unread ? 'inline-flex' : 'none';
                badge.setAttribute('aria-label', `${unread} unread notifications`);
            }
            const box = $('#notifList');
            if (!box) return;
            box.innerHTML = list.length ? list.map((item) => `
                <article class="notification ${item.read_flag ? '' : 'unread'}" data-notification-id="${Number(item.id)}">
                    <div class="notification-content" data-open-notification="${Number(item.id)}" data-target-url="${escapeHtml(item.target_url || ({low_stock:'/inventory',duplicate:'/inventory',request:'/requests',approval:'/requests',purchase_requisition:'/procurement?stage=approvals',transfer:'/asset-operations?view=circulation',maintenance:'/asset-operations?view=maintenance',procurement:'/procurement?stage=receiving'}[item.kind] || ''))}" role="button" tabindex="0" aria-label="Open notification: ${escapeHtml(item.title)}">
                        <b>${escapeHtml(item.title)}</b>
                        <p>${escapeHtml(item.message)}</p>
                        <small>${new Date(item.created_at).toLocaleString()}</small>
                    </div>
                    ${item.read_flag ? '<span class="notification-read-label">Read</span>' : `<button type="button" class="notification-read-button" data-mark-notification-read="${Number(item.id)}">Mark read</button>`}
                </article>
            `).join('') : '<div class="empty">No notifications.</div>';
        })
        .catch(() => {});
}

function markNotificationRead(notificationId, targetUrl = '') {
    secureFetch(`/api/notifications/${encodeURIComponent(notificationId)}/read`, { method: 'POST' })
        .then((response) => { if (!response.ok) throw new Error('Unable to mark notification as read'); return response.json(); })
        .then(() => {
            loadNotifications();
            const safeTarget = typeof targetUrl === 'string' && targetUrl.startsWith('/') && !targetUrl.startsWith('//') ? targetUrl : '';
            if (safeTarget) location.assign(safeTarget);
        })
        .catch(() => toast('Unable to update notification. Please try again.', 'error'));
}

function markNotificationsRead() {
    secureFetch('/api/notifications/read', { method: 'POST' })
        .then((response) => { if (!response.ok) throw new Error('Unable to mark notifications as read'); return response.json(); })
        .then(() => loadNotifications())
        .catch(() => toast('Unable to update notifications. Please try again.', 'error'));
}

function initProfileMenu() {
    const trigger = $('#profileMenuToggle');
    const menu = $('#profileMenu');
    if (!trigger || !menu) return;
    trigger.addEventListener('click', () => {
        const isOpen = trigger.getAttribute('aria-expanded') === 'true';
        trigger.setAttribute('aria-expanded', String(!isOpen));
        menu.hidden = isOpen;
    });
    document.addEventListener('click', (event) => {
        if (!event.target.closest('.profile-menu')) {
            trigger.setAttribute('aria-expanded', 'false');
            menu.hidden = true;
        }
    });
    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') { trigger.setAttribute('aria-expanded', 'false'); menu.hidden = true; }
    });
}

function initRequiredFieldHighlights() {
    document.addEventListener('invalid', (event) => {
        const field = event.target;
        if (field && field.matches('input,select,textarea')) field.classList.add('field-invalid');
    }, true);
    document.addEventListener('input', (event) => {
        const field = event.target;
        if (field?.matches('input,select,textarea') && field.checkValidity()) field.classList.remove('field-invalid');
    }, true);
    document.addEventListener('change', (event) => {
        const field = event.target;
        if (field?.matches('input,select,textarea') && field.checkValidity()) field.classList.remove('field-invalid');
    }, true);
}


/* =========================================================
   DASHBOARD
   ========================================================= */

function initDashboard() {

    if (
        !window.DASH ||
        typeof Chart === 'undefined'
    ) {
        return;
    }

    let charts = {};


    function draw(data) {

        window.DASH = data;

        Object.values(charts).forEach(
            (chart) => chart.destroy()
        );


        const darkTheme = document.body.classList.contains('dark');
        const chartText = darkTheme ? '#a9b7c6' : '#687584';
        const chartGrid = darkTheme ? 'rgba(255,255,255,.07)' : 'rgba(17,45,52,.07)';

        const common = {

            responsive: true,

            maintainAspectRatio: false,

            plugins: {
                legend: {
                    labels: {
                        color: chartText,
                        boxWidth: 9,
                        font: {
                            size: 10
                        }
                    }
                }
            },

            scales: {

                x: {
                    ticks: {
                        color: chartText,
                        font: {
                            size: 9
                        }
                    },

                    grid: {
                        display: false
                    }
                },

                y: {
                    beginAtZero: true,

                    ticks: {
                        color: chartText,
                        font: {
                            size: 9
                        }
                    },

                    grid: {
                        color: chartGrid
                    }
                }
            }
        };


        /* -----------------------------------------------------
           CATEGORY CHART
           ----------------------------------------------------- */

        charts.cat =
            new Chart(
                $('#categoryChart'),
                {
                    type: 'bar',

                    data: {

                        labels:
                            data.category_levels.map(
                                (item) =>
                                    item.category
                                        .replace(
                                            'PPE & Infection Control',
                                            'PPE & Infection'
                                        )
                                        .replace(
                                            'IT & BPO Equipment',
                                            'IT & BPO'
                                        )
                                        .replace(
                                            'Facility & Sanitation',
                                            'Facility & Sanit.'
                                        )
                            ),

                        datasets: [

                            {
                                label:
                                    'On hand',

                                data:
                                    data.category_levels.map(
                                        (item) =>
                                            item.qty
                                    ),

                                backgroundColor:
                                    '#2f8f68',

                                borderRadius:
                                    7
                            },

                            {
                                label:
                                    'Minimum',

                                data:
                                    data.category_levels.map(
                                        (item) =>
                                            item.min
                                    ),

                                backgroundColor:
                                    '#e8b52e',

                                borderRadius:
                                    7
                            }

                        ]
                    },

                    options: {
                        ...common,

                        scales: {
                            ...common.scales,

                            x: {
                                ...common.scales.x
                            },

                            y: {
                                ...common.scales.y
                            }
                        }
                    }
                }
            );


        /* -----------------------------------------------------
           MOVEMENT CHART
           ----------------------------------------------------- */

        charts.mov =
            new Chart(
                $('#movementChart'),
                {
                    type: 'line',

                    data: {

                        labels:
                            data.movements.map(
                                (item) =>
                                    item.label
                            ),

                        datasets: [

                            {
                                label:
                                    'Stock IN',

                                data:
                                    data.movements.map(
                                        (item) =>
                                            item.in
                                    ),

                                borderColor:
                                    '#2f8f68',

                                backgroundColor:
                                    'rgba(47,143,104,.10)',

                                fill:
                                    true,

                                tension:
                                    .35,

                                pointRadius:
                                    3
                            },

                            {
                                label:
                                    'Stock OUT',

                                data:
                                    data.movements.map(
                                        (item) =>
                                            item.out
                                    ),

                                borderColor:
                                    '#c75a4c',

                                backgroundColor:
                                    'rgba(199,90,76,.06)',

                                fill:
                                    true,

                                tension:
                                    .35,

                                pointRadius:
                                    3
                            }

                        ]
                    },

                    options: {
                        ...common,

                        elements: {
                            line: {
                                borderWidth: 2
                            }
                        }
                    }
                }
            );


        /* -----------------------------------------------------
           HEALTH CHART
           ----------------------------------------------------- */

        charts.health =
            new Chart(
                $('#healthChart'),
                {
                    type: 'doughnut',

                    data: {

                        labels: [
                            'Healthy',
                            'Reorder soon',
                            'Out of stock'
                        ],

                        datasets: [
                            {
                                data: [
                                    data.health.healthy,
                                    data.health.reorder,
                                    data.health.out
                                ],

                                backgroundColor: [
                                    '#2f8f68',
                                    '#e8b52e',
                                    '#d89a8e'
                                ],

                                borderWidth:
                                    0
                            }
                        ]
                    },

                    options: {

                        responsive:
                            true,

                        maintainAspectRatio:
                            true,

                        cutout:
                            '72%',

                        plugins: {

                            legend: {
                                display:
                                    false
                            }
                        }
                    }
                }
            );


        const total =
            data.total_items || 1;


        $('#healthPct').textContent =
            Math.round(
                data.health.healthy /
                total *
                100
            ) + '%';


        $('#hHealthy').textContent =
            data.health.healthy;


        $('#hReorder').textContent =
            data.health.reorder;


        $('#hOut').textContent =
            data.health.out;


        $('#movementCount').textContent =
            fmt(
                data.movements.reduce(
                    (total, item) =>
                        total + item.count,
                    0
                )
            ) +
            ' movements';


        $('#lastUpdate').textContent =
            new Date().toLocaleTimeString(
                [],
                {
                    hour: 'numeric',
                    minute: '2-digit',
                    second: '2-digit'
                }
            );


        $('#activity').innerHTML =
            data.recent.length

                ? data.recent.map(
                    (item) => `
                        <div class="activity-row">

                            <span class="move ${item.movement_type}">
                                ${item.movement_type === 'in' ? '↑' : '↓'}
                            </span>

                            <div>

                                <b>
                                    ${escapeHtml(item.name)}
                                </b>

                                <small>
                                    ${escapeHtml(item.by_name || 'System')}
                                    ·
                                    ${new Date(item.created_at).toLocaleString()}
                                </small>

                            </div>

                            <strong>
                                ${item.movement_type === 'in' ? '+' : '-'}${item.quantity}
                            </strong>

                        </div>
                    `
                ).join('')

                : `
                    <div class="empty">
                        No movements yet.
                    </div>
                `;
    }


    window.__redrawDashboard =
        draw;


    draw(
        window.DASH
    );


    setInterval(
        () => {

            secureFetch(
                '/api/dashboard'
            )
                .then(
                    (response) =>
                        response.json()
                )
                .then(draw)
                .catch(() => {});

        },
        5000
    );
}


/* =========================================================
   INVENTORY FILTER
   ========================================================= */

function initInventoryFilter() {

    const search =
        $('#search');

    const category =
        $('#cat');


    function run() {

        document
            .querySelectorAll(
                '#inv tbody tr'
            )
            .forEach(
                (row) => {

                    const searchMatch =
                        !search.value ||
                        row.dataset.search.includes(
                            search.value.toLowerCase()
                        );


                    const categoryMatch =
                        !category.value ||
                        row.dataset.cat ===
                            category.value;


                    row.style.display =
                        searchMatch &&
                        categoryMatch
                            ? ''
                            : 'none';
                }
            );
    }


    search?.addEventListener(
        'input',
        run
    );


    category?.addEventListener(
        'change',
        run
    );
}


/* =========================================================
   QUICK STOCK MOVEMENT
   ========================================================= */

function quickMove(id, type) { openMovementModal(id, type); }

const uiModalFocus = new Map();
function openUiModal(id) {
    const modal = document.getElementById(id);
    if (!modal) return;
    uiModalFocus.set(id, document.activeElement);
    modal.classList.add('open');
    modal.setAttribute('aria-hidden', 'false');
    requestAnimationFrame(() => modal.querySelector('input:not([type="hidden"]),select,button')?.focus());
}
function closeUiModal(id) {
    const modal = document.getElementById(id);
    modal?.classList.remove('open');
    modal?.setAttribute('aria-hidden', 'true');
    uiModalFocus.get(id)?.focus();
}
function openMovementModal(id, type) {
    const form = $('#movementForm');
    if (!form) return;
    form.reset();
    if (id) $('#moveItem').value = String(id);
    if (type) $('#moveType').value = type;
    updateMovementContext();
    openUiModal('stockMovementModal');
    $('#moveQty').focus();
}
function closeMovementModal() { closeUiModal('stockMovementModal'); }
function updateMovementContext() {
    const option = $('#moveItem')?.selectedOptions[0];
    if (!option) return;
    $('#stockMovementContext').textContent = `${option.dataset.name} · Current stock: ${option.dataset.qty} ${option.dataset.unit}`;
    $('#stockMovementTitle').textContent = $('#moveType').value === 'out' ? 'Issue stock · Stock OUT' : 'Receive stock · Stock IN';
    $('#moveQty').max = $('#moveType').value === 'out' ? option.dataset.qty : '';
}
function openScanLookup() { openUiModal('scanLookupModal'); }
// Trap focus only in the new dialogs; existing scanner/vendor behavior stays intact.
document.addEventListener('keydown', (event) => {
    const modal = document.querySelector('#stockMovementModal.open, #scanLookupModal.open, #auditUnsavedModal.open');
    if (!modal) return;
    if (event.key === 'Escape') { event.preventDefault(); closeUiModal(modal.id); }
    if (event.key !== 'Tab') return;
    const nodes = [...modal.querySelectorAll('button,input:not([type="hidden"]),select,a[href]')].filter(e => !e.disabled && e.getClientRects().length);
    const first = nodes[0], last = nodes[nodes.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
});

/* =========================================================
   MOVEMENT FORM
   ========================================================= */

function initMovementForm() {

    $('#movementForm')?.addEventListener(
        'submit',
        (event) => {

            event.preventDefault();


            const body = {

                inventory_id:
                    $('#moveItem').value,

                movement_type:
                    $('#moveType').value,

                quantity:
                    $('#moveQty').value,

                note:
                    $('#moveNote').value
            };


            secureFetch(
                '/api/movement',
                {
                    method: 'POST',

                    headers: {
                        'Content-Type':
                            'application/json'
                    },

                    body:
                        JSON.stringify(body)
                }
            )
                .then(
                    (response) =>
                        response.json()
                            .then(
                                (data) => ({
                                    ok:
                                        response.ok,

                                    data
                                })
                            )
                )
                .then(
                    ({ ok, data }) => {

                        if (!ok) {
                            throw new Error(
                                data.error
                            );
                        }


                        toast(
                            data.message,
                            'success'
                        );


                        event.target.reset();


                        setTimeout(
                            () =>
                                location.reload(),
                            350
                        );
                    }
                )
                .catch(
                    (error) =>
                        toast(
                            error.message,
                            'error'
                        )
                );
        }
    );
}


/* =========================================================
   INVENTORY CATEGORY NAVIGATION
   ========================================================= */

function initInventoryNavigation() {

    const category =
        $('#cat');

    const cards = [
        ...document.querySelectorAll(
            '#inventoryCategoryCards .inventory-category-card'
        )
    ];

    const movement =
        $('#moveItem');


    if (!category) {
        return;
    }


    function syncMovement() {

        if (!movement) {
            return;
        }


        const selected =
            category.value;


        const options = [
            ...movement.options
        ];


        options.forEach(
            (option) => {

                option.hidden =
                    !!selected &&
                    option.dataset.category !==
                        selected;
            }
        );


        const current =
            movement.selectedOptions[0];


        if (current?.hidden) {

            const first =
                options.find(
                    (option) =>
                        !option.hidden
                );


            if (first) {
                movement.value =
                    first.value;
            }
        }
    }


    function applyCategory(
        value
    ) {

        category.value =
            value;


        cards.forEach(
            (card) => {

                card.classList.toggle(
                    'active',
                    card.dataset.category ===
                        value
                );
            }
        );


        category.dispatchEvent(
            new Event('change')
        );


        syncMovement();


        const params =
            new URLSearchParams(
                window.location.search
            );


        if (value) {
            params.set(
                'category',
                value
            );
        } else {
            params.delete(
                'category'
            );
        }


        const next =
            params.toString();


        history.replaceState(
            null,
            '',
            window.location.pathname +
            (
                next
                    ? '?' + next
                    : ''
            )
        );
    }


    cards.forEach(
        (card) => {

            card.addEventListener(
                'click',
                () =>
                    applyCategory(
                        card.dataset.category
                    )
            );
        }
    );


    category.addEventListener(
        'change',
        () => {

            cards.forEach(
                (card) => {

                    card.classList.toggle(
                        'active',
                        card.dataset.category ===
                            category.value
                    );
                }
            );


            syncMovement();
        }
    );


    const initial =
        new URLSearchParams(
            window.location.search
        ).get('category') || '';


    if (
        [
            ...category.options
        ].some(
            (option) =>
                option.value ===
                initial
        )
    ) {
        category.value =
            initial;
    }


    cards.forEach(
        (card) => {

            card.classList.toggle(
                'active',
                card.dataset.category ===
                    category.value
            );
        }
    );


    syncMovement();
}


/* =========================================================
   INVENTORY MODAL
   ========================================================= */

function openItemModal(item) {

    const modal =
        $('#itemModal');

    const form =
        $('#itemForm');


    form.reset();
    form.querySelectorAll('.form-section').forEach((section, index) => section.open = index === 0);
    if (!item) form.dispatchEvent(new Event('ecmci:restore-draft'));


    $('#itemId').value =
        '';


    $('#modalTitle').textContent =
        item
            ? 'Edit item'
            : 'Add item';


    if (item) {

        Object.keys(item)
            .forEach(
                (key) => {

                    const element =
                        form.elements[key];


                    if (element) {

                        element.value =
                            item[key] ?? '';
                    }
                }
            );


        $('#itemId').value =
            item.id;
    }


    form.elements.qty.readOnly = Boolean(item);
    form.elements.qty.title = item ? 'Use Stock IN / OUT to change quantity.' : 'Opening stock';
    modal.classList.add('open');
    modal.setAttribute('aria-hidden', 'false');
}


function closeItemModal() {
    const modal = $('#itemModal');
    modal?.classList.remove('open');
    modal?.setAttribute('aria-hidden', 'true');
}


function editItem(item) {
    openItemModal(item);
}


function editItemById(id) {

    const row =
        document
            .querySelector(
                `.qty[data-id="${id}"]`
            )
            ?.closest('tr');


    const small =
        row?.querySelector(
            'td:first-child small'
        );


    const itemNo =
        small
            ?.textContent
            ?.split(' · ')[0]
            ?.trim();


    if (!itemNo) {

        toast(
            'Unable to find this inventory item.',
            'error'
        );

        return;
    }


    secureFetch(
        '/api/scan?q=' +
        encodeURIComponent(
            itemNo
        )
    )
        .then(
            (response) =>
                response.json()
                    .then(
                        (data) => ({
                            ok:
                                response.ok,

                            data
                        })
                    )
        )
        .then(
            ({ ok, data }) => {

                if (
                    !ok ||
                    !data.item
                ) {

                    throw new Error(
                        'Unable to load this inventory item.'
                    );
                }


                openItemModal(
                    data.item
                );
            }
        )
        .catch(
            (error) =>
                toast(
                    error.message,
                    'error'
                )
        );
}


/* =========================================================
   INVENTORY SAVE
   ========================================================= */

$('#itemForm')?.addEventListener(
    'submit',
    (event) => {

        event.preventDefault();


        const formData =
            new FormData(
                event.target
            );


        secureFetch(
            '/api/inventory',
            {
                method: 'POST',
                body: formData
            }
        )
            .then(
                (response) =>
                    response.json()
                        .then(
                            (data) => ({
                                ok:
                                    response.ok,

                                data
                            })
                        )
            )
            .then(
                ({ ok, data }) => {

                    if (!ok) {

                        throw new Error(
                            data.error
                        );
                    }


                    toast(
                        data.message,
                        'success'
                    );
                    event.target.dispatchEvent(new Event('ecmci:draft-submitted'));

                    closeItemModal();


                    setTimeout(
                        () =>
                            location.reload(),
                        350
                    );
                }
            )
            .catch(
                (error) =>
                    toast(
                        error.message,
                        'error'
                    )
            );
    }
);


/* =========================================================
   DELETE INVENTORY ITEM
   ========================================================= */

let pendingInventoryDeletion = null;

function deleteItem(id, name) {
    const modal = document.getElementById('deleteInventoryModal');
    if (!modal) return; // Non-Super Users must never be offered this action.
    pendingInventoryDeletion = { id, name: String(name || 'this item') };
    document.getElementById('deleteInventoryItemName').textContent = pendingInventoryDeletion.name;
    document.getElementById('deleteInventoryForm').reset();
    const error = document.getElementById('deleteInventoryError');
    error.textContent = '';
    error.hidden = true;
    openUiModal('deleteInventoryModal');
    document.getElementById('deleteInventoryReason').focus();
}

function closeInventoryDeleteModal() {
    const submit = document.getElementById('deleteInventorySubmit');
    if (submit?.disabled) return;
    closeUiModal('deleteInventoryModal');
    pendingInventoryDeletion = null;
}

document.getElementById('deleteInventoryForm')?.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (!pendingInventoryDeletion) return;
    const reason = document.getElementById('deleteInventoryReason').value.trim();
    const error = document.getElementById('deleteInventoryError');
    if (reason.length < 10 || reason.length > 1000) {
        error.textContent = 'Please enter a reason between 10 and 1000 characters.';
        error.hidden = false;
        return;
    }
    const submit = document.getElementById('deleteInventorySubmit');
    submit.disabled = true;
    submit.textContent = 'Deleting…';
    error.hidden = true;
    try {
        const response = await secureFetch(`/api/inventory/${encodeURIComponent(pendingInventoryDeletion.id)}`, {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ reason })
        });
        if (response.redirected && /\/login(?:\?|$)/.test(response.url)) {
            throw new Error('Your session has expired. Sign in again to continue.');
        }
        const payload = await response.json().catch(() => ({}));
        if (!response.ok || payload.ok !== true) {
            throw new Error(payload.error || `Deletion failed (HTTP ${response.status}).`);
        }
        closeUiModal('deleteInventoryModal');
        pendingInventoryDeletion = null;
        toast(payload.message || 'Inventory item removed.', 'success');
        setTimeout(() => location.reload(), 550);
    } catch (failure) {
        error.textContent = failure.message || 'Deletion failed; please try again.';
        error.hidden = false;
    } finally {
        submit.disabled = false;
        submit.textContent = 'Delete item';
    }
});


/* =========================================================
   SCANNER
   ========================================================= */

function scanItem() {

    const input =
        $('#scan');


    const query =
        input?.value.trim();


    if (!query) {
        return;
    }


    secureFetch(
        '/api/scan?q=' +
        encodeURIComponent(
            query
        )
    )
        .then(
            (response) =>
                response.json()
                    .then(
                        (data) => ({
                            ok:
                                response.ok,

                            data
                        })
                    )
        )
        .then(
            ({ ok, data }) => {

                if (!ok) {

                    throw new Error(
                        'No matching item found or you do not have access.'
                    );
                }


                $('#scanResult').innerHTML = `

                    <b>
                        ${escapeHtml(
                            data.item.item_no
                        )}
                    </b>

                    ·

                    ${escapeHtml(
                        data.item.name
                    )}

                    ·

                    <strong>
                        ${data.item.qty}
                        ${escapeHtml(
                            data.item.unit
                        )}
                    </strong>

                    on hand

                `;


                const select =
                    $('#moveItem');


                if (select) {
                    select.value =
                        data.item.id;
                }
            }
        )
        .catch(
            (error) => {

                $('#scanResult')
                    .textContent =
                    error.message;
            }
        );
}


let scannerStream =
    null;

let scanTimer =
    null;


async function startScanner() {

    const modal =
        $('#scannerModal');


    modal.classList.add(
        'open'
    );


    const video =
        $('#scannerVideo');


    const status =
        $('#scannerStatus');


    try {

        if (
            !navigator.mediaDevices?.getUserMedia
        ) {

            throw new Error(
                'Camera access is not supported in this browser.'
            );
        }


        scannerStream =
            await navigator.mediaDevices.getUserMedia(
                {
                    video: {
                        facingMode: {
                            ideal:
                                'environment'
                        }
                    }
                }
            );


        video.srcObject =
            scannerStream;


        if (
            'BarcodeDetector' in window
        ) {

            const detector =
                new BarcodeDetector(
                    {
                        formats: [
                            'qr_code',
                            'code_128',
                            'code_39',
                            'ean_13',
                            'ean_8',
                            'upc_a',
                            'upc_e'
                        ]
                    }
                );


            const scan =
                async () => {

                    if (!scannerStream) {
                        return;
                    }


                    try {

                        const codes =
                            await detector.detect(
                                video
                            );


                        if (codes.length) {

                            const value =
                                codes[0]
                                    .rawValue;


                            $('#scan').value =
                                value;


                            stopScanner();


                            scanItem();


                            return;
                        }

                    } catch {
                        // Continue scanning.
                    }


                    scanTimer =
                        requestAnimationFrame(
                            scan
                        );
                };


            scan();

        } else {

            status.textContent =
                'Camera is open, but this browser does not expose BarcodeDetector. Use the manual code field or Demo scan.';
        }

    } catch (error) {

        status.textContent =
            error.message +
            ' Use Demo scan or manual code entry.';
    }
}


function stopScanner() {

    if (scanTimer) {

        cancelAnimationFrame(
            scanTimer
        );

        scanTimer =
            null;
    }


    if (scannerStream) {

        scannerStream
            .getTracks()
            .forEach(
                (track) =>
                    track.stop()
            );

        scannerStream =
            null;
    }


    $('#scannerModal')
        ?.classList.remove(
            'open'
        );
    if ($('#scanLookupModal')) openUiModal('scanLookupModal');
}


function demoScan() {

    const first =
        document.querySelector(
            '#moveItem option'
        );


    if (!first) {
        return;
    }


    $('#scan').value =
        first.textContent
            .split(' · ')[0];


    stopScanner();

    scanItem();
}


/* =========================================================
   AI DEMAND FORECAST
   ========================================================= */

function initForecast() {

    const itemCards = [
        ...document.querySelectorAll(
            '.forecast-item-card'
        )
    ];


    const categoryGroups = [
        ...document.querySelectorAll(
            '.forecast-category-group'
        )
    ];


    const categoryButtons = [
        ...document.querySelectorAll(
            '.forecast-category'
        )
    ];


    const search =
        $('#forecastSearch');


    const canvas =
        $('#forecastChart');


    const output =
        $('#forecastOutput');


    const empty =
        $('#forecastEmpty');


    const selectedName =
        $('#forecastSelectedName');


    const selectedMeta =
        $('#forecastSelectedMeta');


    const selectedBadge =
        $('#forecastSelectedBadge');


    const totalIn =
        $('#forecastTotalIn');


    const totalOut =
        $('#forecastTotalOut');


    const activityDays =
        $('#forecastActivityDays');


    const leadInput =
        $('#fcLead');


    const safetyInput =
        $('#fcSafety');


    if (!itemCards.length) {
        return;
    }


    let chart =
        null;


    let selectedId =
        null;


    let loadTimer =
        null;


    let requestVersion =
        0;


    function getSettings() {

        let lead =
            Number(
                leadInput?.value
            );


        let safety =
            Number(
                safetyInput?.value
            );


        if (
            !Number.isFinite(lead) ||
            lead < 0
        ) {
            lead = 5;
        }


        if (
            !Number.isFinite(safety) ||
            safety < 0
        ) {
            safety = 3;
        }


        return {
            lead,
            safety
        };
    }


    function closeOtherCategories(
        current
    ) {

        categoryGroups.forEach(
            (group) => {

                if (
                    group ===
                    current
                ) {
                    return;
                }


                const button =
                    group.querySelector(
                        '.forecast-category'
                    );


                const items =
                    group.querySelector(
                        '.forecast-category-items'
                    );


                if (items) {
                    items.hidden =
                        true;
                }


                if (button) {

                    button.classList.remove(
                        'active'
                    );


                    button.setAttribute(
                        'aria-expanded',
                        'false'
                    );
                }
            }
        );
    }


    function openCategory(
        group
    ) {

        const button =
            group.querySelector(
                '.forecast-category'
            );


        const items =
            group.querySelector(
                '.forecast-category-items'
            );


        if (
            !button ||
            !items
        ) {
            return;
        }


        const opening =
            items.hidden;


        closeOtherCategories(
            group
        );


        items.hidden =
            !opening;


        button.classList.toggle(
            'active',
            opening
        );


        button.setAttribute(
            'aria-expanded',
            opening
                ? 'true'
                : 'false'
        );


        if (opening) {

            group.scrollIntoView(
                {
                    behavior:
                        'smooth',

                    block:
                        'nearest'
                }
            );
        }


        filterItems();
    }


    function filterItems() {

        const query =
            (
                search?.value ||
                ''
            )
                .trim()
                .toLowerCase();


        let visible =
            0;


        categoryGroups.forEach(
            (group) => {

                const items =
                    group.querySelector(
                        '.forecast-category-items'
                    );


                const button =
                    group.querySelector(
                        '.forecast-category'
                    );


                const cards = [
                    ...group.querySelectorAll(
                        '.forecast-item-card'
                    )
                ];


                let groupVisible =
                    0;


                cards.forEach(
                    (card) => {

                        const match =
                            !query ||
                            (
                                card.dataset.search ||
                                ''
                            ).includes(
                                query
                            );


                        card.hidden =
                            !match;


                        card.classList.toggle(
                            'selected',
                            card.dataset.id ===
                                selectedId
                        );


                        if (match) {
                            groupVisible++;
                        }
                    }
                );


                if (
                    query &&
                    groupVisible > 0
                ) {

                    items.hidden =
                        false;


                    button.classList.add(
                        'active'
                    );


                    button.setAttribute(
                        'aria-expanded',
                        'true'
                    );

                } else if (
                    query &&
                    groupVisible === 0
                ) {

                    items.hidden =
                        true;


                    button.classList.remove(
                        'active'
                    );


                    button.setAttribute(
                        'aria-expanded',
                        'false'
                    );
                }


                visible +=
                    groupVisible;
            }
        );


        if (empty) {

            empty.hidden =
                visible !== 0;
        }
    }


    function selectItem(
        id
    ) {

        const card =
            itemCards.find(
                (item) =>
                    item.dataset.id ===
                    String(id)
            );


        if (!card) {
            return;
        }


        selectedId =
            String(id);


        itemCards.forEach(
            (item) => {

                item.classList.toggle(
                    'selected',
                    item.dataset.id ===
                        selectedId
                );
            }
        );


        const group =
            card.closest(
                '.forecast-category-group'
            );


        if (group) {

            const items =
                group.querySelector(
                    '.forecast-category-items'
                );


            const button =
                group.querySelector(
                    '.forecast-category'
                );


            closeOtherCategories(
                group
            );


            if (items) {
                items.hidden =
                    false;
            }


            if (button) {

                button.classList.add(
                    'active'
                );


                button.setAttribute(
                    'aria-expanded',
                    'true'
                );
            }
        }


        selectedName.textContent =
            card.querySelector(
                'strong'
            )
                ?.textContent
                ?.trim() ||
            'Inventory item';


        selectedMeta.textContent =
            (
                card.querySelector(
                    'small'
                )
                    ?.textContent
                    ?.trim() ||
                ''
            ) +
            ' · Loading transaction history...';


        selectedBadge.textContent =
            'Updating forecast...';


        scheduleLoadForecast();
    }


    function scheduleLoadForecast() {

        clearTimeout(
            loadTimer
        );


        loadTimer =
            setTimeout(
                loadForecast,
                120
            );
    }


    let samplePreview = false;
    $('#forecastDemoButton')?.addEventListener('click', () => {
        samplePreview = true;
        if (!selectedId && itemCards.length) selectItem(itemCards[0].dataset.id);
        loadForecast();
    });
    $('#forecastLiveButton')?.addEventListener('click', () => { samplePreview = false; loadForecast(); });

    async function loadForecast() {
        if (!selectedId) return;
        const version = ++requestVersion, settings = getSettings();
        try {
            const response = await secureFetch(`/api/${samplePreview ? 'forecast-demo' : 'forecast'}/${encodeURIComponent(selectedId)}?lead=${settings.lead}&safety=${settings.safety}`);
            const data = await response.json();
            if (version !== requestVersion) return;
            if (!response.ok) throw new Error(data.error || 'Unable to load forecast.');
            const isDemo = data.is_demo === true;
            $('#forecastDemoBanner').hidden = !isDemo;
            $('#forecastSourceLabel').textContent = isDemo ? 'SAMPLE FORECAST · DEMONSTRATION' : 'LIVE FORECAST';
            $('#forecastDemoDisclaimer').textContent = data.disclaimer || '';
            $('#forecastDemoButton').textContent = isDemo ? 'Sample preview active' : 'Preview with sample data';
            const f = data.forecast, unit = escapeHtml(data.item.unit), stock = Number(data.item.qty);
            const sufficient = f.data_status === 'Sufficient data';
            const weekly = Number(f.predicted_weekly || 0), daily = Number(f.daily || 0);
            const runsOut = daily > 0 ? Math.max(0, Math.floor(stock / daily)) : null;
            const active = Number(f.active_weeks || 0), fit = Number(f.r2 || 0);
            const reliability = sufficient && active >= 12 && fit >= .7 ? 'High' : sufficient && active >= 6 && fit >= .35 ? 'Medium' : 'Low';
            const urgent = !!f.urgent || stock === 0;
            const soon = sufficient && !urgent && daily > 0 && Number(f.days_to_reorder) <= 7;
            const status = urgent ? 'Reorder now' : soon ? 'Order soon' : sufficient ? 'Stock is fine' : 'Not enough history';
            const statusClass = urgent ? 'out' : soon || !sufficient ? 'low' : 'ok';
            selectedName.textContent = data.item.name;
            selectedMeta.textContent = `${isDemo ? 'SAMPLE DATA · ' : ''}${data.item.item_no} · ${stock} ${data.item.unit} on hand`;
            selectedBadge.textContent = `${isDemo ? 'Demo · ' : ''}${status}`;
            selectedBadge.className = `forecast-selected-badge status ${statusClass}`;
            const history = Array.isArray(f.history_weeks) ? f.history_weeks.slice(-8) : [];
            const labels = history.map((_, i) => i === history.length - 1 ? 'Last week' : `${history.length - i} weeks ago`);
            labels.push('Next week');
            chart?.destroy(); chart = null;
            if (typeof Chart !== 'undefined') {
                const theme = getComputedStyle(document.body), color = token => theme.getPropertyValue(token).trim();
                chart = new Chart(canvas, {
                    type: 'line',
                    data: { labels, datasets: [
                        { label: 'Past usage', data: [...history, null], borderColor: color('--green'), tension: .2, pointRadius: 3 },
                        { label: 'Forecast', data: [...history.slice(0, -1).map(() => null), history.at(-1) ?? 0, sufficient ? weekly : null], borderColor: color('--yellow'), borderDash: [6,4], pointRadius: 4 }
                    ]},
                    options: { animation: false, responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: {
                        x: { ticks: { color: color('--muted'), font: { size: 12 }, maxTicksLimit: 5 }, grid: { display: false } },
                        y: { beginAtZero: true, ticks: { color: color('--muted'), precision: 0, font: { size: 12 } }, grid: { color: color('--line') } }
                    }}
                });
            }
            totalIn.textContent = history.at(-1) ?? 0;
            totalOut.textContent = sufficient ? weekly : '—';
            activityDays.textContent = active;
            const summary = sufficient
                ? `You'll likely need about <b>${weekly} ${unit} per week</b>. ${runsOut === null ? 'Recent usage is too low to estimate a run-out date.' : `At this rate, your current stock covers about <b>${runsOut} days</b>.`} ${Number(f.recommended)>0 ? `Suggested reorder: <b>${Number(f.recommended)} ${unit}</b>.` : 'No order quantity is recommended right now.'}`
                : `We need usage recorded in at least four complete weeks before estimating demand. Keep recording Stock OUT transactions. Your minimum stock threshold is used until enough history is available. ${urgent ? 'Your stock is at or below its minimum; review replenishment now.' : 'Stock is above the configured minimum.'} Use “Preview with sample data” to demonstrate the calculation without changing actual records.`;
            output.innerHTML = `
                <div class="eyebrow">${isDemo ? 'SAMPLE OUTLOOK · DEMONSTRATION ONLY' : 'YOUR STOCK OUTLOOK'}</div>
                <h3>${escapeHtml(data.item.name)}</h3>
                <div class="forecast-verdict ${urgent || soon ? 'urgent' : ''}"><span class="status ${statusClass}">${status}</span><p class="forecast-summary">${summary}</p></div>
                <div class="note prediction-reliability"><b>How reliable is this prediction? ${reliability}</b><p>This label reflects available history and consistency of the usage trend. It is a guide, not a tested accuracy score or a guarantee.</p></div>
                <details class="form-section"><summary>How this works</summary><div class="details-body">We look at your past weekly usage, follow its trend, and combine it with recent usage. Supplier delivery time and your safety stock help decide when to reorder. You approve any purchase yourself.</div></details>
                <details class="form-section"><summary>Technical details</summary><div class="details-body"><dl class="technical-list"><dt>Model</dt><dd>${escapeHtml(f.model)}</dd><dt>Model fit (R²)</dt><dd>${fit}</dd><dt>Complete weeks examined</dt><dd>${f.sample_weeks}</dd><dt>Weeks with recorded usage</dt><dd>${active}</dd><dt>Data status</dt><dd>${escapeHtml(f.data_status)}</dd><dt>Reorder threshold</dt><dd>${f.reorder_point} ${unit}</dd><dt>Lead time / safety stock</dt><dd>${f.lead_time} days / ${f.safety} ${unit}</dd></dl></div></details>`;
        } catch (error) {
            if (version !== requestVersion) return;
            $('#forecastDemoBanner').hidden = !samplePreview;
            $('#forecastSourceLabel').textContent = samplePreview ? 'SAMPLE PREVIEW UNAVAILABLE' : 'LIVE FORECAST';
            selectedMeta.textContent = 'Unable to load this outlook. Please retry.';
            chart?.destroy(); chart = null;
            totalIn.textContent = totalOut.textContent = activityDays.textContent = '—';
            selectedBadge.textContent = 'Forecast unavailable';
            output.innerHTML = `<div class="forecast-placeholder"><h3>Unable to load forecast</h3><p>${escapeHtml(error.message)}</p></div>`;
        }
    }

    /* =====================================================
       FORECAST CATEGORY BUTTONS
       ===================================================== */

    categoryButtons.forEach(
        (button) => {

            button.addEventListener(
                'click',
                () => {

                    const group =
                        button.closest(
                            '.forecast-category-group'
                        );


                    if (group) {

                        openCategory(
                            group
                        );
                    }
                }
            );
        }
    );


    /* =====================================================
       FORECAST ITEM BUTTONS
       ===================================================== */

    itemCards.forEach(
        (card) => {

            card.addEventListener(
                'click',
                () => {

                    selectItem(
                        card.dataset.id
                    );


                    document
                        .querySelector(
                            '.forecast-workspace'
                        )
                        ?.scrollIntoView(
                            {
                                behavior:
                                    'smooth',

                                block:
                                    'start'
                            }
                        );
                }
            );
        }
    );


    /* =====================================================
       FORECAST SEARCH
       ===================================================== */

    search?.addEventListener(
        'input',
        filterItems
    );


    /* =====================================================
       LIVE FORECAST SETTINGS
       ===================================================== */

    [
        leadInput,
        safetyInput
    ].forEach(
        (input) => {

            input?.addEventListener(
                'input',
                scheduleLoadForecast
            );


            input?.addEventListener(
                'change',
                scheduleLoadForecast
            );
        }
    );


    /* =====================================================
       INITIAL FORECAST STATE
       ===================================================== */

    categoryGroups.forEach(
        (group) => {

            const items =
                group.querySelector(
                    '.forecast-category-items'
                );


            if (items) {

                items.hidden =
                    true;
            }
        }
    );


    filterItems();
}


/* =========================================================
   VENDORS
   ========================================================= */

function initVendors() {

    const modal =
        document.querySelector(
            '#vendorEditModal'
        );


    const form =
        document.querySelector(
            '#vendorEditForm'
        );


    if (
        !modal ||
        !form
    ) {
        return;
    }


    const name =
        document.querySelector(
            '#vendorEditName'
        );


    const category =
        document.querySelector(
            '#vendorEditCategory'
        );


    const supplies =
        document.querySelector(
            '#vendorEditSupplies'
        );


    const status =
        document.querySelector(
            '#vendorEditStatus'
        );


    const contact =
        document.querySelector(
            '#vendorEditContact'
        );


    const email =
        document.querySelector(
            '#vendorEditEmail'
        );


    function closeModal() {

        modal.classList.remove(
            'open'
        );


        modal.setAttribute(
            'aria-hidden',
            'true'
        );


        document.body.classList.remove(
            'modal-open'
        );
    }


    function openModal(
        button
    ) {

        const id =
            button.dataset.id;


        form.action =
            '/vendors/' +
            encodeURIComponent(
                id
            ) +
            '/update';


        name.value =
            button.dataset.name ||
            '';


        category.value =
            button.dataset.category ||
            '';


        supplies.value =
            button.dataset.supplies ||
            '';


        status.value =
            button.dataset.status ||
            'Active';


        contact.value =
            button.dataset.contact ||
            '';


        email.value =
            button.dataset.email ||
            '';


        modal.classList.add(
            'open'
        );


        modal.setAttribute(
            'aria-hidden',
            'false'
        );


        document.body.classList.add(
            'modal-open'
        );


        setTimeout(
            () =>
                name.focus(),
            50
        );
    }


    document
        .querySelectorAll(
            '.vendor-edit-btn'
        )
        .forEach(
            (button) => {

                button.addEventListener(
                    'click',
                    () =>
                        openModal(
                            button
                        )
                );
            }
        );


    modal
        .querySelectorAll(
            '[data-close-vendor-modal]'
        )
        .forEach(
            (button) => {

                button.addEventListener(
                    'click',
                    closeModal
                );
            }
        );


    document.addEventListener(
        'keydown',
        (event) => {

            if (
                event.key ===
                    'Escape' &&
                modal.classList.contains(
                    'open'
                )
            ) {

                closeModal();
            }
        }
    );


    document
        .querySelectorAll(
            '.vendor-delete-form'
        )
        .forEach(
            (formElement) => {

                formElement.addEventListener(
                    'submit',
                    (event) => {

                        const row =
                            formElement.closest(
                                'tr'
                            );


                        const vendor =
                            row
                                ?.querySelector(
                                    '.vendor-name-cell b'
                                )
                                ?.textContent
                                ?.trim() ||
                            'this vendor';


                        if (
                            !confirm(
                                `Delete ${vendor}? This vendor will be permanently removed from the masterlist.`
                            )
                        ) {

                            event.preventDefault();
                        }
                    }
                );
            }
        );
}


/* =========================================================
   GLOBAL INITIALIZATION
   ========================================================= */

initTheme();

initNotifications();
initProfileMenu();
initRequiredFieldHighlights();
document.getElementById('notifList')?.addEventListener('click', (event) => {
    const button = event.target.closest('[data-mark-notification-read]');
    if (button) {
        event.stopPropagation();
        markNotificationRead(button.dataset.markNotificationRead);
        return;
    }
    const opened = event.target.closest('[data-open-notification]');
    if (opened) markNotificationRead(opened.dataset.openNotification, opened.dataset.targetUrl || '');
});
document.getElementById('notifList')?.addEventListener('keydown', (event) => {
    const opened = event.target.closest('[data-open-notification]');
    if (!opened || !['Enter', ' '].includes(event.key)) return;
    event.preventDefault();
    markNotificationRead(opened.dataset.openNotification, opened.dataset.targetUrl || '');
});

function initAuditDraft() {
    const form = document.getElementById('auditForm');
    if (!form || form.dataset.finalized === 'true') return;
    let baseline = snapshot(), dirty = false, leavingTo = null, submitting = false;
    function snapshot() { return JSON.stringify([...new FormData(form)].filter(([k]) => k !== '_csrf' && k !== 'draft_revision')); }
    form.addEventListener('input', () => { dirty = snapshot() !== baseline; });
    form.addEventListener('change', () => { dirty = snapshot() !== baseline; });
    window.addEventListener('beforeunload', event => { if (dirty) { event.preventDefault(); event.returnValue = ''; } });
    document.addEventListener('click', event => {
        const link = event.target.closest('a[href]');
        if (!dirty || !link || link.target === '_blank' || event.ctrlKey || event.metaKey || link.hash || link.origin !== location.origin) return;
        event.preventDefault(); leavingTo = link.href; openUiModal('auditUnsavedModal');
    });
    async function save(action, leave = false) {
        if (submitting) return;
        submitting = true;
        const payload = new FormData(form); payload.set('audit_action', action);
        // Leave fields editable, but keep edits made during the request marked dirty.
        const submitted = snapshot();
        const buttons = [...form.querySelectorAll('button'), document.getElementById('auditSaveLeave')];
        buttons.forEach(b => { if (b) b.disabled = true; });
        const errorBox = document.getElementById('auditFormError'); errorBox.hidden = true;
        try {
            const response = await secureFetch(form.action, { method: 'POST', headers: { Accept: 'application/json' }, body: payload });
            const result = await response.json();
            if (!response.ok) {
                form.querySelectorAll('[aria-invalid="true"]').forEach(el => { el.removeAttribute('aria-invalid'); el.classList.remove('field-invalid'); });
                Object.entries(result.field_errors || {}).forEach(([name, message]) => {
                    const field = [...form.elements].find(el => el.name === name);
                    if (field) { field.setAttribute('aria-invalid', 'true'); field.classList.add('field-invalid'); field.setAttribute('title', message); }
                });
                throw new Error(result.error || 'Audit could not be saved.');
            }
            form.elements.draft_revision.value = result.revision;
            baseline = submitted; dirty = snapshot() !== baseline;
            document.getElementById('auditSaveStatus').textContent = result.message + ' ' + result.saved_at;
            toast(result.message, 'success');
            if (result.finalized) { dirty = false; location.reload(); }
            else if (leave && !dirty) { dirty = false; location.assign(leavingTo || document.getElementById('auditBack').href); }
            else {
                closeUiModal('auditUnsavedModal');
                if (action === 'draft') openUiModal('auditDraftSavedModal');
            }
        } catch (error) { errorBox.textContent = error.message; errorBox.hidden = false; toast(error.message, 'error'); }
        finally { submitting = false; buttons.forEach(b => { if (b) b.disabled = false; }); }
    }
    form.addEventListener('submit', event => { event.preventDefault(); save(event.submitter?.value || 'draft'); });
    document.getElementById('auditStay').onclick = () => closeUiModal('auditUnsavedModal');
    document.getElementById('auditLeave').onclick = () => { dirty = false; location.assign(leavingTo || document.getElementById('auditBack').href); };
    document.getElementById('auditSaveLeave').onclick = () => save('draft', true);
    document.getElementById('auditDraftContinue')?.addEventListener('click', () => closeUiModal('auditDraftSavedModal'));
}
