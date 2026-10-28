"""Offline evaluation framework: classification, retrieval (keyword vs semantic vs hybrid) and RAG.

Results are persisted to EvaluationRun and exported as JSON/CSV. Retrieval and RAG metrics are computed on the
small synthetic demo corpus, so they demonstrate the methodology and are NOT evidence of real-world quality.
"""
import csv
import json
import math
import time
from pathlib import Path

from sqlalchemy.orm import Session

from app.ml import demo_corpus, synthetic, training
from app.models import EvaluationRun, User
from app.services import rag_service, retrieval_service
from app.services.embedding_service import get_embedder, get_llm
from app.services.vector_store import get_vector_store


def retrieval_metrics(ranked_docs: list[str], relevant: set[str], k: int) -> dict:
    """Metrics over a ranked list of DOCUMENT names (chunk hits collapsed to first occurrence)."""
    seen, dedup = set(), []
    for d in ranked_docs:
        if d not in seen:
            seen.add(d)
            dedup.append(d)
    top = dedup[:k]
    hits = [d for d in top if d in relevant]
    rr = next((1.0 / (i + 1) for i, d in enumerate(dedup) if d in relevant), 0.0)
    dcg = sum(1.0 / math.log2(i + 2) for i, d in enumerate(top) if d in relevant)
    ideal = sum(1.0 / math.log2(i + 2) for i in range(min(len(relevant), k)))
    return {"recall": len(hits) / len(relevant), "precision": len(hits) / k, "rr": rr,
            "ndcg": dcg / ideal if ideal else 0.0}


def evaluate_retrieval(db: Session, user: User, k: int = 3) -> dict:
    """Requires the demo corpus to be indexed for `user` (see `cli seed-demo`)."""
    per_mode: dict[str, list[dict]] = {"keyword": [], "semantic": [], "hybrid": []}
    for query, relevant in demo_corpus.RETRIEVAL_QUERIES:
        for mode in per_mode:
            hits, _ = retrieval_service.search(db, user, query, mode, page=1, page_size=50)
            per_mode[mode].append(retrieval_metrics([h.filename for h in hits], relevant, k))
    summary = {}
    for mode, rows in per_mode.items():
        n = len(rows)
        summary[mode] = {f"recall@{k}": sum(r["recall"] for r in rows) / n,
                         f"precision@{k}": sum(r["precision"] for r in rows) / n,
                         "mrr": sum(r["rr"] for r in rows) / n, f"ndcg@{k}": sum(r["ndcg"] for r in rows) / n}
    return {"k": k, "n_queries": len(demo_corpus.RETRIEVAL_QUERIES), "metrics": summary,
            "embedding_model": get_embedder().name, "corpus": "synthetic demo corpus (14 documents)",
            "relevance_labels": "author-assigned: each query targets a fact present in exactly one document"}


def evaluate_rag(db: Session, user: User) -> dict:
    """Needs a live LLM. Automatic checks only: citation validity, expected-evidence presence, insufficiency
    behaviour and latency. Answer faithfulness still requires MANUAL review of the exported rows."""
    rows = []
    for question, answerable, expected in demo_corpus.RAG_QUESTIONS:
        start = time.monotonic()
        res = rag_service.answer_question(db, user, question)
        latency = int((time.monotonic() - start) * 1000)
        valid_cites = all(c["chunk_id"] and c["document_id"] for c in res.citations)
        evidence_ok = (expected is None) or any(expected.lower() in c["excerpt"].lower() for c in res.citations)
        rows.append({"question": question, "answerable": answerable, "sufficient_evidence": res.sufficient_evidence,
                     "n_citations": len(res.citations), "citations_valid": valid_cites,
                     "expected_evidence_cited": evidence_ok, "answer": res.answer, "latency_ms": latency,
                     "manual_faithfulness_review": "PENDING"})
    ans = [r for r in rows if r["answerable"]]
    unans = [r for r in rows if not r["answerable"]]
    return {
        "n_questions": len(rows),
        "answerable_answered_rate": sum(r["sufficient_evidence"] for r in ans) / len(ans),
        "expected_evidence_cited_rate": sum(r["expected_evidence_cited"] for r in ans) / len(ans),
        "unanswerable_refusal_rate": sum(not r["sufficient_evidence"] for r in unans) / len(unans),
        "citation_validity_rate": sum(r["citations_valid"] for r in rows) / len(rows),
        "mean_latency_ms": sum(r["latency_ms"] for r in rows) / len(rows),
        "llm": get_llm().name, "rows": rows,
        "caveat": "Unsupported-claim rate requires manual review of `rows`; it is not computed automatically.",
    }


def evaluate_classification(db: Session) -> dict:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        res = training.train_and_select(synthetic.generate(), Path(tmp))
    return {"comparison": res["comparison"], "selected": res["algorithm"], "dataset_info": res["dataset_info"]}


def persist(db: Session, kind: str, config: dict, results: dict, synthetic_data: bool = True) -> EvaluationRun:
    run = EvaluationRun(kind=kind, config=config, results=results, is_synthetic=synthetic_data)
    db.add(run)
    db.commit()
    return run


def export(results: dict, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "evaluation_results.json"
    json_path.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    paths = [json_path]
    if "retrieval" in results:
        p = out_dir / "retrieval_metrics.csv"
        with p.open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["mode", "metric", "value"])
            for mode, m in results["retrieval"]["metrics"].items():
                for name, val in m.items():
                    w.writerow([mode, name, round(val, 4)])
        paths.append(p)
    if "classification" in results:
        p = out_dir / "classification_metrics.csv"
        with p.open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["model", "split", "accuracy", "macro_f1", "weighted_f1", "n"])
            for model, parts in results["classification"]["comparison"].items():
                for split, m in parts.items():
                    w.writerow([model, split, round(m["accuracy"], 4), round(m["macro_f1"], 4),
                                round(m["weighted_f1"], 4), m["n_evaluated"]])
        paths.append(p)
    return paths


def vector_count() -> int | None:
    return get_vector_store().count()
