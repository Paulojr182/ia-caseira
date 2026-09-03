"""Criação segura de anotações de estudo locais."""

import re
import unicodedata
from datetime import datetime

from core.config import PASTA_APLICATIVO


NOTES_DIR = PASTA_APLICATIVO / "study" / "notes"


def save_note(title: str, content: str) -> dict:
    normalized = unicodedata.normalize("NFKD", title)
    slug = "".join(char for char in normalized if not unicodedata.combining(char))
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", slug).strip("-").lower()[:60] or "anotacao"
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = NOTES_DIR / f"{timestamp}-{slug}.md"
    path.write_text(f"# {title.strip()}\n\n{content.strip()}\n", encoding="utf-8")
    return {"success": True, "arquivo": path.name}
