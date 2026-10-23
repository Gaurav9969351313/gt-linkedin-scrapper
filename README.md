# GT LinkedIn Scraper

Scrapes LinkedIn job posts for HR email addresses (Playwright + Prefect + PostgreSQL), stores them,
and emails candidate applications to them. It ships with two admin UIs:

- **Web app** (Angular, invite-only, roles): http://localhost:8502
- **Streamlit app** (single shared login): http://localhost:8501

Contents:
[1. Prerequisites](#1-prerequisites) ·
[2. Get the code](#2-get-the-code) ·
[3. Configure `.env`](#3-configure-env) ·
[4. Streamlit login](#4-set-the-streamlit-login) ·
[5. Initial scrape jobs](#5-initial-scrape-jobs-optional) ·
[6. Start everything](#6-start-everything) ·
[7. Check it's running](#7-check-that-everything-is-running) ·
[8. Create the super admin](#8-create-the-super-admin) ·
[9. Use the web app](#9-use-the-web-app) ·
[10. Run a scrape](#10-run-a-scrape) ·
[11. Send candidate emails](#11-send-candidate-emails) ·
[12. Day-to-day operations](#12-day-to-day-operations) ·
[13. Local development](#13-local-development-without-docker-for-the-apps) ·
[14. Tests](#14-tests) ·
[15. Configuration reference](#15-configuration-reference) ·
[16. Troubleshooting](#16-troubleshooting) ·
[17. Project layout](#17-project-layout)

> Commands below are for **PowerShell on Windows**. They work the same in bash/zsh except where noted.
> A `Makefile` offers shortcuts (`make help`), but `make` isn't installed on Windows by default,
> so every step shows the plain command.

---

## 1. Prerequisites

| Tool | Needed for | Check |
|---|---|---|
| [Docker Desktop](https://www.docker.com/products/docker-desktop/) (running) | Everything | `docker compose version` |
| Git | Getting the code | `git --version` |
| Python 3.11+ | Only for local development and tests | `python --version` |
| Node.js 20+ | Only for working on the Angular app outside Docker | `node --version` |

You also need:

- A **LinkedIn account** for the scraper to log in with.
- An **SMTP account** for outgoing email (reports, invitations, approval emails). For Gmail, turn on
  2-step verification and create an **App Password** at https://myaccount.google.com/apppasswords.

Free ports used: `5432` (Postgres), `4200` (Prefect), `5050` (pgAdmin), `8000` (scraper API),
`8501` (Streamlit), `8502` (web app).

## 2. Get the code

```powershell
git clone <repo-url> gt-linkedin-scraper
cd gt-linkedin-scraper
```

All commands from here on run from this folder (the repo root).

## 3. Configure `.env`

```powershell
Copy-Item .env.example .env
notepad .env
```

Fill in at least these:

| Variable | What to put |
|---|---|
| `LINKEDIN_USERNAME`, `LINKEDIN_PASSWORD` | The LinkedIn account the scraper logs in with |
| `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | Your email address and its App Password |
| `TAG_RECIPIENTS__DEFAULT` | Who receives scrape reports (comma-separated) |
| `WEB_SECRET_KEY` | A long random string (see below) |
| `WEB_PUBLIC_URL` | `http://localhost:8502` locally; your real URL in production (used in invite links) |

Generate `WEB_SECRET_KEY` and paste it into `.env`:

```powershell
[guid]::NewGuid().ToString('N') + [guid]::NewGuid().ToString('N')
```

Without it, everyone is signed out of the web app whenever its container restarts.

Leave the database and Prefect values as they are. Inside Docker the hostnames and file paths
are overridden automatically by `docker-compose.yml`.

> `.env` holds secrets and is git-ignored. Never commit it.

## 4. Set the Streamlit login

The Streamlit app uses one shared username and password:

```powershell
Copy-Item apps/streamlit/.streamlit/secrets.toml.example apps/streamlit/.streamlit/secrets.toml
notepad apps/streamlit/.streamlit/secrets.toml
```

```toml
[auth]
username = "admin"
password = "choose-a-strong-password"
```

This file is git-ignored too. (The web app doesn't use it; it has its own user accounts.)

## 5. Initial scrape jobs (optional)

Scrape jobs are managed in the web app by a super admin (**Scraper jobs**, see step 9). The first
time the stack starts with an empty database, it seeds jobs from [config/jobs.yaml](config/jobs.yaml):

```yaml
jobs:
  - id: 1
    keyword: '"Java" AND "Contract"'   # LinkedIn content search
    scroll_count: 5                     # how far to scroll the results
    tag: java                           # devops | java | qa | freshers | data_engineer
    cron: "31 7 * * *"                  # schedule, Asia/Kolkata time
```

After that the **database is the source of truth**, and edits to this file are ignored. To force a
reload from the file (it overwrites jobs with the same id), run
`docker exec scraper-api python scripts/seed_jobs.py`, then `docker compose restart api`.

## 6. Start everything

```powershell
docker compose up -d --build
```

The first build takes several minutes (it downloads Chromium for Playwright and builds the
Angular app). Shortcut: `make docker`.

On start-up, the stack:

1. **Postgres** starts and creates the `scraper_db` and `prefect` databases.
2. **Prefect server** starts.
3. **Scraper API** runs `scripts/migrate.py`, which creates or upgrades the database schema.
   You don't need to run migrations by hand. It then registers a Prefect deployment for every
   job plus the daily email dispatcher.
4. **Worker**, **Streamlit app**, **web app** and **pgAdmin** start.

## 7. Check that everything is running

```powershell
docker compose ps
```

All seven containers should be `Up` (Postgres, Prefect and pgAdmin also show `healthy`):

| Service | Container | Open |
|---|---|---|
| Web app (Angular + API) | `scraper-frontend-v2` | http://localhost:8502 |
| Streamlit app | `scraper-frontend` | http://localhost:8501 |
| Scraper API (Swagger docs) | `scraper-api` | http://localhost:8000/docs |
| Prefect UI | `scraper-prefect` | http://localhost:4200 |
| pgAdmin | `scraper-pgadmin` | http://localhost:5050 (`admin@example.com` / `admin` unless set via `PGADMIN_EMAIL`/`PGADMIN_PASSWORD`) |
| Postgres | `scraper-postgres` | `localhost:5432`, user `scraper`, db `scraper_db` |
| Prefect worker | `scraper-worker` | – |

Confirm the API migrated and registered the deployments:

```powershell
docker logs scraper-api | Select-String "schema is up to date|reconciled"
```

## 8. Create the super admin

The web app is **invite-only**, so nobody can sign in until you create the first account, a
**super admin**. Run this in your own terminal (PowerShell or Windows Terminal). It asks for a
password interactively, so it won't work from inside an IDE "run" panel:

```powershell
docker exec -it scraper-frontend-v2 gt-create-super-admin --email epostgauravtalele@gmail.com --name "Gaurav Talele"
```

```
Password:            <type it; nothing is shown>
Confirm password:    <type it again>
Created super admin you@example.com
```

- Passwords must be at least 10 characters.
- Running the same command for an **existing** email resets that person's password and makes them
  an active super admin. That is also how you recover a forgotten super-admin password.
- You can create several super admins this way, or promote people from the web app (step 9).
- If you've set up local Python (section 13), `make super-admin EMAIL=you@example.com NAME="Your Name"`
  does the same thing from the host.

## 9. Use the web app

Open http://localhost:8502 and sign in with the super admin you just created.

### Roles

| Role | Dashboard | Candidates | Scraper jobs & Tags | Approve requests / invite / disable | Can grant roles |
|---|---|---|---|---|---|
| `user` | ✓ | **one**, their own (My Candidature page) | – | – | – |
| `admin` | ✓ | all: grid, add any number, edit, delete | – | users only | `user` |
| `super_admin` | ✓ | all: grid, add any number, edit, delete | ✓ | everyone except themselves | `user`, `admin`, `super_admin` |

### Add people. Option A: invite them

1. Go to **Users → Invite**.
2. Enter their email and pick a role (only super admins can invite admins).
3. Click **Send invite**. They get an email with a one-time link, and you also see the link with
   a **Copy** button. If email isn't configured, the dialog says so and you can send the link yourself.
4. They open the link, enter their name and a password, and are signed in.

Links expire after 7 days (`WEB_INVITE_TTL_DAYS`). Under **Users → Pending invitations**:
**Resend** creates a fresh link (the old one stops working) and **Revoke** cancels it.
Invite links are never stored; only a hash of the token is kept, so a lost link can't be recovered,
only resent.

### Add people. Option B: they request access

1. They open http://localhost:8502, click **Request access**, and enter name, email, password and reason.
2. Every admin and super admin is emailed about the request.
3. Until it's approved they **cannot sign in**. They see "waiting for admin approval".
4. An admin opens **Users → Access requests**, picks a role and clicks **Approve** (or **Reject**).
   The person is emailed and can then sign in with the password they chose.

A rejected person may submit a new request later.

### Manage people

Under **Users → Members**:

- **Disable** / **Enable** an account. Disabling takes effect on their very next click.
- **Change role** (super admins only), using the role drop-down.
- Nobody can disable themselves or change their own role.

### Scraper jobs (super admins only)

**Scraper jobs** lists every LinkedIn search the scraper runs, with its schedule, status, last run
and how many HR emails it has found. Every change is applied to the Prefect schedule immediately.

- **New job / Edit**: the LinkedIn search (e.g. `"Java" AND "Contract"`), a tag, how far to scroll
  the results (1–100), and when to run. Pick a schedule preset or enter a cron expression
  (`minute hour day month weekday`, India time); the form shows it in plain English.
- **Run now** (▶) starts a run immediately. Refresh to watch the status change.
- **Hold** (⏸) pauses the schedule without losing anything; **Resume** restarts it.
- **Run history** (🕒) shows each run's start time, status, record count and any error.
- **Delete** removes the job, its schedule **and the HR email records it found**. To stop a job
  but keep its data, put it on hold instead.

If Prefect is unreachable, the change is still saved and a warning tells you the schedule will be
synced the next time the scraper API starts.

### Tags (super admins only)

Tags group scrape jobs, the HR emails they find, and candidates: a candidate tagged `java` is
emailed to the HR addresses found by `java` jobs. **Tags** shows how many jobs, candidates and
email records use each one.

- **New tag**: a label (e.g. `Python Developer`) and a name (e.g. `python_developer`). The name is
  stored on jobs and candidates, so it can't be changed later; the label can.
- **Deactivate** hides a tag from new jobs and candidates; existing ones keep it.
- **Delete** is only possible when no job or candidate uses the tag.

### Candidates and dashboard

- **Dashboard** (everyone): email-record totals, emails per tag, emails per day.
- **My Candidature** (users): a user creates **one** candidature with **Create my Candidature**
  (name, contact, tag, email account + password, subject, HTML body, resume `.pdf`/`.docx`) and
  can edit it later on the same page. They can't see anyone else's candidates, and can't delete
  their own (ask an admin).
- **Candidates** (admins and super admins only): a grid of every candidate with its **Owner**
  (the account that created it; `—` for ones added through Streamlit or scripts). Admins can add
  any number of candidates, and edit or delete any of them.

These rules are enforced by the API, not just hidden in the UI. Saved email passwords are never
shown again; leave the field blank when editing to keep the current one. Resumes are stored in
`runtime/resumes/<candidate_name>/`.

> The **Streamlit app** has a single shared login with no roles, so anyone with that login can
> see and edit every candidate there.

## 10. Run a scrape

Scrapes run automatically on each job's schedule. To run one now, the easiest way is
**Scraper jobs → ▶ Run now** in the web app (super admin). Alternatively:

```powershell
# Through the scraper API (job id 1)
Invoke-RestMethod -Method Post http://localhost:8000/trigger/1

# Through Prefect (each deployment already knows its job id)
docker exec scraper-worker prefect deployment run scrape-single-job/scrape-job-1
```

You can also open the Prefect UI (http://localhost:4200) → **Deployments** → `scrape-job-1` → **Run**.

Follow it in the Prefect UI or with `docker logs -f scraper-worker`. Results land in the
`email_records` table (visible on both dashboards) and as CSVs in `runtime/extract/<dd-mm-yyyy>/`.

The first run logs in to LinkedIn and saves the session to `runtime/data/auth_state.json`, so
later runs reuse it. Each failed login attempt saves a screenshot to `runtime/debug/`. If LinkedIn
shows a security checkpoint, the job is marked `error`.

### Watching a run in Prefect

Open http://localhost:4200, then **Runs**. Scrape runs are named `scrape-job-<id>`, and email runs `hr-email-dispatcher-<date>`
(with one `hr-email-dispatcher-candidate-<name>` sub-run per candidate).

- **Logs tab**: every step, numbered and timed, with the details inline. For example:
  ```
  ══ Scrape job #1: started ══
  ▶ Step 1/8: Load job settings
     • Search: "Java" AND "Contract"
  ✓ Step 1/8 done in 0.1s: Load job settings
  ▶ Step 3/8: Log in to LinkedIn
  Trying the saved LinkedIn session from runtime/data/auth_state.json
  Session restored from auth state
  ...
     • Scroll 3/5: page is 812 KB, 9 unique email(s) visible so far
  ...
  ══ Scrape job #1: finished in 1m 12s. 14 email(s) and 6 post(s) saved ══
  ```
  Failures say which step broke and why, plus a **What to do** hint for login or security-check problems.
- **Artifacts tab**: a summary report (result, duration, counts, and a table of steps with their timings).
- **State**: a run whose scrape or emails failed now shows **Failed** (red), not Completed.

The same steps also go to `docker logs -f scraper-worker`.

## 11. Send candidate emails

The **hr-email-dispatcher** deployment runs daily at 05:00 (Asia/Kolkata). For every **active**
candidate it emails each scraped HR address with the same tag, attaching the candidate's resume.
To run it now:

```powershell
docker exec scraper-worker prefect deployment run hr-email-dispatcher/hr-email-dispatcher
```

## 12. Day-to-day operations

| Task | Command |
|---|---|
| Stop everything (data is kept) | `docker compose down` |
| Start again | `docker compose up -d` |
| Apply code changes | `docker compose up -d --build` |
| Rebuild one service | `docker compose up -d --build frontend-v2` |
| Follow logs | `docker compose logs -f api worker frontend-v2` |
| Apply new migrations | Automatic on API start, or `docker compose restart api` |
| Re-sync all Prefect schedules from the database | `docker compose restart api` |
| Open a SQL shell | `docker exec -it scraper-postgres psql -U scraper -d scraper_db` |

**Where the data lives:**

- **Database**: the `postgres_data` Docker volume. Back it up with:
  ```powershell
  docker exec scraper-postgres pg_dump -U scraper scraper_db > backup.sql
  ```
- **Files**: the `runtime/` folder (see [runtime/README.md](runtime/README.md)): resumes, LinkedIn
  session, logs, CSV extracts, debug screenshots. Back up `runtime/resumes` and `runtime/data`.

**Start from scratch** (deletes the database):

```powershell
docker compose down -v
docker compose up -d --build
```

Then create the super admin again (step 8).

## 13. Local development (without Docker for the apps)

Run Postgres, Prefect and pgAdmin in Docker, and the Python/Angular processes on your machine
with auto-reload:

```powershell
# One-time setup
python -m venv .venv
.venv\Scripts\Activate.ps1                       # bash: source .venv/bin/activate
pip install -e ".[dev,streamlit]"
playwright install chromium
cd apps/web; npm install; cd ../..

# Infrastructure only
docker compose up -d postgres prefect-server pgadmin

# Database
python scripts/migrate.py
python -m gt_linkedin_scraper.web.cli --email you@example.com --name "Your Name"   # first time only
```

Then run each of these in its own terminal (with the venv activated):

| What | Command | URL |
|---|---|---|
| Scraper API | `uvicorn gt_linkedin_scraper.api.main:app --port 8000 --reload` | :8000 |
| Prefect worker | `python scripts/start_worker.py` | – |
| Streamlit | `streamlit run apps/streamlit/app.py --server.port=8501 --secrets.files=apps/streamlit/.streamlit/secrets.toml` | :8501 |
| Web API | `uvicorn gt_linkedin_scraper.web.app:app --port 8502 --reload --reload-dir src` | :8502 |
| Angular dev server | `cd apps/web; npm start` | :4300 (proxies `/api` to :8502) |

`.env` already points at `localhost`, so no changes are needed. Don't run the full Docker stack at
the same time, because the ports would clash. Other helpers in `scripts/`:

| Script | Purpose |
|---|---|
| `run_job_local.py <id>` | Run a scrape job directly, without Prefect |
| `run_job_directly.py` | Trigger job 1 through Prefect and wait for it |
| `list_jobs.py` | Print jobs and their status |
| `seed_jobs.py` | Reload `config/jobs.yaml` into the database (overwrites jobs with the same id) |
| `insert_candidate_from_email.py` | Insert the candidate defined in the script |
| `monitor_task.py` | Poll a Prefect flow run's task states |

VS Code launch configurations for most of these are in `.vscode/launch.json`.

## 14. Tests

```powershell
pip install -e ".[dev,streamlit]"   # once
pytest
```

The suite (web API auth, invitations, roles, candidates, and the Streamlit pages) runs against a
throwaway SQLite database, so you don't need Docker for it.

## 15. Configuration reference

All settings are defined in [src/gt_linkedin_scraper/core/config.py](src/gt_linkedin_scraper/core/config.py)
and read from environment variables or `.env`.

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | localhost asyncpg URL | Async DB (scraper API, flows, Alembic) |
| `DATABASE_URL_SYNC` | localhost psycopg2 URL | Sync DB (Streamlit, web API, scripts) |
| `LINKEDIN_USERNAME` / `LINKEDIN_PASSWORD` | – | Scraper's LinkedIn login |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` / `SMTP_FROM` | Gmail, 587 | Outgoing email |
| `TAG_RECIPIENTS__<TAG>` / `TAG_RECIPIENTS__DEFAULT` | – | Scrape-report recipients |
| `PREFECT_API_URL` | `http://localhost:4200/api` | Prefect server |
| `JOBS_CONFIG_PATH` | `config/jobs.yaml` | Jobs seeded into an empty database |
| `LOG_LEVEL` / `LOG_FORMAT` | `INFO` / `json` | Logging |
| `RESUME_UPLOAD_DIR` | `runtime/resumes` | Candidate resumes |
| `AUTH_STATE_PATH` | `runtime/data/auth_state.json` | Saved LinkedIn session |
| `LOG_DIR` / `EXTRACT_DIR` / `DEBUG_DIR` | `runtime/logs` / `runtime/extract` / `runtime/debug` | Logs, CSV extracts, login screenshots |
| `WEB_SECRET_KEY` | random per start | Signs web-app sessions |
| `WEB_PUBLIC_URL` | request URL | Base URL in invite links |
| `WEB_TOKEN_TTL` | `43200` (12 h) | Web session length, in seconds |
| `WEB_INVITE_TTL_DAYS` | `7` | Invite link validity |
| `WEB_STATIC_DIR` | `apps/web/dist/web/browser` | Built Angular app served by the web API |

## 16. Troubleshooting

| Symptom | Fix |
|---|---|
| `port is already allocated` | Another program (or a local dev server) uses that port. Stop it, or change the left-hand port in `docker-compose.yml`. |
| Build fails with `Read timed out` / `EOF` from PyPI or Docker Hub | Network hiccup. Run `docker compose up -d --build` again. |
| Web app: "Invalid email or password" for a brand-new install | No account exists yet. Do step 8. |
| Web app: signed out after a restart | Set `WEB_SECRET_KEY` in `.env`, then `docker compose up -d frontend-v2`. |
| Invitation dialog says the email couldn't be sent | Check the `SMTP_*` values (Gmail needs an App Password). Meanwhile, copy the link from the dialog. |
| "Too many failed attempts" at sign-in | Wait 15 minutes, or `docker compose restart frontend-v2`. |
| Forgot the super-admin password | Re-run the step 8 command with the same email. |
| `docker exec -it` says "the input device is not a TTY" | Run it in PowerShell or Windows Terminal, not an IDE output panel. |
| Streamlit shows a `secrets` error | Create `apps/streamlit/.streamlit/secrets.toml` (step 4). |
| API log shows `Deployer failed` | Prefect wasn't reachable. Run `docker compose restart api`. |
| `migrate.py`: "Database has tables but no alembic_version" | The database was created outside the migrations. If its schema matches the models, run `alembic stamp head` once. |
| Scrape job ends in `error` | Check `docker logs scraper-worker` and the screenshots in `runtime/debug/`; LinkedIn may need a manual login or checkpoint. |
| `make` isn't recognised | Use the plain commands in this README, or install make (`choco install make`). |

More background and known gaps: [docs/known-issues.md](docs/known-issues.md).

## 17. Project layout

```
.
├── src/gt_linkedin_scraper/     Python package (pip install -e .)
│   ├── api/                     Scraper REST API (FastAPI, :8000)
│   ├── web/                     Web-app API (FastAPI, :8502): auth, invites, users, candidates
│   │   ├── routes/              auth, admin (users/invites), candidates, jobs, tags
│   │   └── cli.py               gt-create-super-admin
│   ├── core/                    Settings, async + sync DB sessions, logging
│   ├── crawler/                 Playwright LinkedIn crawler and parser
│   ├── scheduler/               Prefect flows and tasks; deployments.py syncs jobs to Prefect
│   ├── notifier/                Email reports
│   ├── models/                  SQLAlchemy models
│   └── storage/                 Repositories and resume file storage
├── apps/
│   ├── streamlit/               Streamlit UI (:8501)
│   └── web/                     Angular 17 UI (built into the web-app image)
├── alembic/                     Database migrations
├── config/jobs.yaml             Initial scrape jobs (seeded into an empty database)
├── docker/postgres/initdb/      Postgres init SQL (creates the prefect database)
├── scripts/                     migrate, seed, worker, run/inspect jobs, add a candidate
├── tests/                       pytest suite
├── docs/                        Known issues, SQL snippets, sample HTTP requests
├── runtime/                     Files the app writes (git-ignored, mounted into containers)
├── Dockerfile                   Scraper image (API + worker)
├── docker-compose.yml           The whole stack
├── Makefile                     Shortcuts (make help)
└── .env.example                 Configuration template
```
