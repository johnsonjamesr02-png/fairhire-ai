from pydantic import BaseModel


class ResumeInput(BaseModel):
    resume_text: str
    demographic_group: str | None = None  # optional, for bias-audit testing only


class JobDescriptionInput(BaseModel):
    jd_text: str


class ScoreRequest(BaseModel):
    candidate_profile: dict
    job_requirements: dict


class AuditCandidate(BaseModel):
    demographic_group: str
    selected: bool


class AuditRequest(BaseModel):
    candidates: list[AuditCandidate]
