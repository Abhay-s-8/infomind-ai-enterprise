"""Reproducible training/evaluation for TF-IDF + {Logistic Regression, Linear SVM}.

Selection criterion: highest macro-F1 on the VALIDATION split. Reported metrics come from the untouched TEST split.
"""
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, precision_recall_fscore_support
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC

SEED = 42
MIN_PER_CLASS = 6


class DatasetError(ValueError):
    pass


def validate_dataset(df: pd.DataFrame) -> pd.DataFrame:
    if not {"text", "label"}.issubset(df.columns):
        raise DatasetError("Dataset needs 'text' and 'label' columns.")
    df = df[["text", "label"]].dropna().copy()
    df["text"] = df["text"].astype(str).str.strip()
    df = df[df["text"].str.len() > 0].drop_duplicates(subset="text")
    counts = df["label"].value_counts()
    if len(counts) < 2:
        raise DatasetError("At least two classes are required.")
    small = counts[counts < MIN_PER_CLASS]
    if len(small):
        raise DatasetError(f"Classes with fewer than {MIN_PER_CLASS} examples: {small.to_dict()}")
    return df.reset_index(drop=True)


def _pipeline(kind: str) -> Pipeline:
    tfidf = TfidfVectorizer(lowercase=True, strip_accents="unicode", ngram_range=(1, 2), sublinear_tf=True,
                            stop_words="english", min_df=1)
    clf = (LogisticRegression(max_iter=1000, C=5.0, random_state=SEED) if kind == "logistic_regression"
           else LinearSVC(C=1.0, random_state=SEED))
    return Pipeline([("tfidf", tfidf), ("clf", clf)])


def evaluate(pipe: Pipeline, texts, labels, categories: list[str]) -> dict:
    pred = pipe.predict(texts)
    p, r, f, s = precision_recall_fscore_support(labels, pred, labels=categories, zero_division=0)
    mp, mr, mf, _ = precision_recall_fscore_support(labels, pred, labels=categories, average="macro", zero_division=0)
    _, _, wf, _ = precision_recall_fscore_support(labels, pred, labels=categories, average="weighted", zero_division=0)
    return {
        "n_evaluated": int(len(labels)),
        "accuracy": float(accuracy_score(labels, pred)),
        "macro_precision": float(mp), "macro_recall": float(mr), "macro_f1": float(mf), "weighted_f1": float(wf),
        "per_class": {c: {"precision": float(p[i]), "recall": float(r[i]), "f1": float(f[i]), "support": int(s[i])}
                      for i, c in enumerate(categories)},
        "confusion_matrix": {"labels": categories,
                             "matrix": confusion_matrix(labels, pred, labels=categories).tolist()},
    }


def train_and_select(df: pd.DataFrame, out_dir: Path, seed: int = SEED, dataset_name: str = "synthetic") -> dict:
    df = validate_dataset(df)
    categories = sorted(df["label"].unique())
    counts = df["label"].value_counts()
    # 60/20/20 stratified split; fall back to 70/30 (no validation split) when classes are tiny
    three_way = counts.min() >= 10
    if three_way:
        tr, rest = train_test_split(df, test_size=0.4, stratify=df["label"], random_state=seed)
        val, te = train_test_split(rest, test_size=0.5, stratify=rest["label"], random_state=seed)
    else:
        tr, te = train_test_split(df, test_size=0.3, stratify=df["label"], random_state=seed)
        val = None
    leakage = len(set(tr["text"]) & set(te["text"])) + (len(set(tr["text"]) & set(val["text"])) if val is not None else 0)
    if leakage:
        raise DatasetError(f"{leakage} identical texts appear in more than one split.")

    comparison, fitted = {}, {}
    for kind in ("logistic_regression", "linear_svm"):
        pipe = _pipeline(kind).fit(tr["text"], tr["label"])
        fitted[kind] = pipe
        entry = {"test": evaluate(pipe, te["text"], te["label"], categories)}
        if val is not None:
            entry["validation"] = evaluate(pipe, val["text"], val["label"], categories)
        comparison[kind] = entry
    sel_split = "validation" if val is not None else "test"
    best = max(comparison, key=lambda k: (comparison[k][sel_split]["macro_f1"], k == "logistic_regression"))

    stamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    digest = hashlib.sha256(json.dumps([df["text"].tolist(), df["label"].tolist()]).encode()).hexdigest()[:8]
    version = f"{best}-{stamp}-{digest}"
    out_dir.mkdir(parents=True, exist_ok=True)
    artifact = out_dir / f"{version}.joblib"
    score_type = "probability_uncalibrated" if best == "logistic_regression" else "decision_score"
    joblib.dump({"pipeline": fitted[best], "categories": categories, "version": version, "algorithm": best,
                 "score_type": score_type}, artifact)
    return {
        "version": version, "algorithm": best, "artifact_path": str(artifact), "categories": categories,
        "score_type": score_type, "metrics": comparison[best]["test"], "comparison": comparison,
        "dataset_info": {
            "name": dataset_name, "total": int(len(df)), "class_counts": {k: int(v) for k, v in counts.items()},
            "train": int(len(tr)), "validation": int(len(val)) if val is not None else 0, "test": int(len(te)),
            "seed": seed, "evaluation_split": "test (held out)", "selection_split": sel_split,
            "selection_criterion": f"macro-F1 on {sel_split} split",
            "trained_at": datetime.now(UTC).isoformat(),
            "caveat": "Small and/or synthetic data: metrics demonstrate the pipeline and are not evidence of "
                      "real-world accuracy." if len(df) < 2000 else "",
        },
    }


class LoadedModel:
    def __init__(self, path: str):
        bundle = joblib.load(path)  # trusted artifacts only: files written by train_and_select in MODEL_DIR
        self.pipeline: Pipeline = bundle["pipeline"]
        self.categories: list[str] = bundle["categories"]
        self.version: str = bundle["version"]
        self.algorithm: str = bundle["algorithm"]
        self.score_type: str = bundle["score_type"]

    def predict(self, text: str, low_confidence: float = 0.55, svm_margin: float = 0.3) -> dict:
        if self.score_type == "probability_uncalibrated":
            probs = self.pipeline.predict_proba([text])[0]
            scores = dict(zip(self.pipeline.classes_, map(float, probs), strict=True))
            ranked = sorted(scores.values(), reverse=True)
            low = ranked[0] < low_confidence
        else:
            dec = np.atleast_1d(self.pipeline.decision_function([text])[0])
            scores = dict(zip(self.pipeline.classes_, map(float, dec), strict=True))
            ranked = sorted(scores.values(), reverse=True)
            low = (ranked[0] - ranked[1]) < svm_margin  # margin heuristic, not a probability
        category = max(scores, key=scores.get)
        return {"category": category, "score": scores[category], "score_type": self.score_type,
                "all_scores": scores, "low_confidence": bool(low), "model_version": self.version}
