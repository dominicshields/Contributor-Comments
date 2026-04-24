# Contributor Comments — Application Context

This document provides a comprehensive context reference for the Contributor Comments application, intended for AI assistants and developers working on the codebase.

## Purpose

Contributor Comments is an internal ONS (Office for National Statistics) tool for capturing, searching, and managing unstructured contributor comments against reporting units. It is used by ONS analysts to record notes from contributor interactions (phone calls, emails, form queries) and retrieve them by reporting unit, survey, author, or date.

## Technology Stack

- **Backend**: Python 3.12, Flask 3.1.1, Jinja2 templates
- **Database**: PostgreSQL (primary), SQLite for tests
- **ORM**: Flask-SQLAlchemy with SQLAlchemy mapped columns
- **Migrations**: Alembic (10 versioned migrations in `migrations/versions/`)
- **Auth**: Flask-Login with dual mode — SSO (production) and local password (dev/test)
- **CSRF**: Flask-WTF CSRFProtect
- **Frontend CSS**: ONS Design System CDN (v73.0.0) + Bootstrap 5.3 + custom `contributor-ons.css`
- **Frontend JS**: Vanilla JavaScript (no framework), Bootstrap JS bundle
- **Testing**: pytest with in-memory SQLite
- **Containerisation**: Dockerfile (python:3.12-slim)
- **Infrastructure**: Terraform (AWS RDS PostgreSQL, S3)
- **CI/CD**: Concourse pipeline (`pipeline.yml`)

## Project Structure

```
Contributor-Comments/
├── app/
│   ├── __init__.py          # App factory, Alembic runner, context processors, template filters
│   ├── extensions.py        # db, login_manager, csrf singletons
│   ├── models.py            # All SQLAlchemy models
│   ├── seed.py              # Reference data seeding (surveys, users, templates)
│   ├── validation.py        # RUREF, period, periodicity validation
│   ├── routes/
│   │   ├── auth.py          # Login/logout, SSO + local auth
│   │   ├── comments.py      # Main search, add, RUREF detail, by-author, by-date, contacts, help
│   │   └── admin.py         # Survey CRUD, system info, bulk upload, templates, delete-all
│   ├── static/
│   │   └── design-system/v1/contributor-ons.css   # Custom ONS-aligned stylesheet
│   └── templates/
│       ├── base.html                # Master layout: header, nav, footer, flash messages
│       ├── auth/login.html
│       ├── comments/
│       │   ├── index.html           # Search + Add Comment (tabbed)
│       │   ├── ruref_detail.html    # Single RUREF comment view
│       │   ├── by_author.html       # Comments grouped by author
│       │   ├── by_date.html         # Year/month index + month detail
│       │   ├── edit_comment.html
│       │   ├── edit_contact.html
│       │   └── contact_management.html
│       ├── admin/
│       │   ├── surveys.html
│       │   ├── system_info.html
│       │   ├── bulk_upload_comments.html
│       │   ├── templates.html
│       │   └── delete_all_comments.html
│       └── help/
│           ├── index.html
│           └── edit.html
├── migrations/              # Alembic migration scripts
├── tests/                   # pytest test suite
├── terraform/               # AWS infrastructure (RDS, S3, security groups)
├── specs/                   # Design and feature specifications
├── utilities/               # generate_test_comments.py
├── surveys.csv              # Import source for survey metadata
├── pipeline.yml             # Concourse CI/CD
├── Dockerfile
├── requirements.txt
├── alembic.ini
└── run.py                   # Entry point
```

## Data Model

Seven database tables, all defined in `app/models.py`:

| Table | Primary Key | Purpose |
|---|---|---|
| `users` | `id` (int) | App users — authors, editors, admins. Stores password hash, admin flag, spellcheck preference. |
| `reporting_units` | `ruref` (string, 11 digits) | Reporting unit references. Auto-created when first comment is added. |
| `surveys` | `code` (string, 3 digits) | Survey metadata — description, periodicity (Annual/Quarterly/Monthly/Other), forms_per_period, display_order, is_active. |
| `comments` | `id` (int) | Core comment records. FK to reporting_units, surveys (nullable for general), users. Stores period (YYYYMM), comment_text, contact snapshots, timestamps. |
| `comment_edits` | `id` (int) | Edit history — previous_text, new_text, editor_id, edited_at. FK to comments and users. |
| `contacts` | `id` (int) | Scoped contacts per RUREF + survey (or RUREF + general). Unique constraint on (ruref, survey_code). |
| `comment_templates` | `id` (int) | Standard wording templates for Add Comment. Ordered by display_order, can be active/inactive. |
| `site_content` | `key` (string) | Key-value store for editable content (currently: help page). |

### Key Relationships

- A comment belongs to one reporting_unit, optionally one survey, and one author (user).
- General comments have `is_general=True` and `survey_code=NULL`.
- Comments store contact snapshots at creation time so later contact edits don't rewrite history.
- Contacts are scoped to (ruref, survey_code) with a unique constraint. `survey_code=NULL` means general scope.
- Comment edits form a history chain per comment.

### Validation Rules

- **RUREF**: exactly 11 numeric characters.
- **Period**: `YYYYMM`, valid month (01–12), year between 1990 and current+5.
- **Survey periodicity enforcement**:
  - Monthly: any month
  - Quarterly: months 03, 06, 09, 12
  - Annual/Other: month 12
  - Exception: survey `141` requires month `04`
- **Survey code**: exactly 3 numeric characters.

## Authentication

Controlled by `AUTH_MODE` environment variable:

- **`sso`** (default/production): Reads `X-Forwarded-User` and `X-Forwarded-Name` headers from upstream reverse proxy. Auto-provisions new users unless `SSO_AUTO_PROVISION=false`. SSO users get a random password hash (unused).
- **`local`** (dev/test): Username/password login form. Seeded test users: `admin`, `analyst1`, `analyst2` (all `Password123!`).

### Authorisation

- All authenticated users can: search, add comments, edit comments, edit contacts, view all pages except System Config.
- Admin users (`is_admin=True`) additionally access: Survey Metadata CRUD, System Config (system info, bulk upload, templates, delete-all).
- Admin checks use `current_user.is_admin` in route handlers.

## Route Architecture

Three Flask Blueprints:

### `auth` (`/auth`)
- `GET/POST /auth/login` — SSO or local login
- `POST /auth/logout` — Logout

### `comments` (root)
- `GET /comments` — Main page (Search tab + Add Comment tab)
- `POST /comments/new` — Create comment
- `GET /ruref/<ruref>` — RUREF detail page
- `GET /comments/by-author` — Comments by Author (paginated, 50 per page)
- `GET /comments/by-date` — Comments by Date (year/month index + month detail, 50 per page)
- `GET/POST /comments/<id>/edit` — Edit comment text
- `GET /comments/contact-prefill` — JSON API for auto-prefilling contact fields
- `POST /comments/check-contact` — Legacy contact check (still present)
- `POST /comments/preferences/spellcheck` — JSON API for spellcheck toggle
- `GET /contacts-management` — Contact Management page
- `GET/POST /contacts/<id>/edit` — Edit contact
- `GET /help` — Help page
- `GET/POST /help/edit` — Edit help page (admin)

### `admin` (`/admin`)
- `GET /admin/surveys` — Survey list (sortable)
- `POST /admin/surveys` — Add survey
- `POST /admin/surveys/<code>/metadata` — Update survey
- `POST /admin/surveys/<code>/toggle-active` — Activate/deactivate
- `POST /admin/surveys/<code>/delete` — Delete survey + related data
- `POST /admin/surveys/import` — Import from `surveys.csv`
- `GET /admin/system-config/system-info` — System Info (Comments + Contacts tabs)
- `GET/POST /admin/system-config/bulk-upload-comments` — Bulk CSV upload
- `GET/POST /admin/system-config/templates` — Template management
- `POST /admin/system-config/templates/<id>` — Update template
- `POST /admin/system-config/templates/<id>/move` — Reorder template
- `GET/POST /admin/system-config/delete-all-comments` — Delete all comments and contacts

## Frontend Architecture

### ONS Design System Alignment

The application follows the ONS Design System (https://service-manual.ons.gov.uk/design-system) using the **internal header** variant. Key design system references:

- **Header**: `ons-header--internal` pattern with dark blue top bar (ONS logo, user identity, sign-out), ocean blue service title bar, and ocean blue primary navigation. See: https://service-manual.ons.gov.uk/design-system/components/header
- **Phase banner**: BETA tag above header. See: https://service-manual.ons.gov.uk/design-system/components/phase-banner
- **Navigation**: Two-tier — primary nav (ocean blue) for main sections, sub-nav (light tint) for subsections (Comments submenu, System Config submenu). See: https://service-manual.ons.gov.uk/design-system/components/navigation
- **Footer**: Standard ONS footer with links and legal text. See: https://service-manual.ons.gov.uk/design-system/components/footer
- **Skip link**: Accessibility skip-to-content link. See: https://service-manual.ons.gov.uk/design-system/components/skip-to-content
- **Browser banner**: Unsupported browser warning. See: https://service-manual.ons.gov.uk/design-system/components/browser-banner
- **Typography**: OpenSans font family with `font-feature-settings: "ss01"`. See: https://service-manual.ons.gov.uk/design-system/foundations/typography
- **Colours**: ONS palette — Night blue (#003c57), Ocean blue (#206095), Leaf green (#0f8243), Ruby red (#d0021b), Sun yellow (#fbc900 for focus). See: https://service-manual.ons.gov.uk/design-system/foundations/colours
- **Focus states**: 3px Sun yellow outline + black box-shadow. See: https://service-manual.ons.gov.uk/design-system/foundations/focus-state
- **Panels**: Used sparingly for action results, not for general content grouping. See: https://service-manual.ons.gov.uk/design-system/components/panel
- **Tables**: Standard HTML tables with ONS styling for data display. See: https://service-manual.ons.gov.uk/design-system/components/table
- **Pagination**: Bootstrap pagination component (not ONS native). See: https://service-manual.ons.gov.uk/design-system/components/pagination
- **Collapsible groups**: Custom implementation for author groups and year/month index using `<details>`/`<summary>` and JS-driven toggle buttons.

### CSS Layering

1. **Bootstrap 5.3** (CDN) — Grid, forms, buttons, modals, tooltips, alerts
2. **ONS Design System main.css** (CDN v73.0.0) — Typography, colours, some component styles
3. **`contributor-ons.css`** (local) — Custom overrides that bridge Bootstrap and ONS patterns. Defines CSS custom properties for the ONS colour palette, styles the internal header, navigation, footer, content sections, comment cards, survey picker, collapsible groups, and responsive breakpoints.

### Key CSS Custom Properties

```css
--ons-blue: #003c57        /* Night blue */
--ons-blue-alt: #206095    /* Ocean blue */
--ons-green: #0f8243       /* Leaf green — primary buttons */
--ons-red: #d0021b         /* Ruby red */
--ons-focus: #fbc900       /* Sun yellow — focus rings */
--ons-grey-95: #f5f5f6     /* Light grey backgrounds */
--ons-grey-15: #e2e2e3     /* Borders */
--ons-grey-75: #707071     /* Muted text */
```

### JavaScript Patterns

All JS is vanilla, loaded in `{% block extra_js %}` per template. Key behaviours:

- **CSRF injection**: Auto-injects `csrf_token` hidden input into all POST forms from `<meta name="csrf-token">`.
- **Survey picker**: Collapsible checkbox list with filter, select-all, clear, and count badge.
- **General comment toggle**: Hides/shows survey select, clears survey value when general is checked.
- **Contact auto-prefill**: Fetches `/comments/contact-prefill` via AJAX when RUREF + survey scope is complete. Fires on RUREF blur, survey change, and general toggle change.
- **Spellcheck toggle**: Persists per-user preference via `POST /comments/preferences/spellcheck`.
- **Template insert modal**: Bootstrap modal with filter input; clicking a template appends wording to comment textarea.
- **Collapsible author groups**: JS-driven expand/collapse with Collapse all / Expand all buttons.
- **Year/month index**: Native `<details>` elements with JS Collapse all / Expand all.
- **Show Contact Information radio**: Triggers page reload with `show_contacts` query parameter on change.

## Template Filters

Defined in `app/__init__.py`:

- `uk_datetime` — Converts UTC datetime to Europe/London timezone, formats as `DD Mon YYYY HH:MM`.
- `highlight_term` — Wraps search term matches in `<mark>` tags within escaped text. Used in search results.

## Comment Display Ordering

Comments are consistently ordered across views:

1. **General comments first** (is_general=True), then survey-specific
2. **Survey display_order** ascending (configured in Survey Metadata)
3. **Period descending** (newest first)
4. **Created timestamp descending** within same period

## Contact Behaviour

- Contacts are scoped to (ruref, survey_code). General scope uses `survey_code=NULL`.
- When adding a comment, existing contact details for the matching scope are auto-prefilled via AJAX.
- If the user changes prefilled contact details, the scoped contact record is updated and the comment saves the new values as snapshots.
- Comment records store `contact_name_snapshot`, `contact_phone_snapshot`, `contact_email_snapshot` at creation time.
- Contact display in results uses snapshots first; falls back to live contact only if no snapshot exists.
- Orphan contacts (no matching comments) are cleaned up on Contact Management page load.
- `Show Contact Information` radio (No/Yes) controls visibility across Search, Show Comments, and RUREF detail.

## Environment Configuration

Key environment variables (see `.env.example`):

| Variable | Default | Purpose |
|---|---|---|
| `SECRET_KEY` | `dev-secret-key` | Flask session secret |
| `APP_ENV` | `dev` | Controls startup behaviour (dev/local/test = seed + create_all; other = alembic only) |
| `AUTH_MODE` | `sso` | Authentication mode (`sso` or `local`) |
| `DATABASE_URL` | PostgreSQL localhost | SQLAlchemy connection string |
| `SSO_HEADER_USERNAME` | `X-Forwarded-User` | SSO identity header |
| `SSO_HEADER_FULL_NAME` | `X-Forwarded-Name` | SSO display name header |
| `SSO_AUTO_PROVISION` | `true` | Auto-create users from SSO |
| `ONS_DESIGN_SYSTEM_VERSION` | `73.0.0` | CDN version for ONS CSS |

## Startup Behaviour

In `create_app()`:

- **dev/development/local/test**: Runs Alembic upgrade head (except test with SQLite memory), then `db.create_all()`, then seeds surveys, test users, and default comment templates.
- **Other environments** (production): Runs Alembic upgrade head only. No seeding.

## Testing

- Tests use in-memory SQLite (`DATABASE_URL=sqlite:///:memory:`).
- `conftest.py` provides `app`, `client`, `login_admin`, `login_analyst` fixtures.
- CSRF is disabled in tests (`WTF_CSRF_ENABLED=False`).
- Test files cover: admin surveys, app config, SSO auth, comment routes, bulk upload, validation.

## Infrastructure

### Terraform (`terraform/`)

- AWS provider, region parameterised
- S3 bucket for app logs (versioning enabled)
- RDS PostgreSQL 16.3 (`db.t4g.micro`, 20GB gp3, encrypted, private)
- DB subnet group and security group (ingress from app SG on port 5432)

### Concourse Pipeline (`pipeline.yml`)

Four jobs: `test` → `build-image` → `terraform-plan` → `terraform-apply`

## Bulk Upload CSV Format

Required columns: `ruref`, `period`, `comment_text`

Optional columns: `survey_code`, `is_general`, `author_name`, `saved_at`, `contact_name`, `contact_phone`, `contact_email`

Import creates missing reporting units and author users automatically. Rows failing validation are skipped. General comments are inferred from blank `survey_code` or truthy `is_general`.

## Key Design Decisions

1. **PostgreSQL-first**: The data model uses PostgreSQL features (check constraints, text search). Code structure separates data access to support a future DynamoDB adapter.
2. **Contact snapshots**: Comments freeze contact details at creation time so historical records are not affected by later contact edits.
3. **Dual auth**: SSO for production with auto-provisioning; local passwords for development. Both share the same `users` table.
4. **ONS internal header**: Uses the ONS Design System internal service header pattern rather than the public-facing header, appropriate for an internal analyst tool.
5. **Bootstrap + ONS hybrid**: Bootstrap provides form controls, grid, modals, and tooltips. ONS Design System provides typography, colours, header/footer patterns. Custom CSS bridges the two.
6. **No frontend framework**: All interactivity is vanilla JS to keep the stack simple and aligned with the existing ONS Flexi approach.
7. **Flash messages for feedback**: All user actions (save, error, import results) use Flask flash messages rendered as Bootstrap alerts.
8. **Alembic for schema evolution**: Production uses Alembic migrations exclusively. Dev environments also run `db.create_all()` as a safety net.
