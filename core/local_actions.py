"""Ações locais explicitamente permitidas para o ALFRED."""

import os
import subprocess
import unicodedata
import webbrowser


APLICATIVOS_PERMITIDOS = {
    "calculadora": ("processo", ["calc.exe"]),
    "calc": ("processo", ["calc.exe"]),
    "bloco de notas": ("processo", ["notepad.exe"]),
    "notepad": ("processo", ["notepad.exe"]),
    "explorador de arquivos": ("processo", ["explorer.exe"]),
    "explorador": ("processo", ["explorer.exe"]),
    "paint": ("processo", ["mspaint.exe"]),
    "configuracoes": ("uri", "ms-settings:"),
    "navegador": ("url", "https://www.google.com"),
}


def _normalizar_nome(nome):
    texto = unicodedata.normalize("NFKD", str(nome).strip().lower())
    return "".join(caractere for caractere in texto if not unicodedata.combining(caractere))


def listar_aplicativos_permitidos():
    """Retorna nomes amigáveis sem repetir os aliases internos."""
    return [
        "calculadora",
        "bloco de notas",
        "explorador de arquivos",
        "paint",
        "configurações",
        "navegador",
    ]


def abrir_aplicativo(nome):
    """Abre apenas aplicativos presentes na lista segura."""
    nome_normalizado = _normalizar_nome(nome)
    configuracao = APLICATIVOS_PERMITIDOS.get(nome_normalizado)

    if not configuracao:
        disponiveis = ", ".join(listar_aplicativos_permitidos())
        return {
            "sucesso": False,
            "mensagem": (
                f"O aplicativo '{nome}' não está autorizado. "
                f"Aplicativos disponíveis: {disponiveis}."
            ),
        }

    tipo, destino = configuracao

    try:
        if tipo == "processo":
            subprocess.Popen(destino, shell=False)
        elif tipo == "uri":
            os.startfile(destino)
        elif tipo == "url":
            if not webbrowser.open(destino, new=2):
                raise RuntimeError("O navegador padrão não respondeu.")

        return {
            "sucesso": True,
            "mensagem": f"{nome} foi aberto com sucesso.",
        }
    except (OSError, RuntimeError) as erro:
        return {
            "sucesso": False,
            "mensagem": f"Não foi possível abrir {nome}: {erro}",
        }
