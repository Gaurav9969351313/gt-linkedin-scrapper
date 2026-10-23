# Web app (Angular 17)

Invite-only Angular UI. Its API is the `gt_linkedin_scraper.web` package
(`src/gt_linkedin_scraper/web/`), which also serves this app's production build on **:8502**.

```
apps/web/src/app/
├── core/       API client, auth service/guards/interceptor, models
├── layout/     App shell (sidebar, user menu)
├── pages/      login, request-access, accept-invite, dashboard, candidates, my-candidature,
│               jobs (scraper jobs), tags, users
└── shared/     Icon and bar-chart components
```

## Access model

An account becomes **active** in one of two ways:

1. **Invitation**: an admin invites an email address. The invitee gets an email (and the admin
   sees a one-time copyable link), sets a name and password, and is signed in.
2. **Access request**: the person submits name, email, password and a reason at
   `/request-access`. The account is **pending** and cannot sign in until an admin approves it.

| Role          | Candidates                          | Approve / invite / disable | Grant roles                    |
|---------------|-------------------------------------|----------------------------|--------------------------------|
| `user`        | one, their own (`/my-candidature`) | –                          | –                              |
| `admin`       | all (`/candidates` grid), unlimited | users only                 | `user`                         |
| `super_admin` | all (`/candidates` grid), unlimited | everyone (except self)     | `user`, `admin`, `super_admin` |

Everyone sees the dashboard. Only admins can delete candidates. **Scraper jobs** (`/jobs`) and
**Tags** (`/tags`) are super admin only (route guard + API).

Disabling an account or changing a role takes effect on the user's next request.

## Development

From the repo root:

```bash
make web-install    # once
make web-api        # API on http://localhost:8502
make web            # Angular dev server on http://localhost:4300 (proxies /api to :8502)
```

`make web-build` writes `apps/web/dist/web/browser`, which `make web-api` then serves on :8502.

## Docker

`docker compose up -d --build frontend-v2` builds this app and the API into one image
(`apps/web/Dockerfile`, build context = repo root).
