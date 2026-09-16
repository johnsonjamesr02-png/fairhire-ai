# FairHire AI

[![tests](https://github.com/johnsonjamesr02-png/fairhire-ai/actions/workflows/tests.yml/badge.svg)](https://github.com/johnsonjamesr02-png/fairhire-ai/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](requirements.txt)

**AI-powered resume screening with a built-in legal fairness audit.**

**[Live project page & demo walkthrough →](https://johnsonjamesr02-png.github.io/fairhire-ai/)**

Most "AI resume screener" projects stop at matching keywords to a job
description. FairHire AI adds the piece that actually matters to an
employer: it audits its own hiring recommendations for disparate impact
under the same statistical test regulators use — the EEOC's four-fifths
rule (29 CFR 1607.4(D)) and NYC Local Law 144's bias-audit requirement for
Automated Employment Decision Tools (AEDTs).

The pitch in one sentence: **a hiring AI's accuracy and its legal exposure
should be measured together, not separately** — this project does both, end
to end, in one pipeline.

## Why this project

Local Law 144 (in effect since 2023, actively enforced in 2026) requires
NYC employers to commission an independent bias audit before using an AEDT
on candidates, publish the results, and give candidates notice. The
underlying math — selection rate by demographic group, impact ratio,
flagged if under 80% — is exactly what `backend/bias_audit.py` implements.
Building that logic (not just an LLM wrapper) is what makes this project
different from a weekend "ChatGPT resume matcher."

## Architecture

```
Resume text ──┐
              ├──▶ ai_service.parse_resume() ──┐
Job desc text ┘                                 ├──▶ ai_service.score_candidate() ──▶ fit score + rationale
              └──▶ ai_service.parse_job_description() ┘
                                                              │
                                              (join with EEO group label,
                                               collected separately —
                                               never seen by the scorer)
                                                              │
                                                              ▼
                                          bias_audit.run_four_fifths_audit()
                                                              │
                                                              ▼
                                          selection rate / impact ratio / flagged groups
```

- **`backend/ai_service.py`** — all Claude API calls. Resume/JD parsing and
  candidate scoring are all done as *structured JSON output* (a fixed
  schema in the system prompt), so the LLM acts as a reasoning component
  inside a normal pipeline rather than a chatbot you have to regex-scrape.
  The scoring prompt explicitly instructs the model to ignore name/gender/
  age/etc. and score qualifications only. Ships with a `DEMO_MODE` that
  runs the whole pipeline offline with deterministic stand-in logic, so it
  works out of the box with no API key — set `ANTHROPIC_API_KEY` to switch
  to live calls with no code changes.
- **`backend/bias_audit.py`** — pure Python/dataclasses, no LLM involved.
  Computes per-group selection rates and impact ratios and flags anything
  under the four-fifths threshold. Deliberately kept independent of
  whatever scoring model feeds it, so it could audit *any* hiring tool's
  decisions, not just this one.
- **`backend/main.py`** — FastAPI app exposing both as REST endpoints.
- **`frontend/`** — a small dashboard that calls the API and renders the
  ranking + audit report. (`fairhire-ai-demo.html`, shared alongside this
  project, is a static snapshot of one run for quick viewing without
  standing up the backend.)
- **`data/`** — synthetic sample resumes, a sample JD, and a synthetic EEO
  demographic file (`synthetic_demographics.csv`) kept as a **separate**
  file from the resumes on purpose — that separation is the point, not an
  accident.
- **`tests/test_bias_audit.py`** — 7 unit tests covering the exact edge
  case that matters most: a ratio of exactly 0.80 must *not* be flagged,
  0.79 must be.

## Design decisions worth explaining in an interview

1. **Demographic data never touches the scoring model.** It's joined to
   results only afterward, for audit purposes — mirroring how real EEO
   self-ID data is collected separately from applications. An AI system
   that infers race/gender from a resume to "check for bias" would itself
   be a bias risk.
2. **The audit module has no idea what produced the scores.** It takes any
   list of `{group, selected}` and audits it. That means it's reusable
   against a completely different scoring method later without touching
   this file — a common ask in real MLOps/compliance work.
3. **Structured output, not chat.** Every LLM call returns a fixed JSON
   schema, validated before anything downstream touches it. This is the
   difference between "I used the ChatGPT API" and "I built an LLM into a
   software pipeline."
4. **Offline demo mode by design**, not as an afterthought — it's what let
   this ship as a fully working, testable project without needing to
   spend API credits for every run, and it's a realistic pattern for
   local dev against any paid API.

## Setup

```bash
cd fairhire-ai
pip install -r requirements.txt

# Works immediately with no key, using offline demo-mode logic:
python scripts/run_demo.py

# Run the test suite:
python -m pytest tests/ -v

# For live Claude API calls instead of demo mode:
export ANTHROPIC_API_KEY=your-key-here
python scripts/run_demo.py

# Run the API server:
cd backend && uvicorn main:app --reload --port 8000
# then open frontend/index.html (update API_BASE in app.js if needed)
```

## Honest limitations (worth naming, not hiding)

- The demo-mode scorer is simple keyword/years matching — a stand-in for
  the LLM, not a claim that keyword matching is good hiring practice. The
  real scoring happens through Claude when `ANTHROPIC_API_KEY` is set.
- Eight synthetic candidates is enough to demonstrate and unit-test the
  math, not enough to be statistically meaningful — a real audit needs a
  real applicant pool.
- This is a personal/portfolio project, not a compliance product. A real
  AEDT bias audit must be conducted by an independent auditor under Local
  Law 144 — this project demonstrates understanding of that requirement,
  it doesn't satisfy it.

## Roadmap ideas

- Swap keyword skill-matching for real embeddings similarity as a second
  signal alongside the LLM score.
- Add intersectional group analysis (e.g., Black women vs. all others),
  which Local Law 144 audits require alongside single-category analysis.
- Persist run history so selection rates can be tracked over time, not
  just per-run.
