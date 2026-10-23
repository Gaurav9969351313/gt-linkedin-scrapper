import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Ensure critical paths are absolute so flows running from temp dirs can still find them
project_root = Path(__file__).resolve().parent.parent
runtime = project_root / "runtime"
os.environ.setdefault("JOBS_CONFIG_PATH", str(project_root / "config" / "jobs.yaml"))
os.environ.setdefault("AUTH_STATE_PATH", str(runtime / "data" / "auth_state.json"))
os.environ.setdefault("RESUME_UPLOAD_DIR", str(runtime / "resumes"))
os.environ.setdefault("LOG_DIR", str(runtime / "logs"))
os.environ.setdefault("EXTRACT_DIR", str(runtime / "extract"))
os.environ.setdefault("DEBUG_DIR", str(runtime / "debug"))
# Show the scraper's own log lines in each Prefect run's Logs tab.
os.environ.setdefault("PREFECT_LOGGING_EXTRA_LOGGERS", "gt_linkedin_scraper")

# Pass through to prefect worker
os.execvp(sys.executable, [sys.executable, "-m", "prefect", "worker", "start", "--pool", "default"])
