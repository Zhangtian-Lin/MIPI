from dataclasses import dataclass
from typing import Literal
from uuid import UUID

SourceGrade = Literal["S1", "S2", "S3", "S4", "S5", "S6"]
SourceStatus = Literal["candidate", "trial", "active", "degraded", "inactive", "retired"]


@dataclass(frozen=True)
class SourceRegistration:
    public_id: str
    name: str
    owner: str
    base_url: str
    source_grade: SourceGrade
    authority_scope: tuple[str, ...]
    languages: tuple[str, ...]


@dataclass(frozen=True)
class SourceRecord:
    internal_id: UUID
    public_id: str
    name: str
    owner: str
    base_url: str
    source_grade: SourceGrade
    authority_scope: tuple[str, ...]
    languages: tuple[str, ...]
    status: SourceStatus
    crawl_status: str


@dataclass(frozen=True)
class SourceRegistrationResult:
    source: SourceRecord
    duplicate: bool


class SourceNotFoundError(Exception):
    pass


class SourceConflictError(Exception):
    pass
