"""Local, free retrieval calibration against labeled synthetic questions (no LLM)."""

import json
from pathlib import Path

import numpy as np

from app.core.config import settings
from app.services.embeddings import provider
from app.services.knowledge import chunk_markdown


def evaluate():
    root = Path(__file__).resolve().parents[1] / "knowledge"
    chunks, filenames = [], []
    for path in sorted((root / "demo").glob("*.md")):
        raw = path.read_text()
        if "scope: team:Analytics" in raw:
            continue
        body = raw.split("---", 2)[2]
        for chunk in chunk_markdown(body):
            chunks.append(chunk)
            filenames.append(path.name)
    vectors = np.asarray(provider.encode(chunks, "passage"))
    cases = json.loads((root / "evaluation.json").read_text())
    questions = np.asarray(provider.encode([case["question"] for case in cases], "query"))
    scores = questions @ vectors.T
    positive, negative = [], []
    report = []
    for case, row in zip(cases, scores, strict=True):
        order = np.argsort(-row)
        hit = not case["documents"] or any(filenames[i] in case["documents"] for i in order[:5])
        score = float(row[order[0]])
        (positive if case["documents"] else negative).append(score)
        report.append(
            {
                "question": case["question"],
                "score": round(score, 5),
                "top_document": filenames[order[0]],
                "expected_retrieved": hit,
            }
        )
    lower, upper = max(negative), min(positive)
    threshold = round((lower + upper) / 2, 6) if lower < upper else None
    result = {
        "model": settings.embedding_model,
        "cases": report,
        "max_negative": lower,
        "min_positive": upper,
        "recommended_threshold": threshold,
        "note": "Small synthetic calibration set; not a production guarantee.",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if threshold is None or not all(row["expected_retrieved"] for row in report):
        raise SystemExit(
            "Калибровка не разделила вопросы. Дополните документы/выборку; порог не назначен."
        )
    print(f"RAG_MIN_SCORE={threshold}")


if __name__ == "__main__":
    evaluate()
