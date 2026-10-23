# runtime/

Files the application writes while it runs. Everything here except this README is git-ignored,
and the whole folder is mounted into every container as `/app/runtime`.

| Folder     | Contents                                      | Setting             |
|------------|-----------------------------------------------|---------------------|
| `resumes/` | Candidate resumes (`<candidate_slug>/<file>`) | `RESUME_UPLOAD_DIR` |
| `data/`    | LinkedIn session (`auth_state.json`)          | `AUTH_STATE_PATH`   |
| `logs/`    | Application logs (`app.log`)                  | `LOG_DIR`           |
| `extract/` | Daily CSV extracts (`dd-mm-yyyy/`)            | `EXTRACT_DIR`       |
| `debug/`   | Screenshots/HTML from failed LinkedIn logins  | `DEBUG_DIR`         |

Folders are created on first use. Back up `resumes/` and `data/`; the rest can be regenerated.
