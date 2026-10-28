import pytest

from app import evaluation
from app.ml import demo_corpus
from app.services import document_service
from app.tests.conftest import make_user


def test_retrieval_metric_math():
    m = evaluation.retrieval_metrics(["b", "a", "c"], {"a"}, k=3)
    assert m["recall"] == 1.0 and m["rr"] == 0.5 and m["precision"] == pytest.approx(1 / 3)
    assert m["ndcg"] == pytest.approx(1 / 1.5849625, rel=1e-4)  # 1/log2(3)
    miss = evaluation.retrieval_metrics(["x", "y"], {"a"}, k=2)
    assert miss == {"recall": 0.0, "precision": 0.0, "rr": 0.0, "ndcg": 0.0}


def test_retrieval_metrics_collapse_duplicate_documents():
    m = evaluation.retrieval_metrics(["a", "a", "a", "b"], {"b"}, k=2)
    assert m["recall"] == 1.0 and m["rr"] == 0.5


def test_retrieval_evaluation_end_to_end(db):
    user = make_user(db, "eval@example.com")
    for name, text in demo_corpus.DOCS.items():
        document_service.ingest_upload(db, user.id, name, "text/plain", text.encode(), is_demo=True)
    document_service.run_pending_jobs(db, limit=100)
    res = evaluation.evaluate_retrieval(db, user)
    assert res["n_queries"] == len(demo_corpus.RETRIEVAL_QUERIES)
    assert set(res["metrics"]) == {"keyword", "semantic", "hybrid"}
    assert res["metrics"]["keyword"]["mrr"] > 0.5  # sanity floor on the easy synthetic corpus
    assert "author-assigned" in res["relevance_labels"]


def test_export_writes_json_and_csv(tmp_path):
    results = {"retrieval": {"metrics": {"keyword": {"mrr": 0.9}}}}
    paths = evaluation.export(results, tmp_path)
    assert {p.name for p in paths} == {"evaluation_results.json", "retrieval_metrics.csv"}
