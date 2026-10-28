import pandas as pd
import pytest

from app.ml import synthetic, training
from app.tests.conftest import SAMPLE_TEXT, process_jobs


@pytest.fixture(scope="module")
def trained(tmp_path_factory):
    return training.train_and_select(synthetic.generate(40, seed=7), tmp_path_factory.mktemp("m"))


def test_synthetic_data_is_reproducible_and_deduplicated():
    a, b = synthetic.generate(20, seed=1), synthetic.generate(20, seed=1)
    assert a.equals(b)
    assert a["text"].is_unique and set(a["label"]) == set(synthetic.CATEGORIES)


def test_training_compares_both_models_and_reports_required_metrics(trained):
    assert set(trained["comparison"]) == {"logistic_regression", "linear_svm"}
    m = trained["metrics"]
    for key in ("accuracy", "macro_precision", "macro_recall", "macro_f1", "weighted_f1", "n_evaluated",
                "per_class", "confusion_matrix"):
        assert key in m
    assert sum(sum(r) for r in m["confusion_matrix"]["matrix"]) == m["n_evaluated"]
    info = trained["dataset_info"]
    assert info["train"] + info["validation"] + info["test"] == info["total"]
    assert info["selection_split"] == "validation" and "held out" in info["evaluation_split"]
    assert info["caveat"]  # small/synthetic data must carry a limitations note


def test_training_is_deterministic(tmp_path):
    df = synthetic.generate(30, seed=3)
    r1, r2 = training.train_and_select(df, tmp_path / "a"), training.train_and_select(df, tmp_path / "b")
    assert r1["metrics"]["macro_f1"] == r2["metrics"]["macro_f1"]
    assert r1["algorithm"] == r2["algorithm"]


def test_score_type_is_honest(tmp_path):
    """SVM outputs are decision values (not probabilities); LR outputs are labelled uncalibrated."""
    import joblib
    df = synthetic.generate(30)
    for kind, stype in (("logistic_regression", "probability_uncalibrated"), ("linear_svm", "decision_score")):
        pipe = training._pipeline(kind).fit(df["text"], df["label"])
        path = tmp_path / f"{kind}.joblib"
        joblib.dump({"pipeline": pipe, "categories": sorted(df["label"].unique()), "version": kind,
                     "algorithm": kind, "score_type": stype}, path)
        pred = training.LoadedModel(str(path)).predict("The purchasing department issues the purchase order.")
        assert pred["score_type"] == stype
        if kind == "logistic_regression":
            assert abs(sum(pred["all_scores"].values()) - 1.0) < 1e-6
        else:
            assert abs(sum(pred["all_scores"].values()) - 1.0) > 1e-3  # not a probability distribution


def test_prediction_shape_and_low_confidence_flag(trained):
    model = training.LoadedModel(trained["artifact_path"])
    p = model.predict("The purchasing department issues the purchase order and invoice payment terms.")
    assert p["category"] == "Finance and Procurement" and p["model_version"] == trained["version"]
    gibberish = model.predict("zxqv wlorp ktmn", low_confidence=0.99)
    assert gibberish["low_confidence"] is True


def test_dataset_validation_rejects_bad_data():
    with pytest.raises(training.DatasetError):
        training.validate_dataset(pd.DataFrame({"text": ["a"], "label": ["x"]}))
    with pytest.raises(training.DatasetError):
        training.validate_dataset(pd.DataFrame({"foo": [1]}))
    tiny = pd.DataFrame({"text": [f"t{i}" for i in range(10)], "label": ["a"] * 5 + ["b"] * 5})
    with pytest.raises(training.DatasetError, match="fewer than"):
        training.validate_dataset(tiny)


def _train(client, admin):
    r = client.post("/api/v1/classification/train", headers=admin, json={"dataset": "synthetic"})
    assert r.status_code == 202  # background task completes within the TestClient request
    return client.get("/api/v1/classification/models", headers=admin).json()


def test_train_endpoint_admin_only_and_audited(client, admin, analyst):
    assert client.post("/api/v1/classification/train", headers=analyst, json={}).status_code == 403
    models = _train(client, admin)
    assert len(models) == 1 and models[0]["is_active"]
    logs = client.get("/api/v1/audit?action=model.train", headers=admin).json()
    assert logs and logs[0]["outcome"] == "success"
    m = client.get("/api/v1/classification/metrics", headers=analyst).json()
    assert m["metrics"]["n_evaluated"] > 0 and "comparison" in m


def test_metrics_404_before_training(client, analyst):
    assert client.get("/api/v1/classification/metrics", headers=analyst).status_code == 404
    assert client.post("/api/v1/classification/predict", headers=analyst, json={"text": "x"}).status_code == 409


def test_document_gets_prediction_and_review_never_overwritten(client, admin, analyst, reviewer, upload_and_process):
    _train(client, admin)
    doc_id = upload_and_process(analyst, "inv.txt", SAMPLE_TEXT)
    d = client.get(f"/api/v1/documents/{doc_id}", headers=analyst).json()
    assert d["prediction"]["category"] == "Finance and Procurement"
    assert d["prediction"]["model_version"] and d["verified_category"] is None

    r = client.post(f"/api/v1/reviews/{doc_id}", headers=reviewer,
                    json={"decision": "correct", "category": "Administration", "note": "it is an admin memo"})
    assert r.status_code == 201
    d = client.get(f"/api/v1/documents/{doc_id}", headers=analyst).json()
    assert d["verified_category"] == "Administration" and d["category"] == "Administration"
    assert d["prediction"]["category"] == "Finance and Procurement"  # machine prediction retained separately

    assert client.post(f"/api/v1/documents/{doc_id}/reclassify", headers=analyst).status_code == 200
    d = client.get(f"/api/v1/documents/{doc_id}", headers=analyst).json()
    assert d["verified_category"] == "Administration"  # human label survives reclassification
    assert d["prediction"]["review_status"] == "reviewed"
    hist = client.get("/api/v1/reviews/history", headers=reviewer).json()
    assert hist[0]["predicted"] == "Finance and Procurement" and hist[0]["final"] == "Administration"


def test_review_validation(client, admin, analyst, reviewer, upload_and_process):
    _train(client, admin)
    doc_id = upload_and_process(analyst, "inv.txt", SAMPLE_TEXT)
    url = f"/api/v1/reviews/{doc_id}"
    assert client.post(url, headers=reviewer, json={"decision": "correct"}).status_code == 400
    assert client.post(url, headers=reviewer, json={"decision": "correct", "category": "Nonsense"}).status_code == 400
    assert client.post(url, headers=analyst, json={"decision": "confirm"}).status_code == 403
    assert client.post("/api/v1/reviews/nope", headers=reviewer, json={"decision": "confirm"}).status_code == 404
    assert client.post(url, headers=reviewer, json={"decision": "confirm"}).status_code == 201


def test_low_confidence_prediction_enters_review_queue(client, admin, analyst, reviewer, upload_and_process, monkeypatch):
    from app.core.config import get_settings
    monkeypatch.setattr(get_settings(), "low_confidence_threshold", 0.999)
    _train(client, admin)
    models = client.get("/api/v1/classification/models", headers=admin).json()
    doc_id = upload_and_process(analyst, "vague.txt", "Thanks for your note. See you soon, kind regards.")
    q = client.get("/api/v1/reviews", headers=reviewer).json()
    if models[0]["score_type"] == "probability_uncalibrated":
        assert q["total"] == 1 and q["items"][0]["document_id"] == doc_id
        client.post(f"/api/v1/reviews/{doc_id}", headers=reviewer, json={"decision": "confirm"})
        assert client.get("/api/v1/reviews", headers=reviewer).json()["total"] == 0
    process_jobs()
