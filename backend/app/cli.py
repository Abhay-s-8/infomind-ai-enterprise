"""Command line entry points:  python -m app.cli <command>

  init-db        create tables (development convenience; production uses `alembic upgrade head`)
  create-admin   create an administrator   (--email, --password or INITIAL_ADMIN_PASSWORD, [--if-missing])
  reindex        rebuild the vector index from stored chunk text   (--if-needed to skip when complete)
  seed-demo      insert the SYNTHETIC demo corpus for a user and process it
  train          train + activate the classifier (synthetic data, or --csv path; --if-missing to skip if trained)
  export-data    write sample training CSV and demo documents under data/
  evaluate       run the evaluation suite and export JSON/CSV   (--skip-rag to skip the LLM part)
"""
import argparse
import os
import sys
from pathlib import Path

from sqlalchemy import select

from app.core.config import PROJECT_DIR, get_settings
from app.core.security import hash_password
from app.db.session import Base, SessionLocal, engine
from app.models import Role, User


def _user(db, email: str) -> User:
    user = db.scalar(select(User).where(User.email == email.lower()))
    if user is None:
        sys.exit(f"No such user: {email}. Create one with `create-admin` or register in the UI.")
    return user


def cmd_init_db(_):
    Base.metadata.create_all(engine)
    print("Tables created.")


def cmd_create_admin(a):
    """The password may come from INITIAL_ADMIN_PASSWORD so it never appears in a process list or shell history."""
    password = a.password or os.environ.get("INITIAL_ADMIN_PASSWORD", "")
    if len(password) < 10:
        sys.exit("Administrator password must be at least 10 characters (--password or INITIAL_ADMIN_PASSWORD).")
    with SessionLocal() as db:
        existing = db.scalar(select(User).where(User.email == a.email.lower()))
        if existing:
            if a.reset_password:  # explicit, operator-only (needs shell or environment access to the service)
                if existing.role != Role.admin.value:
                    sys.exit(f"{a.email} is not an administrator; refusing to reset its password.")
                existing.password_hash = hash_password(password)
                db.commit()
                print(f"Administrator {a.email} password reset.")
                return
            if a.if_missing:
                print(f"Administrator {a.email} already exists; nothing to do.")
                return
            sys.exit("User already exists.")
        db.add(User(email=a.email.lower(), full_name="Administrator", password_hash=hash_password(password),
                    role=Role.admin.value))
        db.commit()
    print(f"Administrator {a.email} created.")


def cmd_train(a):
    import pandas as pd

    from app.services import classification_service

    df = pd.read_csv(a.csv) if a.csv else None
    with SessionLocal() as db:
        existing = classification_service.active_model_version(db)
        if a.if_missing and existing is not None and Path(existing.artifact_path).exists():
            print(f"Active model {existing.version} already present; nothing to do.")
            return
        mv = classification_service.train_model(db, df, None, a.csv or "synthetic")
        m = mv.metrics
        print(f"Trained {mv.version} ({mv.algorithm})")
        print(f"  held-out test n={m['n_evaluated']} accuracy={m['accuracy']:.3f} macro-F1={m['macro_f1']:.3f}")
        print(f"  note: {mv.dataset_info['caveat']}")


def cmd_reindex(a):
    from app.core.errors import ServiceUnavailable
    from app.services import document_service

    try:
        with SessionLocal() as db:
            n = document_service.rebuild_vectors(db, force=not a.if_needed)
    except ServiceUnavailable as exc:
        sys.exit(f"Reindex failed: {exc.message}")
    print(f"Vector index rebuilt from stored text: {n} chunks." if n else "Vector index already complete; nothing to do.")


def cmd_seed_demo(a):
    from app.ml import demo_corpus
    from app.services import document_service

    with SessionLocal() as db:
        user = _user(db, a.email)
        added = 0
        for name, text in demo_corpus.DOCS.items():
            _, dup = document_service.ingest_upload(db, user.id, name, "text/plain", text.encode(), is_demo=True)
            added += 0 if dup else 1
        n = document_service.run_pending_jobs(db, limit=500)
    print(f"Seeded {added} new demo documents (marked is_demo); processed {n} jobs for {a.email}.")


def cmd_export_data(_):
    from app.ml import demo_corpus, synthetic

    sample = PROJECT_DIR / "data" / "sample"
    sample.mkdir(parents=True, exist_ok=True)
    synthetic.generate().to_csv(sample / "training_data.csv", index=False)
    docs = sample / "documents"
    docs.mkdir(exist_ok=True)
    for name, text in demo_corpus.DOCS.items():
        (docs / name).write_text(text + "\n", encoding="utf-8")
    print(f"Wrote {sample / 'training_data.csv'} and {len(demo_corpus.DOCS)} demo documents.")


def cmd_evaluate(a):
    from app import evaluation
    from app.core.errors import ServiceUnavailable

    out_dir = PROJECT_DIR / "data" / "evaluation"
    with SessionLocal() as db:
        user = _user(db, a.email)
        results = {"classification": evaluation.evaluate_classification(db)}
        evaluation.persist(db, "classification", {"dataset": "synthetic"}, results["classification"])
        results["retrieval"] = evaluation.evaluate_retrieval(db, user)
        evaluation.persist(db, "retrieval", {"k": results["retrieval"]["k"]}, results["retrieval"])
        if not a.skip_rag:
            try:
                results["rag"] = evaluation.evaluate_rag(db, user)
                evaluation.persist(db, "rag", {}, {k: v for k, v in results["rag"].items() if k != "rows"})
            except ServiceUnavailable as exc:
                print(f"RAG evaluation skipped: {exc.message}")
    for p in evaluation.export(results, out_dir):
        print("wrote", p)
    for mode, m in results["retrieval"]["metrics"].items():
        print(f"  retrieval[{mode}]", {k: round(v, 3) for k, v in m.items()})


def main():
    p = argparse.ArgumentParser(prog="app.cli")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init-db").set_defaults(fn=cmd_init_db)
    s = sub.add_parser("create-admin")
    s.add_argument("--email", required=True)
    s.add_argument("--password", help="omit to read INITIAL_ADMIN_PASSWORD from the environment")
    s.add_argument("--if-missing", action="store_true", help="succeed quietly if the user already exists")
    s.add_argument("--reset-password", action="store_true", help="set the password of an existing administrator")
    s.set_defaults(fn=cmd_create_admin)
    s = sub.add_parser("train")
    s.add_argument("--csv")
    s.add_argument("--if-missing", action="store_true", help="skip when an active model with an artifact exists")
    s.set_defaults(fn=cmd_train)
    s = sub.add_parser("reindex")
    s.add_argument("--if-needed", action="store_true", help="only rebuild when the index is missing chunks")
    s.set_defaults(fn=cmd_reindex)
    s = sub.add_parser("seed-demo")
    s.add_argument("--email", default=get_settings().dev_admin_email or "admin@example.com")
    s.set_defaults(fn=cmd_seed_demo)
    sub.add_parser("export-data").set_defaults(fn=cmd_export_data)
    s = sub.add_parser("evaluate")
    s.add_argument("--email", default=get_settings().dev_admin_email or "admin@example.com")
    s.add_argument("--skip-rag", action="store_true")
    s.set_defaults(fn=cmd_evaluate)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
