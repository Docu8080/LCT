"""Reproducible simulation and a frozen synthetic matching benchmark."""

import hashlib
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
DATASET = ROOT / "docs/validation_dataset.json"
RESULTS = ROOT / "docs/validation_results.json"


def dcg(values):
    return sum((2**value - 1) / math.log2(i + 2) for i, value in enumerate(values[:5]))


def validate():
    rng = random.Random(20261010)
    assessment = []
    for spec in ["backend", "frontend"]:
        for grade in GRADES:
            rows = []
            for seed in range(120):
                theta = rng.uniform(-2.5, 2.5)
                questions = generate(spec, grade, seed)
                answers = {
                    item["id"]: item["answer"]
                    if rng.random()
                    < probability(theta, item["difficulty"], 0.25 if item.get("options") else 0.02)
                    else "__wrong__"
                    for item in questions
                }
                result = evaluate(questions, answers, grade)
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
                        math.sqrt(
                            statistics.mean((row["theta"] - row["estimate"]) ** 2 for row in rows)
                        ),
                        3,
                    ),
                    "classification_accuracy": round(
                        statistics.mean(row["correct_class"] for row in rows), 3
                    ),
                    "mean_decision_confidence": round(
                        statistics.mean(row["confidence"] for row in rows), 1
                    ),
                }
            )

    dataset_text = DATASET.read_text(encoding="utf-8")
    dataset = json.loads(dataset_text)
    profiles = dataset["profiles"]
    queries = []
    for query in dataset["queries"]:
        need = query["need"]
        labels = query["labels"]
        ranked = []
        for profile in profiles:
            match = rank_candidate(
                profile["profile"], need, profile["categories"], profile["achievements"]
            )
            if match is not None:
                ranked.append((match["score"], profile))
        ranked.sort(key=lambda item: (-item[0], item[1]["id"]))
        pool = [profile for _, profile in ranked]
        assert len(pool) >= 5, "The benchmark needs at least five eligible candidates per query"
        ideal = dcg(sorted((labels[str(profile["id"])] for profile in pool), reverse=True))
        assert ideal > 0, "Each query must have a labelled relevant candidate"
        shuffled = sorted(pool, key=lambda profile: profile["id"])
        random.Random(dataset["seed"] + query["query"]).shuffle(shuffled)
        ranked_labels = [labels[str(profile["id"])] for profile in pool]
        random_labels = [labels[str(profile["id"])] for profile in shuffled]
        queries.append(
            {
                "query": query["query"],
                "need": need,
                "eligible_pool_n": len(pool),
                "ndcg_at_5": round(dcg(ranked_labels) / ideal, 4),
                "random_ndcg_at_5": round(dcg(random_labels) / ideal, 4),
                "precision_at_5": sum(label >= 2 for label in ranked_labels[:5]) / 5,
                "random_precision_at_5": sum(label >= 2 for label in random_labels[:5]) / 5,
                "top_ids": [profile["id"] for profile in pool[:5]],
            }
        )

    return {
        "seed": dataset["seed"],
        "dataset_sha256": hashlib.sha256(dataset_text.encode("utf-8")).hexdigest(),
        "dataset_hash_encoding": "UTF-8 with LF line endings",
        "assessment_n": 720,
        "assessment": assessment,
        "matching_profiles_n": len(profiles),
        "matching_queries_n": len(queries),
        "matching": {
            "baseline": "random_order_in_the_same_eligible_pool",
            "mean_ndcg_at_5": round(statistics.mean(query["ndcg_at_5"] for query in queries), 4),
            "random_mean_ndcg_at_5": round(
                statistics.mean(query["random_ndcg_at_5"] for query in queries), 4
            ),
            "mean_precision_at_5": round(
                statistics.mean(query["precision_at_5"] for query in queries), 4
            ),
            "random_mean_precision_at_5": round(
                statistics.mean(query["random_precision_at_5"] for query in queries), 4
            ),
        },
        "limitations": [
            "Responses simulated using the same IRT model used for scoring; optimistic and not independent empirical validation.",
            "Difficulties, grade cuts and weights are expert assumptions; no actual candidate calibration.",
            "Frozen matching relevance labels use a transparent synthetic rubric, not employer judgments or hiring outcomes.",
            "The random baseline uses the same category-eligible pool and the same labels as the ranker; the former all-profile random comparison was not a fair ranking baseline.",
        ],
        "queries": queries,
    }


if __name__ == "__main__":
    result = validate()
    if "--check" in sys.argv:
        assert result == json.loads(RESULTS.read_text(encoding="utf-8")), (
            "Validation results changed; regenerate and review them"
        )
    else:
        RESULTS.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(
        json.dumps(
            {key: value for key, value in result.items() if key != "queries"},
            ensure_ascii=False,
            indent=2,
        )
    )
