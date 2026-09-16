"""
run_demo.py — runs the full FairHire AI pipeline against the sample data,
with no server required. Good for a quick sanity check or a terminal demo
in an interview.

Usage:
    cd fairhire-ai
    python scripts/run_demo.py
"""

import csv
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import ai_service
import bias_audit

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
SELECTION_CUTOFF = 60  # fit_score >= cutoff => "selected" for audit purposes


def load_demographics():
    path = os.path.join(DATA_DIR, "synthetic_demographics.csv")
    with open(path) as f:
        return {row["candidate_file"]: row["demographic_group"] for row in csv.DictReader(f)}


def main():
    print(f"DEMO_MODE = {ai_service.DEMO_MODE} "
          f"({'no ANTHROPIC_API_KEY set — using offline stand-in logic' if ai_service.DEMO_MODE else 'calling live Claude API'})\n")

    with open(os.path.join(DATA_DIR, "sample_job_description.txt")) as f:
        jd_text = f.read()
    job_requirements = ai_service.parse_job_description(jd_text)
    print("Job requirements:")
    print(json.dumps(job_requirements, indent=2), "\n")

    demographics = load_demographics()
    resume_dir = os.path.join(DATA_DIR, "sample_resumes")
    results = []

    for filename in sorted(os.listdir(resume_dir)):
        with open(os.path.join(resume_dir, filename)) as f:
            resume_text = f.read()
        profile = ai_service.parse_resume(resume_text)
        score = ai_service.score_candidate(profile, job_requirements)
        selected = score["fit_score"] >= SELECTION_CUTOFF
        results.append({
            "file": filename,
            "name": profile["candidate_name"],
            "fit_score": score["fit_score"],
            "selected": selected,
            "demographic_group": demographics[filename],
            "rationale": score["rationale"],
        })

    results.sort(key=lambda r: r["fit_score"], reverse=True)
    print(f"{'Candidate':<16}{'Fit Score':<12}{'Selected':<10}{'Group':<10}Rationale")
    for r in results:
        print(f"{r['name']:<16}{r['fit_score']:<12}{str(r['selected']):<10}{r['demographic_group']:<10}{r['rationale']}")

    print("\nRunning bias audit (EEOC four-fifths rule)...\n")
    audit_input = [{"demographic_group": r["demographic_group"], "selected": r["selected"]} for r in results]
    report = bias_audit.run_four_fifths_audit(audit_input)
    print(json.dumps(report.to_dict(), indent=2))

    if not report.passes_four_fifths_rule:
        print(f"\n⚠ FLAGGED: {report.flagged_groups} fall below the 80% four-fifths threshold "
              f"relative to {report.reference_group}. Under NYC Local Law 144, this tool would "
              f"need further investigation before use in a covered jurisdiction.")
    else:
        print("\n✓ Passes the four-fifths rule for this sample — no group flagged.")


if __name__ == "__main__":
    main()
