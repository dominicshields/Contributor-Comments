# Contributor Comments

Contributor Comments is a Flask + Jinja application for capturing and searching unstructured contributor comments for ONS users.

## Implemented Scope

- Flask web application with Jinja templates
- PostgreSQL-backed data model
- Survey metadata management
- Authentication with seeded test users
- Comment capture, edit history, and search
- ONS-style frontend pattern aligned with existing Flexi approach
- Terraform scaffold for AWS resources
- Concourse pipeline scaffold for test/build/deploy

## Data Model

- `reporting_units`
	- `ruref` (11 numeric chars, PK)
- `surveys`
	- `code` (3 chars, PK)
	- `display_order`
	- `description` (text description of survey)
	- `forms_per_period` (numeric count)
- `comments`
	- `id` (PK)
	- `ruref` (FK to reporting_units)
	- `survey_code` (FK to surveys)
	- `period` (YYYYMM)
	- `comment_text`
	- `author_id` (FK to users)
	- `created_at` (UTC)
- `comment_edits`
	- Tracks editor, edit timestamp, previous text, and new text
- `users`
	- App login users (author/editor identity source)

## Functional Behaviour

- RUREF validation: exactly 11 numeric characters
- Period validation: strict `YYYYMM` with valid month
- Search supports:
	- Direct RUREF lookup
	- Survey filter (single or multiple)
	- Full-text contains search across comment text and key identifiers
- Main page uses separate tabs for `Search` and `Add Comment`
- Search results are shown only after a search is performed
- RUREF detail page groups comments by survey in configured survey order, with descending period order
- Author displayed after comment with created timestamp on hover tooltip
- Comment edits are recorded in a true edit history table
- Admin survey metadata supports create, update, activate/deactivate, and complete delete (with confirmation)

## Seed Data

Local and dev startup runs:

- `db.create_all()`
- Survey seed list: `221`, `241`, `002`, `023`, `138`
- Test users:
	- `admin` / `Password123!`
	- `analyst1` / `Password123!`
	- `analyst2` / `Password123!`

## Getting started for Devs
## Local Run

1. Clone and enter the project:

```bash
git clone <your-repo-url>
cd Contributor-Comments
```

2. Install uv (if not already installed):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

3. Create and activate a virtual environment (uv option):

```bash
uv venv .venv
source .venv/bin/activate
```

Alternative with Python directly:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

4. Install dependencies (uv option):

```bash
uv pip install -r requirements.txt
```

Alternative with pip:

```bash
pip install -r requirements.txt
```

5. Start PostgreSQL locally and create a database owned by the `postgres` role:

```bash
sudo -u postgres psql
```

Then run the following in the `psql` prompt:

```sql
CREATE ROLE postgres WITH LOGIN SUPERUSER;
CREATE DATABASE contributor_comments OWNER postgres;
GRANT ALL PRIVILEGES ON DATABASE contributor_comments TO postgres;
\q
```

If `postgres` already exists, use this instead:

```sql
ALTER DATABASE contributor_comments OWNER TO postgres;
GRANT ALL PRIVILEGES ON DATABASE contributor_comments TO postgres;
\q
```

6. Create and load a local environment file:

```bash
cp .env.example .env
set -a
source .env
set +a
```

7. Start the app:

```bash
uv run python run.py
```

Alternative:

```bash
python run.py
```

8. Open `http://localhost:5000`.

9. Login with seeded local users:

- `admin` / `Password123!`
- `analyst1` / `Password123!`
- `analyst2` / `Password123!`

## Database Migrations (Alembic)

- Migration config: `alembic.ini`
- Migration scripts: `migrations/versions/`

Run migrations:

```bash
uv run alembic upgrade head
```

Alternative:

```bash
alembic upgrade head
```

Environment behavior:

- `APP_ENV=dev|development|local|test`: uses `db.create_all()` and seeds local survey/test-user data.
- Any other `APP_ENV` value: runs `alembic upgrade head` at startup and does not auto-seed local test users.

Create a new migration:

```bash
uv run alembic revision --autogenerate -m "describe change"
```

Alternative:

```bash
alembic revision --autogenerate -m "describe change"
```

## Tests

Run automated tests:

```bash
uv run pytest
```

Alternative:

```bash
pytest
```

## Infrastructure Scaffolding

- Terraform files are under `terraform/` and provision:
	- S3 bucket for app logs
	- RDS PostgreSQL instance and supporting network references
- Concourse pipeline is in `pipeline.yml` with jobs for:
	- test
	- image build
	- terraform plan
	- terraform apply

## Notes

- The app is currently PostgreSQL-first by design.
- Code structure keeps data access and route layers separated to support future DynamoDB adapter work with limited refactoring.

## Estimated AWS Monthly Costs (500 Users, 10 Comments Per User Per Day)

These are planning estimates, not quotes. Use AWS Pricing Calculator before procurement.

### Assumptions Used

- Activity volume:
	- `500 users * 10 comments/day = 5,000 comments/day`
	- `~150,000 new comments/month`
- Read activity for estimate:
	- `~1,500,000 comment-read operations/month` (moderate search usage assumption)
- Average comment item size (with metadata): `~1-2 KB`
- Region pricing varies; ranges below are representative for a UK/EU region.
- Costs below focus on the database layer only (not app containers/EC2, ALB, NAT, CloudWatch, etc.).

### Option 1: PostgreSQL (RDS, current approach)

Typical small production-like baseline (Single-AZ):

- RDS instance (`db.t4g.micro` to `db.t4g.small`): `~$15-$45/month`
- Storage (`20-50 GB` gp3): `~$2-$6/month`
- Backup/storage overhead: `~$0-$5/month`

Estimated monthly database total:

- **`~$20-$56/month`** (Single-AZ)

If you require Multi-AZ for higher resilience, a practical range is:

- **`~$80-$180/month`** (depending on class/storage/backup profile)

### Option 2: DynamoDB (on-demand)

For the same workload, with on-demand capacity:

- Writes (`~150k/month`): `~$0.20-$0.35/month`
- Reads (`~1.5M/month`): `~$0.25-$0.60/month`
- Table storage (`~1-5 GB` active): `~$0.30-$1.60/month`
- Optional PITR backup: `~$0.20-$1.50/month`

Estimated monthly database total:

- **`~$1-$4/month`** (on-demand, moderate read profile)

### Quick Comparison

- PostgreSQL (RDS Single-AZ): **`~$20-$56/month`**
- PostgreSQL (RDS Multi-AZ): **`~$80-$180/month`**
- DynamoDB (on-demand): **`~$1-$4/month`**

### Important Caveats

- DynamoDB costs can increase with very heavy query/read patterns, larger item sizes, or GSIs.
- PostgreSQL costs are largely fixed by instance size, so low-volume and medium-volume workloads can cost similar amounts.
- Total platform cost is usually dominated by compute/network/security components, not just database costs.