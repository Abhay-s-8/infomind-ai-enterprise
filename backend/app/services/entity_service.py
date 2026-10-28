"""Entity extraction: rule-based patterns (always available) plus spaCy NER when the optional model is installed.
Extraction is heuristic and will contain errors; reviewers can remove incorrect annotations."""
import re
from functools import lru_cache

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models import DocumentChunk, ExtractedEntity

_RULES = {
    "MONEY": re.compile(r"(?:[$€£]\s?\d[\d,]*(?:\.\d+)?(?:\s?(?:million|billion|k|m|bn))?)|(?:\b\d[\d,]*(?:\.\d+)?\s?(?:USD|EUR|GBP|INR)\b)", re.I),
    "DATE": re.compile(r"\b(?:\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.? \d{1,2}(?:, \d{4})?|\d{1,2} (?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{4})\b"),
    "TIME": re.compile(r"\b(?:[01]?\d|2[0-3]):[0-5]\d(?:\s?[AP]M)?\b", re.I),
    "EMAIL": re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),
}
_SPACY_LABELS = {"PERSON": "PERSON", "ORG": "ORG", "GPE": "LOCATION", "LOC": "LOCATION", "DATE": "DATE",
                 "TIME": "TIME", "MONEY": "MONEY"}


@lru_cache
def _spacy_nlp():
    try:
        import spacy

        return spacy.load("en_core_web_sm", disable=["lemmatizer"])
    except Exception:  # spaCy or the model is an optional dependency
        return None


def spacy_available() -> bool:
    return _spacy_nlp() is not None


def extract_entities(text: str) -> list[tuple[str, str, str]]:
    """Return unique (text, label, method) tuples."""
    found: dict[tuple[str, str], str] = {}
    for label, rx in _RULES.items():
        for m in rx.finditer(text):
            found.setdefault((m.group(0).strip(), label), "rule")
    nlp = _spacy_nlp()
    if nlp is not None:
        for ent in nlp(text[:100_000]).ents:
            label = _SPACY_LABELS.get(ent.label_)
            if label:
                found[(ent.text.strip(), label)] = "spacy"
    return [(t, label, method) for (t, label), method in found.items() if t]


def index_document_entities(db: Session, document_id: str) -> int:
    db.execute(delete(ExtractedEntity).where(ExtractedEntity.document_id == document_id))
    chunks = db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).all()
    seen, count = set(), 0
    for ch in chunks:
        for text, label, method in extract_entities(ch.text):
            if (text, label) in seen:
                continue
            seen.add((text, label))
            db.add(ExtractedEntity(document_id=document_id, chunk_id=ch.id, text=text[:500], label=label,
                                   method=method))
            count += 1
    db.commit()
    return count
