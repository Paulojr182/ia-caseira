import math

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPen, QRadialGradient
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from gemini.live_client_basic import GeminiLiveWorker
from ui.content_panel import ContentPanel


ESTILO_GLOBAL = """
QMainWindow, QWidget#raiz {
    background-color: #050506;
}

QWidget {
    color: #f1f1f3;
    font-family: "Segoe UI";
}

QFrame#painelLateral, QFrame#painelCentral {
    background-color: #08080a;
    border: 1px solid #4a1018;
    border-radius: 20px;
}

QLabel#tituloSistema {
    color: #f7f7f8;
    font-family: "Consolas";
    font-size: 20px;
    font-weight: 700;
}

QLabel#subtituloSistema {
    color: #85858d;
    font-family: "Consolas";
    font-size: 10px;
}

QLabel#tituloAlfred {
    color: #f6eaed;
    font-family: "Consolas";
    font-size: 27px;
    font-weight: 600;
}

QLabel#statusValor {
    color: #8b8589;
    font-family: "Consolas";
    font-size: 10px;
}

QLabel#tituloRegistro {
    color: #8b858d;
    font-family: "Consolas";
    font-size: 10px;
}

QPushButton {
    min-height: 46px;
    padding: 0 16px;
    color: #efeff1;
    background-color: #121216;
    border: 1px solid #651522;
    border-radius: 13px;
    font-size: 11px;
    font-weight: 600;
}

QPushButton:hover {
    color: #ffffff;
    background-color: #1a0d11;
    border-color: #c51e3a;
}

QPushButton:pressed {
    background-color: #310b13;
}

QPushButton#botaoChamada {
    min-height: 54px;
    color: #ffffff;
    background-color: #cb0d2e;
    border: 1px solid #f23b57;
    border-radius: 14px;
    font-size: 12px;
    font-weight: 700;
}

QPushButton#botaoChamada:hover {
    background-color: #e11238;
}

QPushButton#botaoChamada[encerrando="true"] {
    background-color: #4c111b;
    border-color: #8f1d2e;
}

QTextEdit#registro {
    color: #9b969b;
    background-color: #030304;
    border: 1px solid #49101a;
    border-radius: 13px;
    padding: 10px;
    font-family: "Consolas";
    font-size: 9px;
    selection-background-color: #8f1428;
}

QScrollBar:vertical {
    width: 7px;
    background: transparent;
}

QScrollBar::handle:vertical {
    min-height: 24px;
    background: #54101b;
    border-radius: 3px;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
"""


class NeuralCoreWidget(QWidget):
    """Núcleo visual animado que reage ao áudio do Alfred."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._fase = 0.0
        self._nivel_alvo = 0.0
        self._nivel = 0.0
        self._online = False
        self.setMinimumSize(460, 390)

        self._timer = QTimer(self)
        self._timer.setInterval(50)
        self._timer.timeout.connect(self._animar)
        self._timer.start()

    def definir_nivel(self, nivel):
        self._nivel_alvo = max(0.0, min(float(nivel), 1.0))

    def definir_online(self, online):
        self._online = bool(online)
        self.update()

    def _animar(self):
        self._fase = (self._fase + 0.025) % (math.pi * 2)
        self._nivel += (self._nivel_alvo - self._nivel) * 0.18
        self._nivel_alvo *= 0.96
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        largura = self.width()
        altura = self.height()
        centro = QPointF(largura / 2, altura * 0.49)
        pulso = (math.sin(self._fase * 2.0) + 1.0) * 0.5
        energia = self._nivel if self._online else 0.0
        raio = min(largura, altura) * (0.285 + energia * 0.025)

        fundo = QRadialGradient(centro, raio * 2.5)
        fundo.setColorAt(0.0, QColor(70, 0, 13, 115 if self._online else 62))
        fundo.setColorAt(0.42, QColor(32, 0, 7, 60))
        fundo.setColorAt(1.0, QColor(3, 3, 4, 0))
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(fundo))
        painter.drawEllipse(centro, raio * 2.45, raio * 2.05)

        cor_grade = QColor(195, 18, 48, 130 if self._online else 82)
        painter.setBrush(Qt.NoBrush)

        caneta_orbita = QPen(QColor(150, 12, 36, 90), 1.2)
        caneta_orbita.setDashPattern([7, 8])
        painter.setPen(caneta_orbita)
        painter.drawEllipse(
            QRectF(
                centro.x() - raio * 1.48,
                centro.y() - raio * 0.68,
                raio * 2.96,
                raio * 1.36,
            )
        )

        painter.save()
        painter.translate(centro)
        painter.rotate(-13 + math.sin(self._fase) * 2.0)
        painter.drawEllipse(QRectF(-raio * 1.36, -raio * 0.53, raio * 2.72, raio * 1.06))
        painter.restore()

        painter.setPen(QPen(cor_grade, 0.9))
        for indice in range(14):
            angulo = (180.0 / 14.0) * indice + self._fase * 9.0
            painter.save()
            painter.translate(centro)
            painter.rotate(angulo)
            painter.drawEllipse(QRectF(-raio * 0.36, -raio, raio * 0.72, raio * 2.0))
            painter.restore()

        for indice in range(-7, 8):
            proporcao = indice / 8.0
            meia_largura = raio * math.sqrt(max(0.0, 1.0 - proporcao * proporcao))
            y = centro.y() + proporcao * raio
            painter.drawEllipse(
                QRectF(
                    centro.x() - meia_largura,
                    y - raio * 0.09,
                    meia_largura * 2.0,
                    raio * 0.18,
                )
            )

        painter.setPen(QPen(QColor(226, 24, 57, 145), 1.25))
        painter.drawEllipse(QRectF(centro.x() - raio, centro.y() - raio, raio * 2, raio * 2))
        painter.drawEllipse(QRectF(centro.x() - raio, centro.y() - raio * 0.13, raio * 2, raio * 0.26))

        brilho = raio * (0.31 + energia * 0.42 + pulso * 0.025)
        gradiente_nucleo = QRadialGradient(centro, brilho)
        gradiente_nucleo.setColorAt(0.0, QColor(255, 238, 240, 245))
        gradiente_nucleo.setColorAt(0.08, QColor(255, 72, 92, 238))
        gradiente_nucleo.setColorAt(0.35, QColor(207, 10, 45, 115))
        gradiente_nucleo.setColorAt(1.0, QColor(150, 0, 25, 0))
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(gradiente_nucleo))
        painter.drawEllipse(centro, brilho, brilho)

        reflexo = QLinearGradient(0, centro.y() + raio * 1.12, 0, centro.y() + raio * 1.75)
        reflexo.setColorAt(0.0, QColor(180, 0, 30, 60))
        reflexo.setColorAt(1.0, QColor(100, 0, 18, 0))
        painter.setBrush(QBrush(reflexo))
        painter.drawEllipse(
            QRectF(
                centro.x() - raio * 0.85,
                centro.y() + raio * 1.12,
                raio * 1.7,
                raio * 0.38,
            )
        )

        for indice in range(24):
            distancia = (indice - 11.5) * raio * 0.065
            intensidade = int(35 + 75 * (1.0 - abs(indice - 11.5) / 12.0))
            painter.setBrush(QColor(205, 15, 46, intensidade))
            painter.drawEllipse(
                QPointF(centro.x() + distancia, centro.y() + raio * 1.48),
                1.4,
                1.4,
            )


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ALFRED // Neural Desktop Assistant")
        self.setMinimumSize(900, 620)
        self.resize(1160, 780)
        self.live_worker = None
        self.setStyleSheet(ESTILO_GLOBAL)
        self._criar_interface()

    def _criar_interface(self):
        raiz = QWidget()
        raiz.setObjectName("raiz")
        layout_raiz = QHBoxLayout(raiz)
        layout_raiz.setContentsMargins(16, 16, 16, 16)
        layout_raiz.setSpacing(15)

        painel_lateral = QFrame()
        painel_lateral.setObjectName("painelLateral")
        painel_lateral.setFixedWidth(280)
        lateral = QVBoxLayout(painel_lateral)
        lateral.setContentsMargins(18, 22, 18, 18)
        lateral.setSpacing(11)

        titulo = QLabel("SYSTEM CORE")
        titulo.setObjectName("tituloSistema")
        titulo.setAlignment(Qt.AlignCenter)

        subtitulo = QLabel("Controle neural e telemetria local")
        subtitulo.setObjectName("subtituloSistema")
        subtitulo.setAlignment(Qt.AlignCenter)

        self.btn_chamada = QPushButton("INICIAR CONEXÃO")
        self.btn_chamada.setObjectName("botaoChamada")
        self.btn_tela = QPushButton("▣  ANALISAR TELA")
        self.btn_camera = QPushButton("◉  ANALISAR CÂMERA")

        registro_titulo = QLabel("EVENT STREAM")
        registro_titulo.setObjectName("tituloRegistro")
        registro_titulo.setAlignment(Qt.AlignCenter)

        self.log_box = QTextEdit()
        self.log_box.setObjectName("registro")
        self.log_box.setReadOnly(True)
        self.log_box.setPlaceholderText("Aguardando eventos do sistema...")

        lateral.addWidget(titulo)
        lateral.addWidget(subtitulo)
        lateral.addSpacing(10)
        lateral.addWidget(self.btn_chamada)
        lateral.addWidget(self.btn_tela)
        lateral.addWidget(self.btn_camera)
        lateral.addSpacing(7)
        lateral.addWidget(registro_titulo)
        lateral.addWidget(self.log_box, 1)

        painel_central = QFrame()
        painel_central.setObjectName("painelCentral")
        central = QVBoxLayout(painel_central)
        central.setContentsMargins(18, 46, 18, 24)
        central.setSpacing(7)

        titulo_alfred = QLabel("A L F R E D")
        titulo_alfred.setObjectName("tituloAlfred")
        titulo_alfred.setAlignment(Qt.AlignCenter)

        self.status_valor = QLabel("○  OFFLINE")
        self.status_valor.setObjectName("statusValor")
        self.status_valor.setAlignment(Qt.AlignCenter)

        self.nucleo = NeuralCoreWidget()
        self.painel_conteudo = ContentPanel()
        self.painel_conteudo.voltar_solicitado.connect(
            lambda: self.stack.setCurrentWidget(self.nucleo)
        )

        self.stack = QStackedWidget()
        self.stack.addWidget(self.nucleo)
        self.stack.addWidget(self.painel_conteudo)
        self.stack.setCurrentWidget(self.nucleo)

        central.addWidget(titulo_alfred)
        central.addWidget(self.status_valor)
        central.addWidget(self.stack, 1)

        layout_raiz.addWidget(painel_lateral)
        layout_raiz.addWidget(painel_central, 1)
        self.setCentralWidget(raiz)

        self.btn_chamada.clicked.connect(self.alternar_chamada)
        self.btn_tela.clicked.connect(self.analisar_tela)
        self.btn_camera.clicked.connect(self.analisar_camera)

    def escrever_log(self, texto):
        self.log_box.append(f"> {texto}")

    def definir_status(self, texto):
        texto = str(texto)
        texto_maiusculo = texto.upper()
        offline = texto_maiusculo in {"OFFLINE", "ERRO"}
        transicao = "CONECTANDO" in texto_maiusculo or "ENCERRANDO" in texto_maiusculo
        conectado = "CONECTADO" in texto_maiusculo or (
            self.live_worker is not None
            and not transicao
            and not offline
        )

        if offline:
            exibido = f"○  {texto_maiusculo}"
            cor = "#8b8589"
        elif conectado:
            exibido = "●  ONLINE"
            cor = "#e01b3c"
        else:
            exibido = "◌  DESCONECTANDO" if "ENCERRANDO" in texto_maiusculo else "◌  CONECTANDO"
            cor = "#bd1732"

        self.status_valor.setText(exibido)
        self.status_valor.setStyleSheet(f"color: {cor};")
        self.nucleo.definir_online(conectado)

    def alternar_chamada(self):
        if self.live_worker is None:
            self.iniciar_chamada()
        else:
            self.encerrar_chamada()

    def iniciar_chamada(self):
        self.btn_chamada.setText("ENCERRAR CONEXÃO")
        self.btn_chamada.setProperty("encerrando", True)
        self.btn_chamada.style().unpolish(self.btn_chamada)
        self.btn_chamada.style().polish(self.btn_chamada)
        self.definir_status("CONECTANDO")
        self.escrever_log("Iniciando conexão...")

        self.live_worker = GeminiLiveWorker()
        self.live_worker.status_recebido.connect(self.atualizar_status)
        self.live_worker.erro_recebido.connect(self.mostrar_erro)
        self.live_worker.chamada_encerrada.connect(self.chamada_finalizada)
        self.live_worker.solicitou_encerramento.connect(self.encerrar_chamada)
        self.live_worker.nivel_audio.connect(self.nucleo.definir_nivel)
        self.live_worker.conteudo_visual_recebido.connect(
            self.mostrar_conteudo_visual
        )
        self.live_worker.start()

    def encerrar_chamada(self):
        if self.live_worker:
            self.definir_status("ENCERRANDO")
            self.escrever_log("Encerrando conexão...")
            self.live_worker.parar()

    def atualizar_status(self, texto):
        self.definir_status(texto)
        self.escrever_log(texto)

    def mostrar_erro(self, erro):
        self.definir_status("ERRO")
        self.escrever_log(f"Erro: {erro}")

    def chamada_finalizada(self):
        self.live_worker = None
        self.btn_chamada.setText("INICIAR CONEXÃO")
        self.btn_chamada.setProperty("encerrando", False)
        self.btn_chamada.style().unpolish(self.btn_chamada)
        self.btn_chamada.style().polish(self.btn_chamada)
        self.nucleo.definir_nivel(0.0)
        self.definir_status("OFFLINE")
        self.escrever_log("Conexão encerrada.")

    def analisar_tela(self):
        if not self.live_worker:
            self.escrever_log("Inicie a conexão antes de analisar a tela.")
            return
        self.escrever_log("Solicitando análise da tela...")
        self.live_worker.solicitar_analise_tela()

    def analisar_camera(self):
        if not self.live_worker:
            self.escrever_log("Inicie a conexão antes de analisar a câmera.")
            return
        self.escrever_log("Solicitando análise da câmera...")
        self.live_worker.solicitar_analise_camera()

    def mostrar_conteudo_visual(self, conteudo):
        self.painel_conteudo.mostrar_conteudo(conteudo)
        self.stack.setCurrentWidget(self.painel_conteudo)
        self.escrever_log("Painel educacional atualizado.")

    def closeEvent(self, event):
        if self.live_worker:
            self.live_worker.parar()
            self.live_worker.wait(3000)
        event.accept()
