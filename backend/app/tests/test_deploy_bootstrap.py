import argparse

import pytest
from sqlalchemy import func, select

from app import cli
from app.core.config import Settings
from app.db.session import SessionLocal, make_engine
from app.models import ModelVersion, Role, User


@pytest.mark.parametrize("given,expected", [
    ("postgres://u:p@host:5432/db", "postgresql+psycopg://u:p@host:5432/db"),
    ("postgresql://u:p@host/db", "postgresql+psycopg://u:p@host/db"),
    ("  postgresql://u:p@host/db  ", "postgresql+psycopg://u:p@host/db"),
    ("postgresql+psycopg://u:p@host/db", "postgresql+psycopg://u:p@host/db"),  # already explicit: untouched
    ("sqlite:////var/data/infomind.db", "sqlite:////var/data/infomind.db"),
])
def test_database_url_gets_the_psycopg_driver(given, expected):
    assert Settings(database_url=given).database_url == expected


def test_production_serves_neither_docs_nor_the_raw_schema(monkeypatch):
    from fastapi.testclient import TestClient

    from app import main

    base = dict(jwt_secret="x" * 40, database_url="sqlite://", qdrant_url=":memory:")
    for env, expected in (("production", 404), ("development", 200)):
        monkeypatch.setattr(main, "get_settings", lambda env=env: Settings(environment=env, **base))
        client = TestClient(main.create_app())  # no `with`: lifespan (workers, seeding) is not started
        assert client.get("/openapi.json").status_code == expected, env
        assert client.get("/docs").status_code == expected, env
        assert client.get("/api/v1/health").status_code == 200  # the health check Render uses stays reachable


def test_file_sqlite_uses_wal_and_busy_timeout(tmp_path):
    eng = make_engine(f"sqlite:///{tmp_path / 'app.db'}")
    with eng.connect() as conn:
        assert conn.exec_driver_sql("PRAGMA journal_mode").scalar() == "wal"
        assert conn.exec_driver_sql("PRAGMA busy_timeout").scalar() == 15000
        assert conn.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1


def _admin_args(**kw):
    return argparse.Namespace(**{"email": "Boss@Example.com", "password": None, "if_missing": False, **kw})


def test_create_admin_reads_password_from_env_and_is_idempotent_with_if_missing(monkeypatch, capsys):
    monkeypatch.setenv("INITIAL_ADMIN_PASSWORD", "a-long-enough-password")
    cli.cmd_create_admin(_admin_args(if_missing=True))
    cli.cmd_create_admin(_admin_args(if_missing=True))  # second boot: no error, no duplicate
    assert "already exists" in capsys.readouterr().out
    with SessionLocal() as db:
        users = list(db.scalars(select(User)))
    assert len(users) == 1 and users[0].email == "boss@example.com" and users[0].role == Role.admin.value
    assert users[0].password_hash != "a-long-enough-password"
    with pytest.raises(SystemExit, match="already exists"):  # without --if-missing it still refuses
        cli.cmd_create_admin(_admin_args())


def test_create_admin_rejects_short_or_missing_passwords(monkeypatch):
    monkeypatch.delenv("INITIAL_ADMIN_PASSWORD", raising=False)
    with pytest.raises(SystemExit, match="at least 10"):
        cli.cmd_create_admin(_admin_args())
    with pytest.raises(SystemExit, match="at least 10"):
        cli.cmd_create_admin(_admin_args(password="short"))
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(User)) == 0


FLEET = "The fleet maintenance budget for the motor pool is 250000 dollars per year. Vehicles are serviced quarterly."


def _wipe_vectors():
    from app.services.vector_store import _client, get_vector_store

    _client().delete_collection(get_vector_store().collection)  # what a restart of temporary storage does


def test_rebuild_vectors_restores_search_after_the_vector_store_was_lost(client, analyst, upload_and_process):
    from app.services import document_service
    from app.services.vector_store import get_vector_store

    upload_and_process(analyst, "fleet.txt", FLEET)
    chunks = get_vector_store().count()
    assert chunks > 0
    with SessionLocal() as db:
        assert document_service.rebuild_vectors(db) == 0  # index complete: nothing to do
    _wipe_vectors()
    assert get_vector_store().count() == 0
    with SessionLocal() as db:
        assert document_service.rebuild_vectors(db) == chunks  # rebuilt from the chunk text kept in SQL
        assert document_service.rebuild_vectors(db) == 0  # and now complete again
        assert document_service.rebuild_vectors(db, force=True) == chunks
    hits = client.post("/api/v1/search/semantic", headers=analyst, json={"query": "fleet maintenance budget"}).json()
    assert hits["results"] and hits["results"][0]["filename"] == "fleet.txt"
    assert get_vector_store().count() == chunks  # forced rebuild replaced, not duplicated


def test_missing_original_file_is_reported_cleanly_without_touching_the_document(client, analyst, upload_and_process):
    from app.core.config import get_settings
    from app.models import Document
    from app.services import document_service

    doc_id = upload_and_process(analyst, "fleet.txt", FLEET)
    with SessionLocal() as db:
        document_service.storage_path(db.get(Document, doc_id).storage_id).unlink()  # temporary storage was reset
    r = client.post(f"/api/v1/documents/{doc_id}/reprocess", headers=analyst)
    assert r.status_code == 409 and r.json()["error"]["code"] == "file_missing"
    assert str(get_settings().storage_dir) not in r.text
    detail = client.get(f"/api/v1/documents/{doc_id}", headers=analyst).json()
    assert detail["status"] == "completed" and detail["chunk_count"] > 0  # still searchable
    assert client.get(f"/api/v1/documents/{doc_id}/download", headers=analyst).status_code == 404
    with SessionLocal() as db:  # even if processing is reached some other way, no server path is exposed
        ok, _ = document_service.process_document(db, doc_id)
        err = db.get(Document, doc_id).error_message
    assert not ok and err == document_service.FILE_GONE and str(get_settings().storage_dir) not in err


def test_reindex_command_prints_what_it_did(client, analyst, upload_and_process, capsys):
    upload_and_process(analyst, "fleet.txt", FLEET)
    cli.cmd_reindex(argparse.Namespace(if_needed=True))
    assert "nothing to do" in capsys.readouterr().out
    _wipe_vectors()
    cli.cmd_reindex(argparse.Namespace(if_needed=True))
    assert "rebuilt from stored text" in capsys.readouterr().out


def test_train_if_missing_trains_once_then_skips(capsys):
    cli.cmd_train(argparse.Namespace(csv=None, if_missing=True))
    assert "Trained" in capsys.readouterr().out
    cli.cmd_train(argparse.Namespace(csv=None, if_missing=True))
    assert "nothing to do" in capsys.readouterr().out
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(ModelVersion)) == 1
