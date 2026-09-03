"""Registro local e sem credenciais do consumo da API."""

import json
from datetime import datetime
from threading import Lock

from core.config import PASTA_APLICATIVO


_LOCK = Lock()


def log_usage(response, tier: str, task_type: str) -> None:
    usage = getattr(response, "usage", None)
    if not usage:
        return
    details = getattr(usage, "input_tokens_details", None)
    record = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "modelo": getattr(response, "model", ""),
        "tier": tier,
        "tipo_tarefa": task_type,
        "input_tokens": getattr(usage, "input_tokens", 0) or 0,
        "cached_input_tokens": getattr(details, "cached_tokens", 0) or 0,
        "output_tokens": getattr(usage, "output_tokens", 0) or 0,
    }
    path = PASTA_APLICATIVO / "logs" / "api_usage.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with _LOCK, path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False) + "\n")
