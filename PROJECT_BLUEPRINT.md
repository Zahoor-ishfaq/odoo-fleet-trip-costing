# PROJECT BLUEPRINT — `fleet_trip_costing`

> **Purpose of this document:** Single source of truth for building this module.
> Any AI/dev session working on this project reads this file FIRST and follows it strictly.
> Owner: Zahoor (Jeddah, KSA — transport/logistics domain expert, Lulu Transport).
> Goal: Free, industry-standard Odoo module on apps.odoo.com to strengthen CV.

---

## 1. Project Summary

**Module name:** `fleet_trip_costing`
**Display name:** Fleet Trip Costing & Profitability
**One-liner:** Answers "Did this trip make money?" — per-trip cost capture, cost/km, and margin analytics on top of Odoo's built-in Fleet module.

**Core features (v1 scope — DO NOT scope-creep):**
1. `fleet.trip` model: vehicle + driver + route + optional customer/sale order link
2. Cost lines per trip: fuel, tolls, driver allowance, maintenance allocation, misc
3. Auto-computed: total cost, cost per km, revenue, margin, margin %
4. Trip states: `draft → in_progress → done → cancelled`
5. Analytics: list, form, kanban, pivot, graph views + filters/groupby
6. Security: two groups (User / Manager) with record rules

**Explicitly OUT of v1:** invoicing automation, GPS/IoT, driver settlements, tyre mgmt, AI features. These are v2+ / separate modules.

---

## 2. Target Versions & Strategy

| Priority | Version | Branch | Notes |
|---|---|---|---|
| Primary | **Odoo 17.0 Community** | `17.0` | Current dev env (Docker) |
| Secondary | **Odoo 19.0 Community** | `19.0` | Forward-port after 17 is stable; install 19 in Docker if 17 blocks us or demand requires |

**Rules:**
- Module version format: `17.0.x.y.z` (first 2 digits MUST match Odoo series).
- Write version-portable code: avoid deprecated APIs, no `attrs`/`states` in XML views on 17 where the modern syntax works (`invisible="state != 'done'"` etc. — 17+ syntax, forward-compatible with 19).
- Odoo store pulls from GitHub branch named exactly `17.0` (and later `19.0`).

---

## 3. Technology Stack & Requirements

| Layer | Technology |
|---|---|
| Platform | Odoo 17.0 Community (Docker image `odoo:17.0`), later `odoo:19.0` |
| Database | PostgreSQL 15 (Docker) |
| Language | Python 3.10+ (whatever ships in the Odoo 17 image), XML for views/data |
| ORM | Odoo ORM only — **never raw SQL** unless a read-only report query is proven necessary |
| Frontend | Standard Odoo views (form/list/kanban/pivot/graph). No custom OWL JS in v1 |
| Dev env | Docker Compose, volume-mounted `./addons`, `--dev=all` |
| VCS | Git + GitHub public repo |
| CI | GitHub Actions: pre-commit + Odoo test run on push/PR |
| Lint/format | `pre-commit` with `black`, `flake8`, `isort`, `pylint-odoo` (OCA config) |
| Tests | `odoo.tests.TransactionCase` (+ `tagged('post_install', '-at_install')` where needed) |
| License | **LGPL-3** (free module) |
| Docs | `README.md` (OCA readme structure), `static/description/index.html` store page |

**Module dependencies (`__manifest__.py` → `depends`):** `['fleet', 'sale']`
Keep dependencies minimal. `sale` only because trips can link to a sale order for revenue. If this creates friction, make revenue a plain Monetary field and drop `sale` to keep the module installable on bare Community. **Decision: start with `['fleet']` + manual revenue field; add optional `sale` link via a tiny bridge module later if needed.** Minimal deps = more installs.

---

## 4. Repository & Module Structure (fixed — do not deviate)

```
fleet_trip_costing/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── fleet_trip.py          # main model
│   └── fleet_trip_cost.py     # cost line model
├── views/
│   ├── fleet_trip_views.xml   # form/list/kanban/search
│   ├── fleet_trip_analytics.xml  # pivot/graph
│   └── fleet_trip_menus.xml   # actions + menus
├── security/
│   ├── fleet_trip_security.xml   # groups + record rules
│   └── ir.model.access.csv
├── data/
│   ├── fleet_trip_sequence.xml   # ir.sequence for trip reference
│   └── fleet_trip_cost_type_data.xml  # default cost types (fuel, toll, ...)
├── tests/
│   ├── __init__.py
│   └── test_fleet_trip.py
├── static/description/
│   ├── icon.png               # 256x256
│   └── index.html             # store listing page
└── README.md
```

Repo root additionally contains: `.pre-commit-config.yaml`, `.github/workflows/ci.yml`, `LICENSE`, `.gitignore`, `docker-compose.yml`, and this `PROJECT_BLUEPRINT.md`.

---

## 5. Data Model

### 5.1 `fleet.trip`
| Field | Type | Notes |
|---|---|---|
| `name` | Char | Sequence `TRIP/2026/00001`, readonly, `copy=False` |
| `vehicle_id` | Many2one `fleet.vehicle` | required, index |
| `driver_id` | Many2one `res.partner` | default from `vehicle_id.driver_id` |
| `date_start` / `date_end` | Datetime | constraint: end ≥ start |
| `route_from` / `route_to` | Char | v1 keeps routes simple (no route master model) |
| `odometer_start` / `odometer_end` | Float | constraint: end ≥ start |
| `distance_km` | Float, compute+store | `end - start`, fallback manual if odometer empty |
| `is_return_empty` | Boolean | domain reality: empty return legs |
| `cost_line_ids` | One2many `fleet.trip.cost` | |
| `revenue` | Monetary | manual in v1 |
| `currency_id` | Many2one | default company currency |
| `total_cost`, `cost_per_km`, `margin`, `margin_pct` | Monetary/Float, compute+store | see §6 |
| `state` | Selection | draft / in_progress / done / cancelled |
| `company_id` | Many2one `res.company` | multi-company safe, default current |
| `notes` | Text | |

`_order = 'date_start desc'`. Add `mail.thread` + `mail.activity.mixin` inheritance for chatter (dep: `mail` — comes free via `fleet`).

### 5.2 `fleet.trip.cost`
| Field | Type |
|---|---|
| `trip_id` | Many2one `fleet.trip`, required, `ondelete='cascade'` |
| `cost_type_id` | Many2one `fleet.trip.cost.type`, required |
| `amount` | Monetary, required, constraint > 0 |
| `date` | Date, default today |
| `note` | Char |

### 5.3 `fleet.trip.cost.type`
Simple master: `name`, `code`, `active`. Seed data: Fuel, Toll, Driver Allowance, Maintenance Allocation, Depreciation, Misc.

---

## 6. Algorithms & Computation Rules

Keep it simple, correct, and O(n) — this is accounting math, not ML.

1. **Total cost:** `total_cost = sum(cost_line_ids.mapped('amount'))`
   - Implement via `@api.depends('cost_line_ids.amount')`, store=True. Batch-safe (loop over `self`, no per-record searches).
2. **Distance:** `distance_km = odometer_end - odometer_start` when both set; else manual field value stands. Guard against negative via `_check` constraint, not silent clamping.
3. **Cost per km:** `cost_per_km = total_cost / distance_km if distance_km else 0.0` — always guard division by zero; use `float_is_zero` with `precision_digits=2` from `odoo.tools`.
4. **Margin:** `margin = revenue - total_cost`; `margin_pct = margin / revenue * 100 if revenue else 0.0`.
5. **Maintenance/depreciation allocation (v1 = manual line, documented method for users):** recommended rate = (annual maintenance budget + annual depreciation) / expected annual km → user enters `rate × distance_km` as a cost line. v2 may automate from `fleet.vehicle.log.services`. **Do not build the automation in v1.**
6. **Currency:** all Monetary fields share `currency_id`; use `currency_id.round()` when doing arithmetic that will be compared.
7. **Aggregation/analytics:** delegated to pivot/graph views + `read_group` (built-in). Write NO custom aggregation Python.

**Performance rules:**
- All computes must handle recordsets in batch (iterate `self`; never `self.ensure_one()` in a compute).
- No `search()` inside loops. Prefetch via `mapped()`.
- `store=True` on all reported computes so pivot/graph/groupby work from SQL.
- Index fields used in default filters (`vehicle_id`, `date_start`, `state`).
- Float fields: never use truthiness to test "is set" — 0.0 is a legitimate value and Odoo Floats default to 0.0. Test the field that is semantically required instead.

---

## 7. Coding Standards (OCA — mandatory)

Follow **OCA guidelines** (https://github.com/OCA/odoo-community.org/blob/master/website/Contribution/CONTRIBUTING.rst and `oca-addons-repo-template` conventions):

- **Python:** PEP8 via `black` (line length 88) + `isort` + `flake8` + `pylint-odoo`. No unused imports, no commented-out dead code, no prints — use `_logger` only when genuinely needed.
- **Naming:** model files = model name with underscores; XML ids = `model_name_view_form`, `model_name_action`, `model_name_menu`; fields suffixed `_id`/`_ids` for relations.
- **XML:** one view per `<record>`, meaningful `id`s, no duplicated arch, use `<list>` (17+) not `<tree>` where the version supports it (17 accepts `tree`; keep `tree` on 17 branch, switch to `list` on 19 branch).
- **Security first:** every new model gets `ir.model.access.csv` rows for both groups. Record rule: multi-company `['|', ('company_id', '=', False), ('company_id', 'in', company_ids)]`.
- **Translations:** all user-facing strings wrapped for translation (XML auto; Python via `_()` from `odoo`).
- **Manifest:** proper `summary`, `category: 'Human Resources/Fleet'`, `license: 'LGPL-3'`, `images: ['static/description/banner.png']`, `application: False`, `installable: True`.
- **Commits:** conventional style `[ADD]`, `[FIX]`, `[IMP]`, `[REF]` (OCA convention), imperative mood, small commits.
- **Code volume rule (per Zahoor):** write the MINIMUM code that does the job correctly. No speculative abstractions, no unused hooks, no "just in case" fields. Every line must justify itself.

---

## 8. `.pre-commit-config.yaml` (repo root — use exactly this, update revs as needed)

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-xml
      - id: check-yaml
  - repo: https://github.com/psf/black
    rev: 24.8.0
    hooks:
      - id: black
  - repo: https://github.com/PyCQA/isort
    rev: 5.13.2
    hooks:
      - id: isort
        args: ["--profile", "black"]
  - repo: https://github.com/PyCQA/flake8
    rev: 7.1.1
    hooks:
      - id: flake8
        args: ["--max-line-length=88", "--extend-ignore=E203,W503"]
  - repo: https://github.com/OCA/pylint-odoo
    rev: v9.1.3
    hooks:
      - id: pylint_odoo
```

Run `pre-commit install` once; `pre-commit run -a` before every push. CI re-runs it.

---

## 9. Testing Rules

- Framework: `from odoo.tests import TransactionCase, tagged`
- File: `tests/test_fleet_trip.py`; class `TestFleetTrip(TransactionCase)`; use `setUpClass` with `cls.env` fixtures (one vehicle, one trip, cost lines).
- **Minimum test matrix (v1):**
  1. Trip creation gets sequence name
  2. `total_cost` sums cost lines correctly (add + delete line)
  3. `distance_km` from odometers; constraint blocks `end < start`
  4. `cost_per_km` division-by-zero guard (distance = 0 → 0.0, no crash)
  5. `margin` / `margin_pct` math incl. zero revenue
  6. State flow draft→done; cancelled trips excluded from default filter
  7. Access: User group can create own-company trip; record rule blocks other company
- Run locally: `docker compose run --rm web odoo -d test_db -i fleet_trip_costing --test-enable --stop-after-init`
- Every bug found later → regression test added first, then fix.

---

## 10. CI — `.github/workflows/ci.yml` (outline)

Two jobs:
1. **lint:** checkout → setup Python → `pip install pre-commit` → `pre-commit run -a`
2. **test:** services: `postgres:15` → run `odoo:17.0` container (or pip-install odoo) → install module with `--test-enable --stop-after-init` → fail on test errors

Badge in README. Green CI is a hard requirement before publishing.

---

## 11. Docker Dev Environment (reference)

```yaml
services:
  web:
    image: odoo:17.0
    depends_on: [db]
    ports: ["8069:8069"]
    volumes:
      - ./addons:/mnt/extra-addons
    command: odoo --dev=all
  db:
    image: postgres:15
    environment:
      POSTGRES_USER: odoo
      POSTGRES_PASSWORD: odoo
      POSTGRES_DB: postgres
```

For Odoo 19: duplicate compose file with `image: odoo:19.0` and a separate DB volume. Never share a database between versions.

---

## 12. Publishing Checklist (apps.odoo.com)

- [ ] GitHub branch `17.0` contains the module at repo root (store requirement)
- [ ] `__manifest__.py`: version `17.0.1.0.0`, license LGPL-3, summary, category, images
- [ ] `static/description/index.html`: screenshots, feature bullets, GIF/short demo
- [ ] `icon.png` 256×256
- [ ] README with install steps, usage, screenshots, CI badge
- [ ] `pre-commit run -a` clean, all tests green
- [ ] Register repo URL on apps.odoo.com → wait for automated scan
- [ ] Price: **Free** · After stable: create `19.0` branch, port, publish again

---

## 13. Session Rules for the AI (self-instructions)

1. Read this file at the start of every working session; follow it over memory.
2. Never expand v1 scope without Zahoor's explicit ok.
3. Write minimal, optimized, batch-safe ORM code — no filler, no boilerplate beyond the standard structure in §4.
4. Every model change → update `ir.model.access.csv` + tests in the same step.
5. All code must pass the §8 hooks conceptually (black-formatted, pylint-odoo clean) as written — don't rely on "fix later."
6. Keep 17→19 portability in mind for every view and API used; note any 19-incompatible construct in a `# PORT-19:` comment.
7. When finished with a file, state which checklist items (§12) it advances.
