import enum


class JobStatus(str, enum.Enum):
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"
    HOLD = "hold"
    DELETED = "deleted"


class Tag(str, enum.Enum):
    DEVOPS = "devops"
    JAVA = "java"
    QA = "qa"
    FRESHERS = "freshers"
    DATA_ENGINEER = "data_engineer"
