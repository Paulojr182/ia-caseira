"""Ferramentas autorizadas e validadas usadas pelo modelo OpenAI."""

import json
from typing import Any, Callable

from core.local_actions import abrir_aplicativo, pesquisar_no_navegador
from memory.memory_manager import esquecer_memoria, listar_memorias, salvar_memoria
from memory.teacher_progress_manager import get_teacher_progress, update_teacher_progress
from study.material_search import search_materials
from study.notes import save_note


def _function_tool(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {
        "type": "function",
        "name": name,
        "description": description,
        "parameters": {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False,
        },
        "strict": True,
    }


BOARD_PROPERTIES = {
    "titulo": {"type": "string"},
    "objetivo": {"type": "string"},
    "resumo": {"type": "string"},
    "topicos": {"type": "array", "items": {"type": "string"}},
    "diagrama": {"type": "array", "items": {"type": "string"}},
    "etapas": {"type": "array", "items": {"type": "string"}},
    "exemplo": {"type": "string"},
    "formula": {"type": "string"},
    "erros_comuns": {"type": "array", "items": {"type": "string"}},
    "destaque": {"type": "string"},
}


FUNCTION_TOOLS = [
    _function_tool(
        "mostrar_conteudo_visual",
        "Monta uma aula completa no quadro local antes de uma explicação educacional.",
        BOARD_PROPERTIES,
        list(BOARD_PROPERTIES),
    ),
    _function_tool(
        "limpar_quadro",
        "Limpa o quadro quando o usuário pedir explicitamente.",
        {},
        [],
    ),
    _function_tool(
        "abrir_aplicativo",
        "Abre um aplicativo Windows permitido quando solicitado explicitamente.",
        {"nome": {"type": "string"}},
        ["nome"],
    ),
    _function_tool(
        "pesquisar_no_navegador",
        "Abre no navegador uma pesquisa solicitada explicitamente pelo usuário.",
        {"tema": {"type": "string"}},
        ["tema"],
    ),
    _function_tool(
        "salvar_memoria",
        "Salva uma informação curta somente quando o usuário pedir para lembrar.",
        {"texto": {"type": "string"}},
        ["texto"],
    ),
    _function_tool(
        "listar_memorias",
        "Lista memórias quando o usuário perguntar o que está guardado.",
        {},
        [],
    ),
    _function_tool(
        "esquecer_memoria",
        "Remove uma memória específica quando o usuário pedir.",
        {"referencia": {"type": "string"}},
        ["referencia"],
    ),
    _function_tool(
        "consultar_progresso",
        "Consulta o resumo local do estudo para continuar uma aula anterior.",
        {"materia": {"type": "string"}},
        ["materia"],
    ),
    _function_tool(
        "atualizar_progresso",
        "Registra um marco resumido da aula ou o resultado de um exercício.",
        {
            "materia": {"type": "string"},
            "tema": {"type": "string"},
            "resultado": {
                "type": "string",
                "enum": ["studied", "correct", "incorrect", "difficulty"],
            },
            "resumo": {"type": "string"},
            "proximo_passo": {"type": "string"},
        },
        ["materia", "tema", "resultado", "resumo", "proximo_passo"],
    ),
    _function_tool(
        "buscar_material_local",
        "Busca somente trechos relevantes nos materiais locais de estudo.",
        {"consulta": {"type": "string"}},
        ["consulta"],
    ),
    _function_tool(
        "salvar_anotacao",
        "Salva uma anotação Markdown somente quando o usuário pedir.",
        {"titulo": {"type": "string"}, "conteudo": {"type": "string"}},
        ["titulo", "conteudo"],
    ),
]


class ToolExecutor:
    def __init__(
        self,
        on_board: Callable[[dict], None],
        on_status: Callable[[str], None],
    ):
        self.on_board = on_board
        self.on_status = on_status

    def execute(self, name: str, raw_arguments: str | dict | None) -> str:
        try:
            arguments = (
                raw_arguments
                if isinstance(raw_arguments, dict)
                else json.loads(raw_arguments or "{}")
            )
        except json.JSONDecodeError:
            return json.dumps({"sucesso": False, "erro": "Argumentos inválidos."})

        try:
            if name == "mostrar_conteudo_visual":
                content = {key: arguments.get(key, [] if key in {
                    "topicos", "diagrama", "etapas", "erros_comuns"
                } else "") for key in BOARD_PROPERTIES}
                self.on_status("Montando aula no quadro...")
                self.on_board(content)
                result: Any = {"sucesso": True, "mensagem": "Quadro atualizado."}
            elif name == "limpar_quadro":
                self.on_board({"action": "clear"})
                result = {"sucesso": True, "mensagem": "Quadro limpo."}
            elif name == "abrir_aplicativo":
                result = abrir_aplicativo(arguments.get("nome", ""))
            elif name == "pesquisar_no_navegador":
                result = pesquisar_no_navegador(arguments.get("tema", ""))
            elif name == "salvar_memoria":
                result = {"sucesso": True, "mensagem": salvar_memoria(arguments.get("texto", ""))}
            elif name == "listar_memorias":
                result = {"sucesso": True, "mensagem": listar_memorias()}
            elif name == "esquecer_memoria":
                result = {"sucesso": True, "mensagem": esquecer_memoria(arguments.get("referencia", ""))}
            elif name == "consultar_progresso":
                result = get_teacher_progress(arguments.get("materia", ""))
            elif name == "atualizar_progresso":
                result = update_teacher_progress(
                    arguments.get("materia", ""),
                    arguments.get("tema", ""),
                    arguments.get("resultado", "studied"),
                    arguments.get("resumo", ""),
                    arguments.get("proximo_passo", ""),
                )
            elif name == "buscar_material_local":
                result = search_materials(arguments.get("consulta", ""))
            elif name == "salvar_anotacao":
                result = save_note(
                    arguments.get("titulo", "Anotação"),
                    arguments.get("conteudo", ""),
                )
            else:
                result = {"sucesso": False, "erro": f"Ferramenta não autorizada: {name}"}
        except Exception as error:
            result = {"sucesso": False, "erro": str(error)}
        return json.dumps(result, ensure_ascii=False)
