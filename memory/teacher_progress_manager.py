"""Progresso resumido do aluno, persistido localmente e sem transcrições."""

import json
import re
import unicodedata
from datetime import datetime
from threading import Lock

from core.config import PASTA_APLICATIVO


PROGRESS_FILE = PASTA_APLICATIVO / "memory" / "teacher_progress.json"
_LOCK = Lock()


def _key(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value).strip().lower())
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")[:80] or "geral"


def _load() -> dict:
    if not PROGRESS_FILE.exists():
        return {"version": 1, "subjects": {}}
    try:
        data = json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("subjects"), dict):
            return data
    except (OSError, json.JSONDecodeError):
        pass
    return {"version": 1, "subjects": {}}


def _save(data: dict) -> None:
    PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary = PROGRESS_FILE.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temporary.replace(PROGRESS_FILE)


def get_teacher_progress(subject: str = "") -> dict:
    with _LOCK:
        subjects = _load()["subjects"]
    if subject:
        key = _key(subject)
        return {"subject": key, "progress": subjects.get(key, {})}
    compact = dict(list(subjects.items())[-8:])
    return {"subjects": compact}


def update_teacher_progress(
    subject: str,
    topic: str,
    result: str,
    summary: str,
    next_step: str,
) -> dict:
    subject_key = _key(subject)
    topic_key = _key(topic)
    result = result if result in {"studied", "correct", "incorrect", "difficulty"} else "studied"
    with _LOCK:
        data = _load()
        subject_data = data["subjects"].setdefault(
            subject_key,
            {"strengths": [], "difficulties": [], "topics": {}, "last_lesson": ""},
        )
        subject_data["last_lesson"] = datetime.now().isoformat(timespec="seconds")
        subject_data["topics"][topic_key] = {
            "result": result,
            "summary": str(summary)[:500],
            "next_step": str(next_step)[:300],
        }
        target = "strengths" if result == "correct" else "difficulties"
        if result in {"correct", "incorrect", "difficulty"} and topic_key not in subject_data[target]:
            subject_data[target].append(topic_key)
            subject_data[target] = subject_data[target][-20:]
        _save(data)
    return {"success": True, "subject": subject_key, "topic": topic_key}
