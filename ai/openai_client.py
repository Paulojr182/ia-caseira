"""Cliente modular para Responses API, transcrição e síntese de voz."""

import base64
from collections import deque
from typing import Callable

from openai import OpenAI

from ai.model_router import ModelChoice, ModelRouter
from ai.prompts import build_instructions
from ai.tools import FUNCTION_TOOLS, ToolExecutor
from ai.usage_logger import log_usage
from core.config import (
    OPENAI_API_KEY,
    OPENAI_STT_MODEL,
)


class OpenAIProfessorClient:
    def __init__(
        self,
        on_board: Callable[[dict], None],
        on_status: Callable[[str], None],
        on_model: Callable[[str], None],
        client: OpenAI | None = None,
    ):
        if not OPENAI_API_KEY and client is None:
            raise ValueError(
                "OPENAI_API_KEY não encontrada. Crie um arquivo .env ao lado do aplicativo."
            )
        self.client = client or OpenAI(api_key=OPENAI_API_KEY, timeout=45.0)
        self.router = ModelRouter()
        self.executor = ToolExecutor(on_board=on_board, on_status=on_status)
        self.on_status = on_status
        self.on_model = on_model
        self.history: deque[tuple[str, str]] = deque(maxlen=10)

    def transcribe(self, wav_bytes: bytes) -> str:
        result = self.client.audio.transcriptions.create(
            model=OPENAI_STT_MODEL,
            file=("fala.wav", wav_bytes, "audio/wav"),
            language="pt",
            response_format="json",
        )
        return str(getattr(result, "text", result)).strip()

    def change_mode(self, text: str) -> str | None:
        return self.router.consume_mode_command(text)

    def respond(
        self,
        user_text: str,
        on_delta: Callable[[str], None],
        cancelled: Callable[[], bool],
        image_bytes: bytes | None = None,
    ) -> tuple[str, ModelChoice] | None:
        choice = self.router.choose(user_text)
        self.on_model(choice.tier)
        self.on_status(f"Pensando com {choice.tier}...")

        content: list[dict] = [{"type": "input_text", "text": self._contextual_input(user_text)}]
        if image_bytes:
            encoded = base64.b64encode(image_bytes).decode("ascii")
            content.append({
                "type": "input_image",
                "image_url": f"data:image/jpeg;base64,{encoded}",
                "detail": "auto",
            })
        input_items: list = [{"role": "user", "content": content}]
        tools = list(FUNCTION_TOOLS)
        if self.router.should_search_web(user_text):
            tools.append({"type": "web_search"})
            self.on_status("Pesquisando fontes atuais...")

        full_text = ""
        for _ in range(3):
            if cancelled():
                return None
            with self.client.responses.stream(
                model=choice.model,
                instructions=build_instructions(),
                input=input_items,
                tools=tools,
                parallel_tool_calls=False,
                max_output_tokens=3000,
                store=False,
                prompt_cache_key="alfred-professor-v1",
            ) as stream:
                for event in stream:
                    if cancelled():
                        break
                    if getattr(event, "type", "") == "response.output_text.delta":
                        delta = str(getattr(event, "delta", ""))
                        if delta:
                            full_text += delta
                            on_delta(delta)
                if cancelled():
                    return None
                response = stream.get_final_response()

            log_usage(
                response,
                choice.tier,
                "web" if self.router.should_search_web(user_text) else "conversa",
            )
            calls = [
                item for item in response.output
                if getattr(item, "type", "") == "function_call"
            ]
            if not calls:
                if not full_text:
                    full_text = str(getattr(response, "output_text", "") or "")
                    if full_text:
                        on_delta(full_text)
                break

            input_items.extend(
                item.model_dump(exclude_none=True, by_alias=True)
                if hasattr(item, "model_dump") else item
                for item in response.output
            )
            for call in calls:
                self.on_status(f"Executando {call.name}...")
                output = self.executor.execute(call.name, call.arguments)
                input_items.append({
                    "type": "function_call_output",
                    "call_id": call.call_id,
                    "output": output,
                })

        answer = full_text.strip()
        if answer:
            self.history.append(("Usuário", user_text.strip()))
            self.history.append(("ALFRED", answer))
        return answer, choice

    def _contextual_input(self, user_text: str) -> str:
        if not self.history:
            return user_text
        lines = [f"{role}: {text}" for role, text in self.history]
        context = "\n".join(lines)
        if len(context) > 6000:
            context = context[-6000:]
        return (
            "CONTEXTO RECENTE DA CONVERSA:\n"
            f"{context}\n\n"
            "PEDIDO ATUAL DO USUÁRIO:\n"
            f"{user_text}"
        )
