"""
ai_service.py

Wraps all calls to the Claude API for FairHire AI:
  1. parse_resume        — unstructured resume text -> structured JSON
  2. parse_job_description — unstructured JD text -> structured requirements
  3. score_candidate      — structured resume + JD -> fit score + rationale

Design notes for whoever picks this up (including future-you in an interview):

- All three functions ask Claude for STRICT JSON and validate/parse it with
  json.loads, so the rest of the app never has to regex-scrape a model's
  prose. This is the "structured output" pattern for using an LLM as a
  reasoning component inside a normal software pipeline, rather than as a
  chatbot.
- DEMO_MODE (default True unless ANTHROPIC_API_KEY is set) returns
  deterministic canned responses so the whole pipeline — parsing, scoring,
  and the bias audit — can be demoed, tested, and screen-recorded without
  spending API credits or requiring a key. Flip it off by exporting a real
  ANTHROPIC_API_KEY and it calls the live API instead. Same interface either
  way, which is the point.
- Swap MODEL for whatever's current when you pick this back up — check
  Anthropic's docs, since model names/versions change.
"""

import json
import os
import re

MODEL = "claude-sonnet-4-6"
DEMO_MODE = os.environ.get("ANTHROPIC_API_KEY") is None


def _extract_json(text: str) -> dict:
    """Claude sometimes wraps JSON in ```json fences despite instructions; strip them."""
    cleaned = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    return json.loads(cleaned)


def _call_claude(system: str, user_message: str) -> str:
    """Thin wrapper so main.py/tests never import the SDK directly."""
    import anthropic

    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env
    response = client.messages.create(
        model=MODEL,
        max_tokens=1500,
        system=system,
        messages=[{"role": "user", "content": user_message}],
    )
    return "".join(block.text for block in response.content if block.type == "text")


PARSE_RESUME_SYSTEM = """You are a resume-parsing engine used inside a hiring pipeline.
Extract structured data from the candidate's resume text. Respond with ONLY a JSON
object — no prose, no markdown fences — matching exactly this shape:
{
  "candidate_name": string,
  "years_experience": number,
  "education": [{"degree": string, "field": string, "institution": string}],
  "skills": [string],
  "certifications": [string]
}
If a field is unknown, use an empty list, empty string, or 0 as appropriate. Never
invent facts not present in the resume."""

PARSE_JD_SYSTEM = """You are a job-description parsing engine used inside a hiring pipeline.
Extract structured requirements from the job description text. Respond with ONLY a
JSON object — no prose, no markdown fences — matching exactly this shape:
{
  "title": string,
  "required_skills": [string],
  "preferred_skills": [string],
  "min_years_experience": number,
  "required_education": string
}"""

SCORE_CANDIDATE_SYSTEM = """You are a candidate-fit scoring engine used inside a hiring
pipeline. You will be given a structured candidate profile and structured job
requirements. Score how well the candidate fits the role on a 0-100 scale based
ONLY on demonstrated skills, experience, and education relative to the stated
requirements. Do not consider or infer the candidate's name, gender, age, race,
national origin, or any other protected characteristic — score qualifications only.
Respond with ONLY a JSON object — no prose, no markdown fences:
{
  "fit_score": number,
  "matched_required_skills": [string],
  "missing_required_skills": [string],
  "rationale": string
}"""


def parse_resume(resume_text: str) -> dict:
    if DEMO_MODE:
        return _demo_parse_resume(resume_text)
    raw = _call_claude(PARSE_RESUME_SYSTEM, resume_text)
    return _extract_json(raw)


def parse_job_description(jd_text: str) -> dict:
    if DEMO_MODE:
        return _demo_parse_jd(jd_text)
    raw = _call_claude(PARSE_JD_SYSTEM, jd_text)
    return _extract_json(raw)


def score_candidate(candidate_profile: dict, job_requirements: dict) -> dict:
    if DEMO_MODE:
        return _demo_score(candidate_profile, job_requirements)
    user_message = json.dumps(
        {"candidate_profile": candidate_profile, "job_requirements": job_requirements}
    )
    raw = _call_claude(SCORE_CANDIDATE_SYSTEM, user_message)
    return _extract_json(raw)


# ---------------------------------------------------------------------------
# Demo-mode fallbacks: lightweight deterministic logic standing in for the
# LLM so `scripts/run_demo.py` works out of the box with no API key. Not
# meant to be "as good as" the real model — just realistic enough to
# exercise the whole pipeline and the bias-audit math end to end.
# ---------------------------------------------------------------------------

def _demo_parse_resume(resume_text: str) -> dict:
    lines = [l.strip() for l in resume_text.splitlines() if l.strip()]
    name = lines[0] if lines else "Unknown Candidate"
    years_match = re.search(r"(\d+)\+?\s+years?", resume_text, re.IGNORECASE)
    years = int(years_match.group(1)) if years_match else 0
    skills_line = next((l for l in lines if l.lower().startswith("skills:")), "")
    skills = [s.strip() for s in skills_line.split(":", 1)[1].split(",")] if skills_line else []
    return {
        "candidate_name": name,
        "years_experience": years,
        "education": [],
        "skills": skills,
        "certifications": [],
    }


def _demo_parse_jd(jd_text: str) -> dict:
    lines = [l.strip() for l in jd_text.splitlines() if l.strip()]
    title = lines[0] if lines else "Unknown Role"
    req_line = next((l for l in lines if l.lower().startswith("required skills:")), "")
    required = [s.strip() for s in req_line.split(":", 1)[1].split(",")] if req_line else []
    years_match = re.search(r"(\d+)\+?\s+years?", jd_text, re.IGNORECASE)
    min_years = int(years_match.group(1)) if years_match else 0
    return {
        "title": title,
        "required_skills": required,
        "preferred_skills": [],
        "min_years_experience": min_years,
        "required_education": "",
    }


def _demo_score(candidate_profile: dict, job_requirements: dict) -> dict:
    cand_skills = {s.lower() for s in candidate_profile.get("skills", [])}
    req_skills = [s for s in job_requirements.get("required_skills", []) if s]
    matched = [s for s in req_skills if s.lower() in cand_skills]
    missing = [s for s in req_skills if s.lower() not in cand_skills]

    skill_component = (len(matched) / len(req_skills) * 70) if req_skills else 35
    years_needed = job_requirements.get("min_years_experience", 0)
    years_have = candidate_profile.get("years_experience", 0)
    experience_component = 30 if years_have >= years_needed else 30 * (
        years_have / years_needed if years_needed else 1
    )
    fit_score = round(skill_component + experience_component, 1)

    return {
        "fit_score": min(fit_score, 100),
        "matched_required_skills": matched,
        "missing_required_skills": missing,
        "rationale": (
            f"Matched {len(matched)}/{len(req_skills)} required skills; "
            f"{years_have} years experience vs. {years_needed} required."
        ),
    }
