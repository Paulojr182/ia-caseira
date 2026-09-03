"""Busca local econômica em materiais TXT, MD, PDF e DOCX."""

import re
from pathlib import Path

from core.config import PASTA_APLICATIVO


MATERIALS_DIR = PASTA_APLICATIVO / "study" / "materials"
EXAMS_DIR = PASTA_APLICATIVO / "study" / "exams"


def _extract_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md"}:
        return path.read_text(encoding="utf-8", errors="ignore")
    if suffix == ".pdf":
        from pypdf import PdfReader

        return "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)
    if suffix == ".docx":
        from docx import Document

        return "\n".join(paragraph.text for paragraph in Document(path).paragraphs)
    return ""


def search_materials(query: str, limit: int = 5) -> dict:
    words = {
        word for word in re.findall(r"[a-záàâãéêíóôõúç0-9]{3,}", query.lower())
    }
    if not words:
        return {"success": False, "message": "Consulta muito curta.", "snippets": []}

    candidates = []
    for directory in (MATERIALS_DIR, EXAMS_DIR):
        if not directory.exists():
            continue
        for path in list(directory.rglob("*"))[:100]:
            if not path.is_file() or path.suffix.lower() not in {".txt", ".md", ".pdf", ".docx"}:
                continue
            try:
                text = _extract_text(path)[:800_000]
            except Exception:
                continue
            paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
            for paragraph in paragraphs:
                lowered = paragraph.lower()
                score = sum(lowered.count(word) for word in words)
                if score:
                    candidates.append((score, path.name, paragraph[:1200]))

    candidates.sort(key=lambda item: item[0], reverse=True)
    snippets = [
        {"arquivo": name, "trecho": text}
        for _score, name, text in candidates[: max(1, min(limit, 8))]
    ]
    return {"success": True, "query": query, "snippets": snippets}
