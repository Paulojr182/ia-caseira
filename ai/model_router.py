"""Roteamento econômico entre os modelos Luna, Terra e Sol."""

from dataclasses import dataclass
import re

from core.config import (
    OPENAI_MODEL_LUNA,
    OPENAI_MODEL_MODE,
    OPENAI_MODEL_SOL,
    OPENAI_MODEL_TERRA,
)


@dataclass(frozen=True)
class ModelChoice:
    tier: str
    model: str
    reason: str


class ModelRouter:
    MODES = {"auto", "economico", "normal", "avancado", "luna", "terra", "sol"}

    def __init__(self, mode: str = OPENAI_MODEL_MODE):
        self.mode = mode if mode in self.MODES else "auto"
        self._next_tier: str | None = None

    @staticmethod
    def _normalize(text: str) -> str:
        return re.sub(r"\s+", " ", str(text).lower()).strip()

    def consume_mode_command(self, text: str) -> str | None:
        value = self._normalize(text)
        if "use sol nesta pergunta" in value:
            self._next_tier = "sol"
            return "SOL será usado somente na próxima pergunta."
        commands = {
            "modo economico": ("economico", "Modo econômico ativado. Vou priorizar Luna."),
            "modo econômico": ("economico", "Modo econômico ativado. Vou priorizar Luna."),
            "modo normal": ("normal", "Modo normal ativado. Terra será o professor padrão."),
            "modo avancado": ("avancado", "Modo avançado ativado. Sol poderá ser usado em tarefas complexas."),
            "modo avançado": ("avancado", "Modo avançado ativado. Sol poderá ser usado em tarefas complexas."),
        }
        for phrase, (mode, answer) in commands.items():
            if phrase in value:
                self.mode = mode
                return answer
        return None

    def choose(self, text: str) -> ModelChoice:
        value = self._normalize(text)
        forced = self._next_tier
        self._next_tier = None
        if forced:
            return self._choice(forced, "solicitado para a próxima pergunta")
        if self.mode in {"luna", "terra", "sol"}:
            return self._choice(self.mode, "modelo forçado na configuração")
        if self.mode == "economico":
            return self._choice("luna", "modo econômico")

        complex_terms = (
            "análise profunda", "analise profunda", "questão extremamente difícil",
            "questao extremamente dificil", "legislação complexa", "legislacao complexa",
            "compare estes documentos", "demonstração matemática", "demonstracao matematica",
        )
        if self.mode == "avancado" and any(term in value for term in complex_terms):
            return self._choice("sol", "tarefa complexa em modo avançado")

        teacher_terms = (
            "explique", "explica", "aula", "professor", "ensine", "não entendi",
            "nao entendi", "exemplo", "exercício", "exercicio", "simulado",
            "compare", "por que", "como funciona", "quadro",
        )
        if any(term in value for term in teacher_terms):
            return self._choice("terra", "explicação ou tarefa pedagógica")

        simple_terms = (
            "bom dia", "boa tarde", "boa noite", "obrigado", "resuma", "resumo curto",
            "flashcard", "próxima pergunta", "proxima pergunta", "abra ", "pesquise ",
        )
        if len(value) < 90 or any(term in value for term in simple_terms):
            return self._choice("luna", "tarefa simples e curta")
        return self._choice("terra", "complexidade intermediária")

    @staticmethod
    def should_search_web(text: str) -> bool:
        value = ModelRouter._normalize(text)
        terms = (
            "pesquise", "procure na internet", "busque na internet", "mais recente",
            "atualizado", "atualizada", "hoje", "últimas notícias", "ultimas noticias",
            "edital", "essa lei mudou", "informação atual", "informacao atual",
        )
        return any(term in value for term in terms)

    @staticmethod
    def _choice(tier: str, reason: str) -> ModelChoice:
        models = {
            "luna": OPENAI_MODEL_LUNA,
            "terra": OPENAI_MODEL_TERRA,
            "sol": OPENAI_MODEL_SOL,
        }
        return ModelChoice(tier=tier.upper(), model=models[tier], reason=reason)
