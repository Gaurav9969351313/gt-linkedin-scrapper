# Known issues and history

Carried over from the original README.

## Missing features / known issues

| Feature | Status | Notes |
|---|---|---|
| **Testing** | Missing | Explicitly excluded per plan, but no test scaffolding exists |
| **Alembic migrations** | Partial | `alembic/` dir + `env.py` exist, but no real migration scripts yet |
| **Windows service** | Dropped | Replaced by Docker + native Python deployment |
| **Proxy rotation** | Not implemented | Architecture supports it; not implemented now |
| **Tag recipient validation** | Partial | Map is configurable via env, but no validation that all tags have recipients |
| **Prefect healthcheck** | Failing | Prefect server shows `unhealthy` in Docker; needs manual DB setup or init script |
| **Auth state persistence** | Partial | Cookie save/load implemented, but `storage_state.json` path not used |
| **LinkedIn checkpoint handling** | Partial | Detects checkpoint, sets job to `error`, but no alerting/webhook |
| **Email delivery failure isolation** | Partial | Notification failure is logged, but not fully isolated from flow success |
| **CSV attachment size guard** | Missing | No 10MB split logic implemented |
| **Migration script from old DB** | Missing | Clean break; old `scheduler.db` not migrated |
| **Multi-cloud/K8s deployment** | Out of scope | Not planned |

## Errors encountered and fixes

| Error | Root Cause | Fix Applied |
|---|---|---|
| `setuptools.backends.legacy:build` backend unavailable | Invalid build backend in `pyproject.toml` | Changed to `setuptools.build_meta` |
| `playwright_stealth.stealth_async` import error | API changed in newer version | Removed stealth import; not critical for basic functionality |
| `ModuleNotFoundError: No module named 'bs4'` | `beautifulsoup4` missing from Docker dependencies | Added `beautifulsoup4>=4.12.2` to `pyproject.toml` dependencies |
| `database "prefect" does not exist` | Prefect server DB not created | Created `prefect` database manually via `docker exec` |
| Prefect server unhealthy | Healthcheck uses `curl` which may not be available | Adjusted healthcheck; server runs but shows unhealthy due to curl |
| `src does not exist or is not a directory` | Docker build context issue with editable install | Moved `COPY src/` before `pip install -e .` in Dockerfile |
| Editable install metadata error | Setuptools deprecation warnings + missing README | Simplified install, ensured `README.md` exists |

## Next steps

1. Fix Prefect server healthcheck or use `curl`-based check
2. Add Alembic migration scripts for schema changes
3. Implement test scaffolding
4. Add proxy rotation support
5. Implement CSV attachment size guard
6. Add webhook/alerting for LinkedIn checkpoint detection
7. Add validation for tag recipient configuration
