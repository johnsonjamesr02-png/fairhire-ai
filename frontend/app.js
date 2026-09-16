const API_BASE = "http://localhost:8000";
document.getElementById("api-base-label").textContent = API_BASE;

const SELECTION_CUTOFF = 60;
let jobRequirements = null;
const scoredCandidates = [];

document.getElementById("parse-jd-btn").addEventListener("click", async () => {
  const jd_text = document.getElementById("jd-text").value;
  const res = await fetch(`${API_BASE}/parse-job-description`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ jd_text }),
  });
  jobRequirements = await res.json();
  document.getElementById("jd-output").textContent = JSON.stringify(jobRequirements, null, 2);
});

document.getElementById("score-btn").addEventListener("click", async () => {
  if (!jobRequirements) {
    alert("Parse a job description first.");
    return;
  }
  const resume_text = document.getElementById("resume-text").value;

  const profileRes = await fetch(`${API_BASE}/parse-resume`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ resume_text }),
  });
  const profile = await profileRes.json();

  const scoreRes = await fetch(`${API_BASE}/score-candidate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ candidate_profile: profile, job_requirements: jobRequirements }),
  });
  const score = await scoreRes.json();
  document.getElementById("score-output").textContent = JSON.stringify(score, null, 2);

  // Demo-only: prompt for a synthetic group label for audit purposes.
  // In a real system this comes from separately-collected EEO self-ID data,
  // never from the resume itself.
  const group = prompt("Synthetic demographic group for audit purposes (e.g. 'Group A'):", "Group A");
  const selected = score.fit_score >= SELECTION_CUTOFF;

  scoredCandidates.push({ name: profile.candidate_name, fit_score: score.fit_score, group, selected });
  renderResultsTable();
});

function renderResultsTable() {
  const tbody = document.querySelector("#results-table tbody");
  tbody.innerHTML = "";
  scoredCandidates.forEach((c) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${c.name}</td><td>${c.fit_score}</td><td>${c.group}</td><td>${c.selected ? "Yes" : "No"}</td>`;
    tbody.appendChild(tr);
  });
}

document.getElementById("audit-btn").addEventListener("click", async () => {
  const candidates = scoredCandidates.map((c) => ({ demographic_group: c.group, selected: c.selected }));
  const res = await fetch(`${API_BASE}/bias-audit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ candidates }),
  });
  const report = await res.json();
  document.getElementById("audit-output").textContent = JSON.stringify(report, null, 2);
});
