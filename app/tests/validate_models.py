"""Reproducible simulation. No empirical claim about real candidates or hires."""

import json
import math
import random
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from assessment import CUTS, GRADES, evaluate, generate, probability
from matching import rank_candidate

ROOT = Path(__file__).resolve().parents[1]
rng = random.Random(20261010)
assessment = []
for spec in ["backend", "frontend"]:
    for grade in GRADES:
        rows = []
        for i in range(120):
            theta = rng.uniform(-2.5, 2.5)
            q = generate(spec, grade, i)
            answers = {
                x["id"]: x["answer"]
                if rng.random()
                < probability(theta, x["difficulty"], 0.25 if x.get("options") else 0.02)
                else "__wrong__"
                for x in q
            }
            result = evaluate(q, answers, grade)
            rows.append(
                {
                    "theta": theta,
                    "estimate": result["theta"],
                    "correct_class": result["passed"] == (theta >= CUTS[grade]),
                    "confidence": result["confidence"],
                }
            )
        assessment.append(
            {
                "specialization": spec,
                "grade": grade,
                "n": len(rows),
                "theta_rmse": round(
                    math.sqrt(statistics.mean((r["theta"] - r["estimate"]) ** 2 for r in rows)), 3
                ),
                "classification_accuracy": round(
                    statistics.mean(r["correct_class"] for r in rows), 3
                ),
                "mean_decision_confidence": round(
                    statistics.mean(r["confidence"] for r in rows), 1
                ),
            }
        )
profiles = []
for i in range(150):
    spec = rng.choice(["backend", "frontend"])
    pool = (
        ["Python", "FastAPI", "SQL", "PostgreSQL", "Docker", "Django"]
        if spec == "backend"
        else ["React", "Vue", "TypeScript", "JavaScript", "CSS", "HTML"]
    )
    skills = rng.sample(pool, rng.randrange(1, 6))
    grade = rng.choice(GRADES)
    profiles.append(
        {
            "id": i,
            "profile": {
                "skills": skills,
                "salary": rng.randrange(80, 351) * 1000,
                "work_format": rng.choice(["remote", "hybrid", "office"]),
            },
            "categories": [
                {
                    "specialization": spec,
                    "grade": grade,
                    "score": rng.randrange(60, 101),
                    "verified_skills": skills[:2],
                }
            ],
            "achievements": [{"strength": 0.2}] if rng.random() < 0.3 else [],
        }
    )


def relevance(p, n):
    # Deliberately separate rubric: exact category + required stack coverage only.
    c = p["categories"][0]
    if c["specialization"] != n["specialization"]:
        return 0
    coverage = len(set(n["skills"]) & set(p["profile"]["skills"])) / len(n["skills"])
    distance = abs(GRADES.index(c["grade"]) - GRADES.index(n["grade"]))
    if distance == 0 and coverage >= 2 / 3:
        return 3
    if distance <= 1 and coverage >= 1 / 3:
        return 2
    if distance <= 1:
        return 1
    return 0


def dcg(values):
    return sum((2**v - 1) / math.log2(i + 2) for i, v in enumerate(values[:5]))


queries = []
for i in range(40):
    spec = rng.choice(["backend", "frontend"])
    pool = (
        ["Python", "SQL", "FastAPI", "PostgreSQL"]
        if spec == "backend"
        else ["React", "TypeScript", "CSS", "JavaScript"]
    )
    need = {
        "specialization": spec,
        "grade": rng.choice(GRADES),
        "skills": rng.sample(pool, 3),
        "salary_to": rng.randrange(140, 301) * 1000,
        "work_format": rng.choice(["remote", "hybrid", "office"]),
    }
    ranked = []
    for p in profiles:
        score = rank_candidate(p["profile"], need, p["categories"], p["achievements"])
        if score:
            ranked.append((score["score"], p))
    ranked.sort(key=lambda x: (-x[0], x[1]["id"]))
    labels = [relevance(p, need) for p in profiles]
    ideal = dcg(sorted(labels, reverse=True))
    shuffled = list(profiles)
    rng.shuffle(shuffled)
    queries.append(
        {
            "query": i,
            "need": need,
            "ndcg_at_5": round(dcg([relevance(p, need) for _, p in ranked]) / ideal, 4),
            "random_ndcg_at_5": round(dcg([relevance(p, need) for p in shuffled]) / ideal, 4),
            "precision_at_5": sum(relevance(p, need) >= 2 for _, p in ranked[:5]) / 5,
            "top_ids": [p["id"] for _, p in ranked[:5]],
        }
    )
result = {
    "seed": 20261010,
    "assessment_n": 720,
    "assessment": assessment,
    "matching_profiles_n": 150,
    "matching_queries_n": 40,
    "matching": {
        "mean_ndcg_at_5": round(statistics.mean(q["ndcg_at_5"] for q in queries), 4),
        "random_mean_ndcg_at_5": round(statistics.mean(q["random_ndcg_at_5"] for q in queries), 4),
        "mean_precision_at_5": round(statistics.mean(q["precision_at_5"] for q in queries), 4),
    },
    "limitations": [
        "Responses simulated using the same IRT model used for scoring; optimistic and not independent empirical validation.",
        "Difficulties, grade cuts and weights are expert assumptions; no actual candidate calibration.",
        "Matching relevance labels use a transparent synthetic rubric, not employer judgments or hiring outcomes.",
    ],
    "queries": queries,
}
(ROOT / "docs/validation_dataset.json").write_text(
    json.dumps(
        {
            "seed": 20261010,
            "profiles": profiles,
            "queries": [
                dict(q, labels={str(p["id"]): relevance(p, q["need"]) for p in profiles})
                for q in queries
            ],
        },
        ensure_ascii=False,
        indent=2,
    )
)
(ROOT / "docs/validation_results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
print(json.dumps({k: v for k, v in result.items() if k != "queries"}, ensure_ascii=False, indent=2))
