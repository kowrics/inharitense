# ECMCI v9 — final request workflow, clean dropdowns, and forecast demo

This complete project retains the inventory UI, report filters/query fix, audit drafts, account settings, and forecast demo, with the latest request workflow and dropdown cleanup. The dashboard design is unchanged; operational links use their now-authorized destinations.

## Final v9 changes

- Employee requests notify Encoder first with status For Review. Encoder endorses to Super User; only Super User approves. Approved requests notify Encoder for release. The final stored status remains Fulfilled.
- Encoder cannot approve a request or release it before approval. Super User retains full review/release access as an administrative fallback, while normal routing starts with Encoder.
- Release checks current stock atomically, records one movement and the releasing user, updates stock usage, and rejects duplicate/concurrent release attempts. It preserves the Super User approval identity and timestamp.
- Item dropdowns on Requests, Assignments, Requisitions, and Stock movement show tag/name only. The page-load stock counts and “available”/“on hand” suffixes have been removed. Category item counts and the required stock-movement context remain. Removing labels does not rewrite existing/demo stock values.
- Pending requests already stored in the database remain accessible in the Encoder inbox; no data migration is required.

## Retained operational permissions and forecast demo

- Encoder can view/create assignments and disburse items to employees. Assignment still deducts stock atomically, records the Stock OUT transaction and responsible user, and leaves receipt acknowledgement to the employee.
- Encoder can prepare and print/save requisition reports for the company's existing purchasing system. This does not create purchase orders or perform purchasing.
- Encoder can view forecasting for inventory planning. This is an assumed planning duty alongside their requisition work.
- Users, vendors masterlist, approvals, and item deletion remain Super User-only. Report Generator remains read-only for operational records. Employee records remain scoped to the employee.
- Forecasting now offers **Preview with sample data**. It computes a real regression result from a fixed illustrative 26-week history, using sample stock of 9 and a sample stock target of 40. All sample outputs are visibly labeled. It does not insert history, change actual stock, or generate a requisition.
- The regression formula, recent-usage blend, and reorder calculation are unchanged. The existing calculation was extracted into `_forecast_from_weekly` so real and sample history use exactly the same calculation.
- Forecast graphs and code scanning now use bundled Chart.js/jsQR files, so those features no longer need their CDN scripts. Font loading still uses the existing Google Fonts URL with CSS fallback fonts.
- `run.bat` now installs dependencies using the virtual environment's `python.exe -m pip`, supports the Python launcher or `python`, and stops when setup fails. This addresses the reported `pip` not recognized / missing Flask error.

## Does forecasting require enough data?

A meaningful demand forecast needs recorded usage. This app's live forecast requires Stock OUT usage in at least **four complete weeks** within its 26-week window. The current incomplete week is excluded. This is the app's minimum-history rule, not proof of accuracy and not a claim that four weeks always guarantees a good prediction.

Until there is enough history, live mode honestly says that history is insufficient and uses the configured minimum-stock threshold for a replenishment warning. It does not invent a weekly-demand prediction. Existing historical usage can count; the requirement is not necessarily four newly elapsed weeks. More representative history helps, and the High/Medium/Low label still describes history/model fit rather than validated forecast accuracy.

The preview lets you demonstrate the full feature immediately without presenting sample observations as actual company activity. For the default sample, it estimates about 14.21 units/week, roughly 4 days of coverage, and a suggested reorder of 31 units. Changes to lead time and safety stock recalculate the preview. Sample quantities use the selected item's unit but do not represent measured usage of that item.

## How to run and demonstrate today

1. Extract `ECMCI_Inventory_System_v9_Final.zip` into a new folder. If upgrading records, stop the old app and back up/copy your current database and environment configuration first.
2. Double-click `run.bat` and let dependency installation finish. Open http://127.0.0.1:5000. Existing demo credentials and edited account passwords are preserved.
3. Open **AI Demand Forecasting** as Super User, Encoder, or Report Generator.
4. Choose a consumable item, then click **Preview with sample data**. You can also click this button first: it selects the first consumable item.
5. Show the weekly-use estimate, trend graph, stock-coverage estimate, suggested reorder, and expandable explanation/technical details.
6. Click **Return to actual records** to show that real history remains separate.

Suggested presentation wording: “This preview uses sample weekly usage to demonstrate our linear regression demand forecast. In actual operation, the system uses recorded Stock OUT transactions. When history is insufficient, it shows a minimum-stock warning instead of an unsupported prediction.”

If setup fails, in the project folder use:

```powershell
python -m ensurepip --upgrade
python -m pip install -r requirements.txt
python app.py
```

## Files in this final update

| Area | Files |
|---|---|
| Permissions / shared forecast calculation / demo API / requisition validation | `app.py` |
| Role-aware navigation and local libraries | `templates/base.html` |
| Permission-safe links only; dashboard design retained | `templates/dashboard.html` |
| Sample preview button, source label, disclosure, return-to-live control | `templates/forecast.html` |
| Request inbox, review/release controls, cleaned item options | `templates/requests.html`, `templates/assignments.html`, `templates/requisitions.html`, `templates/inventory.html` |
| Preview switching and graph presentation | `static/js/app.js` |
| Bundled chart/scanner libraries and licenses | `static/vendor/*` |
| Windows startup | `run.bat` |
| Updated/new regression tests | `tests/test_app.py`, `tests/test_v7.py`, `tests/test_v8.py`, `tests/test_v9.py` |
| Current documentation / exact replacements | `README.md`, `V9_FINAL_NOTES.md`, `V9_SOURCE_CHANGES.diff` |

Existing form names, operational URLs, themes, and class names are retained. The only new endpoint is the read-only `/api/forecast-demo/<item_id>` and it has the same forecasting role checks. There is no additional v9 database migration. The included `migrations/v7_postgresql.sql` and automatic startup migrations still add audit draft/account columns when upgrading from an older release. Do not replace a newer working database with the bundled demo database.

## Checks and manual tests

1. As Employee, submit a request. Check Encoder notifications and the Review inbox.
2. As Encoder, endorse it. A direct approve or premature release must return 403.
3. As Super User, approve the endorsed request. Check the Encoder release notification.
4. As Encoder, release it. Verify stock is deducted exactly once and Employee sees Fulfilled. Repeating release must be rejected.
5. Open item selectors in Requests, Assignments, Requisitions, and Stock movement. Verify they show no stock quantities or availability suffixes.

162 automated SQLite tests passed, including Encoder assignment/requisition success, forbidden administrative actions with valid CSRF, read-only restrictions, employee ownership, preview role checks, invalid parameters, and proof that the preview makes no inventory/movement/requisition changes. Browser checks passed across 80 page/viewport/theme combinations with no horizontal page overflow or JavaScript errors. Request submission, Encoder endorsement, Super User approval, Encoder release, and clean dropdowns were verified in the browser. The preview and return-to-live workflow were checked in both themes and mobile widths. A live PostgreSQL instance and a Windows command shell were unavailable, so those runtime checks remain for your local/staging environment.

Manual checks:

- As Encoder, assign stock to an active Employee; check the quantity deduction and movement log. Open the employee account to acknowledge their own receipt.
- As Encoder, prepare a requisition, then use Print / Save PDF. Try zero/invalid quantity or an invalid item: server must reject it.
- As Encoder, paste `/users`, `/vendors`, and `/reports-v4`: each must return 403. Item deletion and request approval remain forbidden.
- As Report Generator, open Reports and Forecasting; assignment/requisition mutation remains forbidden. As Employee, open only your own items/requests and personal settings.
- Preview forecasting, change lead time/safety stock, return to actual records, and verify actual stock and movement history were not changed.
- Recheck the retained v7 features: stock −/+ confirmation/cancel, counted category selector, collapsed item sections, report reset/chips, partial audit drafts, unsaved warning, and account/password changes.

Run automated checks:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

## Current permission matrix

| Page / action | Super User | Encoder | Report Generator | Employee |
|---|---|---|---|---|
| Dashboard | Full | View | View | Own data |
| Inventory / scan | Full | View / scan | — | — |
| Add / edit / stock IN/OUT | Yes | Yes | — | — |
| Delete inventory | Yes, reference checks | — | — | — |
| Assign / disburse items | Yes | Yes | — | — |
| Assignment register | All | All | — | Own items |
| Receipt acknowledgement | Own recipient only | — | — | Own only |
| Prepare / print requisition report | Yes | Yes | — | — |
| Forecast / labeled sample preview | Yes | View | View | — |
| Reports / exports | Yes | — | View / export | — |
| Audit / draft / finalize | All | Assigned only | — | — |
| Create / assign audits | Yes | — | — | — |
| Users / vendors / lifecycle | Yes | — | — | — |
| Requests | All / create | All / review | — | Own / create |
| Review / endorse requests | Yes | Yes | — | — |
| Approve / reject endorsed requests | Yes | — | — | — |
| Release approved requests | Yes | Yes | — | — |
| Personal settings / notifications | Own | Own | Own | Own |

Company category/subcategory and GL mapping remain a separate requirements decision: this update retains the existing category structure and does not invent unknown GL codes or subcategories.
