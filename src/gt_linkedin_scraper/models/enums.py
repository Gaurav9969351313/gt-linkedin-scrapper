import enum


class JobStatus(str, enum.Enum):
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"
    HOLD = "hold"


# Tags used to be an enum here; they are now rows in the `tags` table
# (models/tag.py), managed by super admins in the web app.
