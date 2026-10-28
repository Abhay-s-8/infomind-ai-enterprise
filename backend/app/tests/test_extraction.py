import pytest

from app.services import extraction_service as ex
from app.tests.conftest import make_docx, make_pdf, make_xlsx


def test_normalize_text_collapses_whitespace_and_strips_control_chars():
    assert ex.normalize_text("a  b\r\n\r\n\r\n\r\nc\x00d") == "a b\n\ncd"


def test_safe_filename_drops_directory_components():
    assert ex.safe_filename("../../etc/passwd") == "passwd"
    assert ex.safe_filename("C:\\Users\\x\\evil.txt") == "evil.txt"
    assert ex.safe_filename(None) == "unnamed"


def test_validate_rejects_unknown_extension_and_empty():
    with pytest.raises(ex.ValidationError):
        ex.validate_upload("run.exe", None, b"MZ...", 1000)
    with pytest.raises(ex.ValidationError):
        ex.validate_upload("a.txt", None, b"", 1000)


def test_validate_rejects_oversize():
    with pytest.raises(ex.ValidationError, match="limit"):
        ex.validate_upload("a.txt", "text/plain", b"x" * 2_000_000, 1_000_000)


def test_validate_rejects_mime_mismatch():
    with pytest.raises(ex.ValidationError, match="content type"):
        ex.validate_upload("a.pdf", "text/html", b"%PDF-1.4", 1000)


def test_validate_rejects_fake_pdf_docx_and_binary_txt():
    with pytest.raises(ex.ValidationError):
        ex.validate_upload("a.pdf", None, b"<html>not a pdf</html>", 1000)
    with pytest.raises(ex.ValidationError):
        ex.validate_upload("a.docx", None, b"plain text pretending", 1000)
    with pytest.raises(ex.ValidationError):
        ex.validate_upload("a.txt", None, b"\x00\x01\x02binary", 1000)


def test_validate_accepts_real_files():
    assert ex.validate_upload("a.pdf", "application/pdf", make_pdf(["hi"]), 10**7) == "pdf"
    assert ex.validate_upload("a.docx", None, make_docx(["hi"]), 10**7) == "docx"
    assert ex.validate_upload("a.xlsx", None, make_xlsx([[1, 2]]), 10**7) == "xlsx"


def test_extract_pdf_keeps_page_numbers(tmp_path):
    p = tmp_path / "f"
    p.write_bytes(make_pdf(["First page about budgets.", "Second page about schedules."]))
    pages = ex.extract_pages(p, "pdf")
    assert [pg.number for pg in pages] == [1, 2]
    assert "schedules" in pages[1].text


def test_extract_docx_xlsx_csv(tmp_path):
    p = tmp_path / "f"
    p.write_bytes(make_docx(["Paragraph one", "Paragraph two"]))
    assert "Paragraph two" in ex.extract_pages(p, "docx")[0].text
    p.write_bytes(make_xlsx([["item", "cost"], ["pump", 40]]))
    assert "pump | 40" in ex.extract_pages(p, "xlsx")[0].text
    p.write_text("a,b\n1,2\n")
    assert "1 | 2" in ex.extract_pages(p, "csv")[0].text


def test_chunking_respects_size_overlap_and_pages():
    pages = [ex.Page(1, "Sentence number one is here. " * 60), ex.Page(2, "Short page.")]
    chunks = ex.chunk_pages(pages, size=300, overlap=50)
    assert len(chunks) > 3
    assert all(len(c.text) <= 300 for c in chunks)
    assert [c.index for c in chunks] == list(range(len(chunks)))
    assert chunks[-1].page == 2 and chunks[0].page == 1


def test_chunking_rejects_bad_params():
    with pytest.raises(ValueError):
        ex.chunk_pages([ex.Page(None, "x")], size=100, overlap=100)
