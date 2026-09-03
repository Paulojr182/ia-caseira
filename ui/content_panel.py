"""Quadro de aula usado pelo ALFRED para explicações visuais."""

from html import escape

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)


class ContentPanel(QWidget):
    """Quadro negro que organiza e revela uma aula em poucas etapas."""

    voltar_solicitado = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._conteudo = {}
        self._fase = 3

        # Poucas atualizações evitam repinturas pesadas e mantêm a janela fluida.
        self._timer_escrita = QTimer(self)
        self._timer_escrita.setInterval(1150)
        self._timer_escrita.timeout.connect(self._avancar_escrita)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(12)

        barra = QHBoxLayout()
        titulo = QLabel("SALA DE AULA // QUADRO DO ALFRED")
        titulo.setObjectName("tituloRegistro")
        self.btn_voltar = QPushButton("VOLTAR AO NÚCLEO")
        self.btn_voltar.setFixedWidth(175)
        self.btn_voltar.clicked.connect(self._voltar)
        barra.addWidget(titulo)
        barra.addStretch(1)
        barra.addWidget(self.btn_voltar)

        self.quadro = QTextBrowser()
        self.quadro.setFrameShape(QFrame.NoFrame)
        self.quadro.setOpenExternalLinks(False)
        self.quadro.setStyleSheet(
            "QTextBrowser {"
            "background-color: #10231d;"
            "border: 10px solid #5a3824;"
            "border-radius: 5px;"
            "padding: 12px;"
            "}"
        )

        layout.addLayout(barra)
        layout.addWidget(self.quadro, 1)
        self.mostrar_boas_vindas()

    @staticmethod
    def _lista(valor, limite):
        if not valor:
            return []
        if not isinstance(valor, list):
            valor = [valor]
        return [str(item).strip() for item in valor[:limite] if str(item).strip()]

    def mostrar_boas_vindas(self):
        self._timer_escrita.stop()
        self._conteudo = {
            "titulo": "Quadro de aula",
            "objetivo": "Compreender o assunto, visualizar as relações e praticar com um exemplo.",
            "resumo": (
                "Pergunte qualquer matéria ao Alfred. Ele dará a explicação por voz "
                "enquanto organiza a aula neste quadro."
            ),
            "topicos": [
                "Definição em linguagem clara",
                "Conceitos conectados passo a passo",
                "Exemplo prático e erros comuns",
            ],
            "diagrama": ["Ideia inicial", "Como funciona", "Aplicação"],
            "etapas": [],
            "exemplo": "Diga: Alfred, explique fotossíntese como um professor.",
            "formula": "",
            "erros_comuns": [],
            "destaque": "Você pode interromper e pedir que ele aprofunde qualquer parte.",
        }
        self._fase = 3
        self._renderizar()

    def mostrar_conteudo(self, conteudo):
        self._timer_escrita.stop()
        etapas = self._lista(conteudo.get("etapas"), 6)
        diagrama = self._lista(conteudo.get("diagrama"), 6) or etapas

        self._conteudo = {
            "titulo": str(conteudo.get("titulo") or "Explicação"),
            "objetivo": str(conteudo.get("objetivo") or "Entender a ideia central e suas aplicações."),
            "resumo": str(conteudo.get("resumo") or ""),
            "topicos": self._lista(conteudo.get("topicos"), 7),
            "diagrama": diagrama,
            "etapas": etapas,
            "exemplo": str(conteudo.get("exemplo") or ""),
            "formula": str(conteudo.get("formula") or ""),
            "erros_comuns": self._lista(conteudo.get("erros_comuns"), 4),
            "destaque": str(conteudo.get("destaque") or ""),
        }
        self._fase = 0
        self._renderizar()
        self._timer_escrita.start()

    def _avancar_escrita(self):
        self._fase += 1
        self._renderizar()
        if self._fase >= 3:
            self._timer_escrita.stop()

    def _voltar(self):
        self._timer_escrita.stop()
        self.voltar_solicitado.emit()

    def _renderizar(self):
        dados = self._conteudo
        titulo = escape(dados.get("titulo", "Explicação"))
        objetivo = escape(dados.get("objetivo", ""))
        resumo = escape(dados.get("resumo", ""))

        if self._fase >= 1:
            linhas_topicos = "".join(
                '<tr><td class="bullet">•</td>'
                f'<td class="texto">{escape(item)}</td></tr>'
                for item in dados.get("topicos", [])
            )
        else:
            linhas_topicos = '<tr><td class="aguarde">Alfred está escrevendo os conceitos...</td></tr>'

        if self._fase >= 2:
            nos = dados.get("diagrama", [])
            linhas_diagrama = ""
            for indice, item in enumerate(nos):
                linhas_diagrama += f'<div class="no">{escape(item)}</div>'
                if indice < len(nos) - 1:
                    linhas_diagrama += '<div class="seta">↓</div>'
            if not linhas_diagrama:
                linhas_diagrama = '<div class="aguarde">Relação direta entre os conceitos.</div>'
        else:
            linhas_diagrama = '<div class="aguarde">Desenhando a sequência visual...</div>'

        parte_final = ""
        if self._fase >= 3:
            exemplo = escape(dados.get("exemplo", ""))
            formula = escape(dados.get("formula", ""))
            erros = dados.get("erros_comuns", [])
            destaque = escape(dados.get("destaque", ""))

            formula_html = f'<div class="formula">{formula}</div>' if formula else ""
            exemplo_html = (
                '<td class="bloco"><h2>Exemplo explicado</h2>'
                f'<div class="texto">{exemplo}</div>{formula_html}</td>'
                if exemplo or formula else ""
            )
            erros_html = "".join(
                f'<li>{escape(item)}</li>' for item in erros
            )
            erros_bloco = (
                '<td class="bloco"><h2>Erros comuns</h2>'
                f'<ul>{erros_html}</ul></td>' if erros_html else ""
            )
            tabela_final = (
                f'<table class="linha-final"><tr>{exemplo_html}{erros_bloco}</tr></table>'
                if exemplo_html or erros_bloco else ""
            )
            destaque_html = (
                '<div class="destaque"><b>CONCLUSÃO:</b> '
                f'{destaque}</div>' if destaque else ""
            )
            parte_final = tabela_final + destaque_html

        escrevendo = (
            '<div class="escrevendo">▌ Alfred está escrevendo no quadro...</div>'
            if self._fase < 3 else
            '<div class="rodape">Acompanhe a explicação por voz e peça para aprofundar qualquer ponto.</div>'
        )

        html = f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><style>
body {{ margin:0; padding:14px 18px; color:#f3f0dc; background:#10231d;
       font-family:'Segoe Print','Comic Sans MS','Segoe UI',sans-serif; }}
.cabecalho {{ color:#d6d1b9; font:11px Consolas,monospace; letter-spacing:3px; }}
h1 {{ margin:5px 0 2px; color:#fffbea; font-size:29px; text-align:center; font-weight:600; }}
.objetivo {{ margin:4px auto 8px; color:#9ec5b0; font:12px Consolas,monospace; text-align:center; }}
.resumo {{ margin:8px 12px 14px; color:#fffde9; font-size:17px; line-height:1.45;
           text-align:center; border-bottom:1px solid #718376; padding-bottom:12px; }}
.colunas,.linha-final {{ width:100%; border-spacing:10px 5px; }}
.coluna,.bloco {{ width:50%; vertical-align:top; padding:11px 15px;
                  border:1px dashed #839182; }}
h2 {{ margin:0 0 8px; color:#f2d96d; font-size:17px; font-weight:600; text-decoration:underline; }}
.lista {{ width:100%; border-spacing:4px 5px; }}
.bullet {{ width:18px; color:#f2d566; font-size:20px; vertical-align:top; }}
.texto,li {{ color:#f5f2df; font-size:14px; line-height:1.4; }}
.aguarde {{ color:#89a092; font-size:13px; font-style:italic; }}
.diagrama {{ text-align:center; }}
.no {{ margin:2px auto; padding:5px 10px; color:#fff8bf; background:#18372d;
       border:1px solid #d9c861; font-size:13px; }}
.seta {{ color:#efd45f; font-size:17px; line-height:1; }}
.linha-final {{ margin-top:7px; }}
.formula {{ margin-top:8px; padding:7px; color:#8ee9df; border:1px solid #5c9e91;
            font:15px Consolas,monospace; text-align:center; }}
ul {{ margin:2px 0; padding-left:20px; }}
.destaque {{ margin:9px 10px 0; padding:9px 14px; color:#fff4a5;
             border:2px solid #dfcb62; font-size:14px; text-align:center; }}
.escrevendo {{ margin-top:10px; color:#e9d569; font:11px Consolas,monospace; }}
.rodape {{ margin-top:10px; color:#829589; font:10px Consolas,monospace; text-align:right; }}
</style></head><body>
<div class="cabecalho">ALFRED // AULA EM ANDAMENTO</div>
<h1>{titulo}</h1>
<div class="objetivo">OBJETIVO: {objetivo}</div>
<div class="resumo">{resumo}</div>
<table class="colunas"><tr>
  <td class="coluna"><h2>Conceitos essenciais</h2><table class="lista">{linhas_topicos}</table></td>
  <td class="coluna"><h2>Ilustração no quadro</h2><div class="diagrama">{linhas_diagrama}</div></td>
</tr></table>
{parte_final}
{escrevendo}
</body></html>"""
        self.quadro.setHtml(html)
