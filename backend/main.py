"""
main.py — FairHire AI backend

Run with:
    uvicorn main:app --reload --port 8000

Endpoints:
    POST /parse-resume            -> structured candidate profile
    POST /parse-job-description   -> structured job requirements
    POST /score-candidate         -> fit score + rationale
    POST /bias-audit              -> EEOC four-fifths rule audit report
    GET  /demo/full-pipeline      -> runs the sample data end to end (see scripts/run_demo.py
                                      for the same thing as a standalone CLI script)
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

import ai_service
import bias_audit
from models import ResumeInput, JobDescriptionInput, ScoreRequest, AuditRequest

app = FastAPI(title="FairHire AI", version="0.1.0")

# Wide-open CORS for local development against the demo frontend only.
# Lock this down before deploying anywhere real.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok", "demo_mode": ai_service.DEMO_MODE}


@app.post("/parse-resume")
def parse_resume(payload: ResumeInput):
    try:
        return ai_service.parse_resume(payload.resume_text)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Resume parsing failed: {e}")


@app.post("/parse-job-description")
def parse_job_description(payload: JobDescriptionInput):
    try:
        return ai_service.parse_job_description(payload.jd_text)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Job description parsing failed: {e}")


@app.post("/score-candidate")
def score_candidate(payload: ScoreRequest):
    try:
        return ai_service.score_candidate(payload.candidate_profile, payload.job_requirements)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Scoring failed: {e}")


@app.post("/bias-audit")
def run_bias_audit(payload: AuditRequest):
    try:
        candidates = [c.model_dump() for c in payload.candidates]
        report = bias_audit.run_four_fifths_audit(candidates)
        return report.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
