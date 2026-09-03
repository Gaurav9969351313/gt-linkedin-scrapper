import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Ensure critical paths are absolute so flows running from temp dirs can still find them
project_root = Path(__file__).parent
os.environ.setdefault("AUTH_STATE_PATH", str(project_root / "data" / "auth_state.json"))
os.environ.setdefault("JOBS_CONFIG_PATH", str(project_root / "config" / "jobs.yaml"))

# Pass through to prefect worker
os.execvp(sys.executable, [sys.executable, "-m", "prefect", "worker", "start", "--pool", "default"])
