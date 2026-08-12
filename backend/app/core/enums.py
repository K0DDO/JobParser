from datetime import datetime
from enum import StrEnum


class SourceName(StrEnum):
    HH = "hh"
    HABR = "habr"
    HIRIFY = "hirify"
    TALANTO = "talanto"
    GETMATCH = "getmatch"


class VacancyStatus(StrEnum):
    NEW = "new"
    MATCHED = "matched"
    IGNORED = "ignored"
    EXPIRED = "expired"


class WorkFormat(StrEnum):
    REMOTE = "remote"
    HYBRID = "hybrid"
    OFFICE = "office"
    UNKNOWN = "unknown"


class ExperienceLevel(StrEnum):
    NO_EXPERIENCE = "no_experience"
    BETWEEN_1_AND_3 = "between_1_and_3"
    BETWEEN_3_AND_6 = "between_3_and_6"
    MORE_THAN_6 = "more_than_6"
    UNKNOWN = "unknown"


class ApplicationStatus(StrEnum):
    DISCOVERED = "discovered"
    MATCHED = "matched"
    QUEUED = "queued"
    APPLIED = "applied"
    VIEWED = "viewed"
    RESPONSE = "response"
    INTERVIEW = "interview"
    TEST_TASK = "test_task"
    OFFER = "offer"
    REJECTED = "rejected"
    IGNORED = "ignored"
    FAILED = "failed"
    DRY_RUN = "dry_run"


class LogLevel(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    SUCCESS = "success"


class QueueItemStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"
    DRY_RUN = "dry_run"


def utcnow() -> datetime:
    from app.core.timeutil import utc_now_naive

    return utc_now_naive()
