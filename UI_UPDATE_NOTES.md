# ECMCI UI replacement

This package contains only CSS and three templates. It does not contain Python, JavaScript, or database changes.

## Install

1. Back up your current `static/css/app.css` and the three templates listed below.
2. Copy `static/css/app.css` from this package into the same path in your project.
3. Copy `templates/base.html`, `templates/login.html`, and `templates/inventory_audit.html` into your project's templates folder.
4. Delete the now-unused `static/css/modern.css`. No template loads it after this update.
5. Restart Flask if template auto-reloading is disabled, then hard-refresh your browser with Ctrl+F5.

The CSS is a complete replacement, not an override to append to the old files.

## Exact template edits

Line numbers refer to the original templates in your supplied system. Apply all removals together, or simply use the included replacement templates.

| File | Original line | Change |
|---|---|---|
| `templates/base.html` | 24 | Remove the stylesheet link to `css/modern.css`; keep the existing `css/app.css` link. |
| `templates/base.html` | 228 | Remove `style="width:min(420px,100%);"` from the confirmation modal card. The same width now lives in `#confirmModal .modal-card`. |
| `templates/base.html` | 238 | Remove `style="font-size:11px;"` from `#confirmMessage`. Its font size now uses `--text-sm` in the CSS. |
| `templates/base.html` | 270 | Remove `style="width:min(360px,100%);"` from the quantity modal card. The same width now lives in `#quantityModal .modal-card`. |
| `templates/base.html` | 284 | Remove the quantity input's inline width, height, border, radius, and padding. It inherits the shared control styles. |
| `templates/login.html` | 1 | Remove only the stylesheet link to `css/modern.css`; leave the rest of this single-line template unchanged. |
| `templates/inventory_audit.html` | 2 | Wrap the register's `<table>...</table>` in `<div class="table-wrap">...</div>` inside the existing `.panel.table-panel`. This makes the table scroll inside its container. |

`TEMPLATE_EDITS.diff` records the exact changes. No existing class names, form names, IDs, handlers, or Jinja conditions/loops have changed. The dynamic inline stock-bar width in `inventory.html` is untouched.

## Main changes

- One stylesheet replaces both styling layers, with no `!important` declarations.
- Navy, green, and yellow colors, DM Sans and Space Grotesk, and light/dark modes are retained. Every literal color is defined in the theme token blocks.
- Type scale: 14px base text, 13px table cells, 12px controls/table headers/body notes, 11px small labels, and 20–24px page/section headings. KPI numbers and the login illustration headline have separate larger tokens.
- Shared 4/8/12/16/24/32px spacing variables, 12px corner radius, 44px controls, consistent page padding, and a 1440px content maximum.
- Thin theme-aware scrollbars use both standard properties and WebKit pseudo-elements. The page, sidebar categories, tables, activity, notifications, and dialogs receive the same scrolling treatment.
- Comfortable table cells, opaque sticky headers, aligned inventory numeric columns, alternating rows, and horizontal/vertical scrolling inside bounded table containers.
- Responsive grids and form layouts down to 320px, with no horizontal document overflow in the checked pages. Modal content scrolls independently of the page.
- Vendor styles are included in the same component system; inventory and vendor dialogs retain their existing JavaScript open/close hooks.

## Validation

The CSS was parsed for syntax errors and checked for `!important` declarations. Template comparison confirms that existing Jinja logic, IDs, form names, classes, and handlers are preserved; the audit template adds only a wrapper element. The preview's Python and JavaScript files are byte-for-byte unchanged.

Chromium checks covered the 11 main authenticated pages at 320, 390, 768, 1024, and 1440px, in both themes (110 combinations). No horizontal document overflow or visible DOM text below 11px was found. Inventory and vendor dialogs were checked at mobile width. This does not claim Firefox/Safari visual testing; their scrollbar properties are included in the stylesheet.

Chart labels are drawn by the existing JavaScript on canvas and cannot be resized using CSS. Their JavaScript configuration is deliberately untouched. Existing external chart scripts were supplied locally only in the test browser to exercise the UI when CDN access was unavailable; no project JS or asset links were changed.
