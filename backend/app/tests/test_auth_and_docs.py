from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import AuditEvent, DocumentChunk
from app.services.vector_store import get_vector_store
from app.tests.conftest import SAMPLE_TEXT, make_docx, make_pdf, make_xlsx, process_jobs


def test_health_is_public(client):
    assert client.get("/api/v1/health").json() == {"status": "ok"}
    ready = client.get("/api/v1/health/ready").json()
    assert ready["database"]["ok"] and ready["vector_store"]["ok"]
    assert ready["ollama"]["ok"] is False  # no Ollama in tests; app still serves


def test_register_login_me(client):
    r = client.post("/api/v1/auth/register", json={"email": "New@Example.com", "password": "a-long-password"})
    assert r.status_code == 201 and r.json()["role"] == "analyst"
    assert "password" not in r.text
    tok = client.post("/api/v1/auth/login", json={"email": "new@example.com", "password": "a-long-password"}).json()
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tok['access_token']}"})
    assert me.status_code == 200 and me.json()["email"] == "new@example.com"


def test_register_validation_and_duplicates(client):
    assert client.post("/api/v1/auth/register", json={"email": "bad", "password": "a-long-password"}).status_code == 422
    assert client.post("/api/v1/auth/register", json={"email": "a@b.co", "password": "short"}).status_code == 422
    ok = {"email": "a@b.co", "password": "a-long-password"}
    assert client.post("/api/v1/auth/register", json=ok).status_code == 201
    assert client.post("/api/v1/auth/register", json=ok).status_code == 409


def test_login_failure_is_audited_and_generic(client, admin):
    r = client.post("/api/v1/auth/login", json={"email": "admin@example.com", "password": "wrong-password"})
    assert r.status_code == 401
    r2 = client.post("/api/v1/auth/login", json={"email": "nobody@example.com", "password": "wrong-password"})
    assert r.json()["error"]["message"] == r2.json()["error"]["message"]
    with SessionLocal() as s:
        events = s.scalars(select(AuditEvent).where(AuditEvent.action == "auth.login")).all()
    assert {e.outcome for e in events} >= {"success", "failure"}
    assert all("password" not in (e.detail or "") for e in events)


def test_protected_endpoints_reject_anonymous_and_bad_tokens(client):
    for path in ("/auth/me", "/documents", "/conversations", "/analytics/overview", "/audit", "/reviews"):
        assert client.get(f"/api/v1{path}").status_code == 401, path
    assert client.get("/api/v1/auth/me", headers={"Authorization": "Bearer garbage"}).status_code == 401


def test_role_enforcement(client, analyst, reviewer, admin):
    assert client.get("/api/v1/audit", headers=analyst).status_code == 403
    assert client.get("/api/v1/audit", headers=reviewer).status_code == 403
    assert client.get("/api/v1/audit", headers=admin).status_code == 200
    assert client.get("/api/v1/reviews", headers=analyst).status_code == 403
    assert client.get("/api/v1/reviews", headers=reviewer).status_code == 200
    assert client.post("/api/v1/classification/train", headers=analyst, json={}).status_code == 403
    assert client.get("/api/v1/users", headers=analyst).status_code == 403
    assert client.post("/api/v1/documents", headers=reviewer,
                       files=[("files", ("a.txt", b"hi", "text/plain"))]).status_code == 403


def test_denied_access_is_audited(client, analyst, admin):
    client.get("/api/v1/audit", headers=analyst)
    logs = client.get("/api/v1/audit?outcome=denied", headers=admin).json()
    assert any(e["action"] == "authz.denied" for e in logs)


def test_admin_can_change_roles_but_not_self_demote(client, admin, make_auth, db):
    make_auth("target@example.com")
    users = client.get("/api/v1/users", headers=admin).json()
    target = next(u for u in users if u["email"] == "target@example.com")
    r = client.patch(f"/api/v1/users/{target['id']}/role", headers=admin, json={"role": "reviewer"})
    assert r.status_code == 200 and r.json()["role"] == "reviewer"
    me = client.get("/api/v1/auth/me", headers=admin).json()
    assert client.patch(f"/api/v1/users/{me['id']}/role", headers=admin, json={"role": "analyst"}).status_code == 400
    assert client.patch(f"/api/v1/users/{target['id']}/role", headers=admin, json={"role": "root"}).status_code == 422


def test_upload_process_and_detail(client, analyst, upload_and_process):
    doc_id = upload_and_process(analyst, "budget.txt", SAMPLE_TEXT)
    d = client.get(f"/api/v1/documents/{doc_id}", headers=analyst).json()
    assert d["status"] == "completed" and d["chunk_count"] >= 1 and d["indexed"]
    assert "purchasing" in d["text_preview"]
    stages = [e["stage"] for e in d["events"]]
    assert stages[0] == "uploaded" and "chunking" in stages and stages[-1] == "completed"
    labels = {e["label"] for e in d["entities"]}
    assert {"DATE", "MONEY"} & labels or "DATE" in labels
    listing = client.get("/api/v1/documents", headers=analyst).json()
    assert listing["total"] == 1 and listing["items"][0]["filename"] == "budget.txt"


def test_upload_all_supported_formats(client, analyst, upload_and_process):
    files = {
        "r.pdf": (make_pdf(["Quarterly report on training outcomes."]), "application/pdf"),
        "m.docx": (make_docx(["Memo about office relocation."]), None),
        "t.xlsx": (make_xlsx([["item", "price"], ["pump", 40]]), None),
        "d.csv": (b"name,qty\nbolt,10\n", "text/csv"),
        "n.txt": (b"plain note about parking", "text/plain"),
    }
    for name, (data, mime) in files.items():
        doc_id = upload_and_process(analyst, name, data, mime)
        assert client.get(f"/api/v1/documents/{doc_id}", headers=analyst).json()["status"] == "completed", name


def test_pdf_chunks_keep_page_numbers(client, analyst, upload_and_process, db):
    doc_id = upload_and_process(analyst, "p.pdf", make_pdf(["Alpha content here.", "Bravo content there."]),
                                "application/pdf")
    pages = {c.page for c in db.scalars(select(DocumentChunk).where(DocumentChunk.document_id == doc_id))}
    assert pages == {1, 2}


def test_upload_rejections(client, analyst, upload):
    assert upload(analyst, "evil.exe", b"MZ\x90\x00").json()["errors"][0]["error"].startswith("Unsupported")
    assert "PDF" in upload(analyst, "fake.pdf", b"<html>", "application/pdf").json()["errors"][0]["error"]
    assert upload(analyst, "empty.txt", b"").json()["errors"][0]["error"] == "The file is empty."
    assert client.get("/api/v1/documents", headers=analyst).json()["total"] == 0


def test_path_traversal_filename_is_neutralised(client, analyst, upload, db):
    r = upload(analyst, "../../../evil.txt", b"harmless text").json()
    assert r["results"][0]["document"]["filename"] == "evil.txt"
    from app.core.config import get_settings
    assert not (get_settings().storage_dir.parent.parent / "evil.txt").exists()


def test_duplicate_upload_is_detected_per_owner(client, analyst, other_analyst, upload):
    a = upload(analyst, "a.txt", b"identical content here").json()["results"][0]
    b = upload(analyst, "renamed.txt", b"identical content here").json()["results"][0]
    assert not a["duplicate"] and b["duplicate"]
    assert a["document"]["id"] == b["document"]["id"]
    c = upload(other_analyst, "a.txt", b"identical content here").json()["results"][0]
    assert not c["duplicate"] and c["document"]["id"] != a["document"]["id"]


def test_size_limit_enforced(client, analyst, upload, monkeypatch):
    from app.core.config import get_settings
    monkeypatch.setattr(get_settings(), "max_upload_mb", 0)
    assert "limit" in upload(analyst, "big.txt", b"x" * 10).json()["errors"][0]["error"]


def test_cross_user_document_isolation(client, analyst, other_analyst, admin, upload_and_process):
    doc_id = upload_and_process(analyst, "secret.txt", SAMPLE_TEXT)
    for method, path in (("get", ""), ("get", "/content"), ("get", "/download"), ("delete", ""),
                         ("post", "/reprocess"), ("post", "/reclassify")):
        r = getattr(client, method)(f"/api/v1/documents/{doc_id}{path}", headers=other_analyst)
        assert r.status_code == 404, (method, path, r.status_code)
    assert client.get("/api/v1/documents", headers=other_analyst).json()["total"] == 0
    assert client.get(f"/api/v1/documents/{doc_id}", headers=admin).status_code == 200  # admin policy


def test_download_is_audited_and_returns_original(client, analyst, admin, upload_and_process):
    doc_id = upload_and_process(analyst, "d.txt", "original bytes")
    r = client.get(f"/api/v1/documents/{doc_id}/download", headers=analyst)
    assert r.status_code == 200 and r.content == b"original bytes"
    logs = client.get("/api/v1/audit?action=document.download", headers=admin).json()
    assert logs and logs[0]["target_id"] == doc_id


def test_delete_removes_file_chunks_and_vectors(client, analyst, upload_and_process, db):
    from app.services import document_service
    doc_id = upload_and_process(analyst, "d.txt", SAMPLE_TEXT)
    from app.models import Document
    path = document_service.storage_path(db.get(Document, doc_id).storage_id)
    assert path.exists() and get_vector_store().count() > 0
    assert client.delete(f"/api/v1/documents/{doc_id}", headers=analyst).status_code == 204
    assert not path.exists() and get_vector_store().count() == 0
    assert client.get(f"/api/v1/documents/{doc_id}", headers=analyst).status_code == 404
    with SessionLocal() as s:
        assert s.scalar(select(DocumentChunk).where(DocumentChunk.document_id == doc_id)) is None


def test_failed_delete_is_visible_and_retryable(client, analyst, upload_and_process, monkeypatch):
    from app.core.errors import ServiceUnavailable
    from app.services import vector_store
    doc_id = upload_and_process(analyst, "d.txt", SAMPLE_TEXT)

    def boom(self, document_id):
        raise ServiceUnavailable("down")
    monkeypatch.setattr(vector_store.VectorStore, "delete_document", boom)
    assert client.delete(f"/api/v1/documents/{doc_id}", headers=analyst).status_code == 503
    assert client.get(f"/api/v1/documents/{doc_id}", headers=analyst).json()["deletion_state"] == "delete_failed"
    monkeypatch.undo()
    assert client.delete(f"/api/v1/documents/{doc_id}", headers=analyst).status_code == 204


def test_corrupt_pdf_fails_with_safe_message(client, analyst, upload):
    r = upload(analyst, "bad.pdf", b"%PDF-1.4 this is not really a pdf", "application/pdf")
    doc_id = r.json()["results"][0]["document"]["id"]
    process_jobs()
    d = client.get(f"/api/v1/documents/{doc_id}", headers=analyst).json()
    assert d["status"] == "failed" and d["error_message"]
    assert "\\" not in d["error_message"] and "uploads" not in d["error_message"]  # no server paths


def test_embedding_outage_degrades_gracefully_and_reprocess_is_idempotent(client, analyst, upload, monkeypatch):
    from app.core.errors import ServiceUnavailable
    from app.services import document_service
    emb = document_service.get_embedder()
    monkeypatch.setattr(type(emb), "embed", lambda self, t: (_ for _ in ()).throw(ServiceUnavailable("Ollama is not reachable.")))
    doc_id = upload(analyst, "d.txt", SAMPLE_TEXT).json()["results"][0]["document"]["id"]
    process_jobs()
    d = client.get(f"/api/v1/documents/{doc_id}", headers=analyst).json()
    assert d["status"] == "failed" and "keyword search works" in d["error_message"]
    kw = client.get("/api/v1/search?query=purchase+order", headers=analyst).json()
    assert kw["total"] >= 1  # keyword search unaffected
    monkeypatch.undo()
    assert client.post(f"/api/v1/documents/{doc_id}/reprocess", headers=analyst).status_code == 202
    process_jobs()
    assert client.get(f"/api/v1/documents/{doc_id}", headers=analyst).json()["status"] == "completed"
    count = get_vector_store().count()
    client.post(f"/api/v1/documents/{doc_id}/reprocess", headers=analyst)
    process_jobs()
    assert get_vector_store().count() == count  # no duplicate vectors after retry


def test_listing_filters_and_pagination(client, analyst, upload_and_process):
    for i in range(3):
        upload_and_process(analyst, f"doc{i}.txt", f"unique content number {i} about topic {i}")
    upload_and_process(analyst, "x.csv", "a,b\n1,2", "text/csv")
    r = client.get("/api/v1/documents?page_size=2&sort=filename", headers=analyst).json()
    assert r["total"] == 4 and len(r["items"]) == 2
    assert client.get("/api/v1/documents?file_type=csv", headers=analyst).json()["total"] == 1
    assert client.get("/api/v1/documents?q=doc1", headers=analyst).json()["total"] == 1
    assert client.get("/api/v1/documents?sort=bogus", headers=analyst).status_code == 422
