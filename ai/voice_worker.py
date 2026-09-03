"""Worker de voz econômico: VAD local, STT, Responses streaming e TTS."""

from array import array
from collections import deque
from enum import Enum
import io
import queue
import re
import threading
import time
import wave

from openai import OpenAI
from PySide6.QtCore import QThread, Signal
import sounddevice as sd

from ai.openai_client import OpenAIProfessorClient
from core.config import OPENAI_API_KEY, OPENAI_TTS_MODEL, OPENAI_TTS_VOICE
from vision.camera_capture import capturar_camera_bytes
from vision.screen_capture import capturar_tela_bytes


INPUT_RATE = 16000
OUTPUT_RATE = 24000
CHANNELS = 1
BLOCK = 320
SILENCE_SECONDS = 0.8
MAX_UTTERANCE_SECONDS = 25


class VoiceState(str, Enum):
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    THINKING = "THINKING"
    SPEAKING = "SPEAKING"
    INTERRUPTED = "INTERRUPTED"


class OpenAIVoiceWorker(QThread):
    status_recebido = Signal(str)
    erro_recebido = Signal(str)
    chamada_encerrada = Signal()
    nivel_audio = Signal(float)
    conteudo_visual_recebido = Signal(dict)
    transcricao_recebida = Signal(str, str, bool, bool)
    solicitou_encerramento = Signal()
    modelo_alterado = Signal(str)

    def __init__(self):
        super().__init__()
        self.ativo = True
        self.state = VoiceState.IDLE
        self._tasks: queue.Queue = queue.Queue(maxsize=4)
        self._tts_queue: queue.Queue = queue.Queue()
        self._cancel = threading.Event()
        self._busy = threading.Event()
        self._speaking = threading.Event()
        self._generation = 0
        self._output_rms = 0.0
        self._microphone_thread: threading.Thread | None = None
        self._tts_thread: threading.Thread | None = None
        self._provider: OpenAIProfessorClient | None = None

    def run(self):
        try:
            if not OPENAI_API_KEY:
                raise ValueError(
                    "OPENAI_API_KEY não encontrada no arquivo .env. "
                    "Use uma chave nova; não reutilize uma chave publicada."
                )
            self._provider = OpenAIProfessorClient(
                on_board=self.conteudo_visual_recebido.emit,
                on_status=self.status_recebido.emit,
                on_model=self.modelo_alterado.emit,
            )
            self._microphone_thread = threading.Thread(
                target=self._microphone_loop, name="alfred-microphone", daemon=True
            )
            self._tts_thread = threading.Thread(
                target=self._tts_loop, name="alfred-tts", daemon=True
            )
            self._microphone_thread.start()
            self._tts_thread.start()
            self._set_state(VoiceState.LISTENING)
            self.status_recebido.emit("Conectado à OpenAI. Pode falar.")

            self._generation += 1
            self.transcricao_recebida.emit(
                "alfred", "Conectado à OpenAI. Pode falar.", True, True
            )
            self._busy.set()
            self._queue_speech("Conectado à OpenAI. Pode falar.", self._generation)
            self._tts_queue.join()
            self._busy.clear()

            while self.ativo:
                try:
                    task = self._tasks.get(timeout=0.2)
                except queue.Empty:
                    continue
                if task is None:
                    break
                try:
                    self._process_task(task)
                except Exception as error:
                    self.erro_recebido.emit(self._friendly_error(error))
                    self._set_state(VoiceState.LISTENING)
                finally:
                    self._tasks.task_done()
        except Exception as error:
            self.erro_recebido.emit(self._friendly_error(error))
        finally:
            self.ativo = False
            self._cancel.set()
            self._clear_tts_queue()
            self._tts_queue.put(None)
            self.nivel_audio.emit(0.0)
            self.chamada_encerrada.emit()

    def _process_task(self, task: dict):
        self._generation += 1
        generation = self._generation
        self._cancel.clear()
        self._busy.set()
        try:
            kind = task.get("kind")
            image = task.get("image")
            if kind == "audio":
                self._set_state(VoiceState.THINKING)
                self.status_recebido.emit("Transcrevendo sua fala...")
                text = self._provider.transcribe(self._pcm_to_wav(task["pcm"]))
            elif kind == "capture_screen":
                self.status_recebido.emit("Capturando tela...")
                image = capturar_tela_bytes()
                text = "Analise a captura da minha tela e explique o que está visível."
            elif kind == "capture_camera":
                self.status_recebido.emit("Capturando câmera...")
                image = capturar_camera_bytes()
                text = "Analise esta imagem da câmera e explique o que está visível."
            else:
                text = task.get("text", "Analise esta imagem e explique o que está visível.")

            text = str(text).strip()
            if not text:
                return
            self.transcricao_recebida.emit("usuario", text, True, True)

            normalized = re.sub(r"[^a-záàâãéêíóôõúç ]", "", text.lower()).strip()
            if normalized in {"pare", "alfred pare", "professor pare"}:
                self._interrupt()
                self.status_recebido.emit("Interrompido. Estou ouvindo.")
                return
            if any(term in normalized for term in ("encerrar conexão", "encerrar chamada", "finalizar chamada")):
                self._queue_speech("Conexão encerrada.", generation)
                self._tts_queue.join()
                self.solicitou_encerramento.emit()
                return

            mode_answer = self._provider.change_mode(text)
            if mode_answer:
                self.modelo_alterado.emit(self._provider.router.mode.upper())
                self.transcricao_recebida.emit("alfred", mode_answer, True, True)
                self._queue_speech(mode_answer, generation)
                self._tts_queue.join()
                return

            self._set_state(VoiceState.THINKING)
            sentence_buffer = ""

            def on_delta(delta: str):
                nonlocal sentence_buffer
                self.transcricao_recebida.emit("alfred", delta, False, False)
                sentence_buffer += delta
                sentence_buffer = self._flush_sentences(
                    sentence_buffer, generation, force=False
                )

            result = self._provider.respond(
                user_text=text,
                on_delta=on_delta,
                cancelled=self._cancel.is_set,
                image_bytes=image,
            )
            if result is None:
                return
            self._flush_sentences(sentence_buffer, generation, force=True)
            self.transcricao_recebida.emit("alfred", "", True, False)
            self._tts_queue.join()
        finally:
            self._busy.clear()
            if self.ativo:
                self._set_state(VoiceState.LISTENING)

    def _flush_sentences(self, buffer: str, generation: int, force: bool) -> str:
        while True:
            matches = list(re.finditer(r"[.!?](?:\s+|$)", buffer))
            if not matches:
                break
            cut = matches[0].end()
            if cut < 80 and len(matches) > 1:
                cut = matches[1].end()
            elif cut < 80 and len(buffer) < 260 and not force:
                break
            sentence = buffer[:cut].strip()
            buffer = buffer[cut:]
            if sentence:
                self._queue_speech(sentence, generation)
        if force and buffer.strip():
            self._queue_speech(buffer.strip(), generation)
            return ""
        return buffer

    def _queue_speech(self, text: str, generation: int):
        if text and self.ativo and not self._cancel.is_set():
            self._tts_queue.put((generation, text[:1800]))

    def _tts_loop(self):
        client = OpenAI(api_key=OPENAI_API_KEY, timeout=45.0)
        while self.ativo:
            item = self._tts_queue.get()
            if item is None:
                self._tts_queue.task_done()
                break
            generation, text = item
            try:
                if generation != self._generation or self._cancel.is_set():
                    continue
                self._speaking.set()
                self._set_state(VoiceState.SPEAKING)
                with client.audio.speech.with_streaming_response.create(
                    model=OPENAI_TTS_MODEL,
                    voice=OPENAI_TTS_VOICE,
                    input=text,
                    instructions="Fale em português brasileiro como um professor claro e paciente.",
                    response_format="pcm",
                ) as response:
                    with sd.RawOutputStream(
                        samplerate=OUTPUT_RATE, dtype="int16", channels=CHANNELS
                    ) as output:
                        for chunk in response.iter_bytes(chunk_size=4096):
                            if (
                                not self.ativo
                                or self._cancel.is_set()
                                or generation != self._generation
                            ):
                                break
                            if len(chunk) % 2:
                                chunk = chunk[:-1]
                            self._output_rms = self._rms(chunk)
                            self.nivel_audio.emit(min(1.0, self._output_rms / 9000.0))
                            if chunk:
                                output.write(chunk)
            except Exception as error:
                self.erro_recebido.emit(f"Erro na voz: {self._friendly_error(error)}")
            finally:
                self._output_rms = 0.0
                self._speaking.clear()
                self.nivel_audio.emit(0.0)
                self._tts_queue.task_done()

    def _microphone_loop(self):
        pre_roll: deque[bytes] = deque(maxlen=10)
        recording: list[bytes] = []
        speech_blocks = 0
        silence_blocks = 0
        noise_floor = 250.0
        max_blocks = int(MAX_UTTERANCE_SECONDS * INPUT_RATE / BLOCK)
        silence_limit = int(SILENCE_SECONDS * INPUT_RATE / BLOCK)

        try:
            with sd.RawInputStream(
                samplerate=INPUT_RATE,
                blocksize=BLOCK,
                dtype="int16",
                channels=CHANNELS,
            ) as stream:
                while self.ativo:
                    data, _ = stream.read(BLOCK)
                    chunk = bytes(data)
                    level = self._rms(chunk)
                    self.nivel_audio.emit(min(1.0, level / 7000.0))
                    normal_threshold = max(550.0, noise_floor * 3.2)

                    if not recording and not self._busy.is_set() and level < normal_threshold:
                        noise_floor = noise_floor * 0.98 + level * 0.02
                    pre_roll.append(chunk)

                    if not recording:
                        threshold = normal_threshold
                        if self._speaking.is_set():
                            threshold = max(
                                2200.0,
                                normal_threshold * 3.0,
                                self._output_rms * 0.35,
                            )
                        if level >= threshold:
                            speech_blocks += 1
                        else:
                            speech_blocks = 0

                        required = 4 if self._busy.is_set() else 2
                        if speech_blocks < required:
                            continue
                        if self._busy.is_set():
                            self._interrupt()
                        recording = list(pre_roll)
                        silence_blocks = 0
                        speech_blocks = 0
                        continue

                    recording.append(chunk)
                    if level < normal_threshold:
                        silence_blocks += 1
                    else:
                        silence_blocks = 0
                    if silence_blocks >= silence_limit or len(recording) >= max_blocks:
                        pcm = b"".join(recording[:-silence_limit] or recording)
                        recording = []
                        pre_roll.clear()
                        if len(pcm) >= int(INPUT_RATE * 0.3) * 2:
                            self._put_task({"kind": "audio", "pcm": pcm})
        except Exception as error:
            if self.ativo:
                self.erro_recebido.emit(f"Erro no microfone: {self._friendly_error(error)}")

    def _interrupt(self):
        self._set_state(VoiceState.INTERRUPTED)
        self._cancel.set()
        self._generation += 1
        self._clear_tts_queue()
        self.status_recebido.emit("Fala interrompida. Ouvindo você...")

    def _clear_tts_queue(self):
        while True:
            try:
                item = self._tts_queue.get_nowait()
            except queue.Empty:
                break
            if item is not None:
                self._tts_queue.task_done()

    def _put_task(self, task: dict):
        try:
            self._tasks.put_nowait(task)
        except queue.Full:
            pass

    @staticmethod
    def _pcm_to_wav(pcm: bytes) -> bytes:
        output = io.BytesIO()
        with wave.open(output, "wb") as wav:
            wav.setnchannels(CHANNELS)
            wav.setsampwidth(2)
            wav.setframerate(INPUT_RATE)
            wav.writeframes(pcm)
        return output.getvalue()

    @staticmethod
    def _rms(data: bytes) -> float:
        if not data:
            return 0.0
        samples = array("h")
        samples.frombytes(data)
        if not samples:
            return 0.0
        return (sum(sample * sample for sample in samples) / len(samples)) ** 0.5

    def _set_state(self, state: VoiceState):
        self.state = state

    @staticmethod
    def _friendly_error(error: Exception) -> str:
        text = str(error)
        lowered = text.lower()
        if "401" in text or "api key" in lowered or "authentication" in lowered:
            return "Não consegui autenticar na OpenAI. Verifique OPENAI_API_KEY."
        if "timeout" in lowered or "connection" in lowered:
            return "Não consegui conectar à OpenAI neste momento."
        if "429" in text or "rate limit" in lowered or "quota" in lowered:
            return "O limite de uso da API foi atingido. Verifique seus créditos e limites."
        return text

    def solicitar_analise_tela(self):
        self._put_task({"kind": "capture_screen"})

    def solicitar_analise_camera(self):
        self._put_task({"kind": "capture_camera"})

    def parar(self):
        self.ativo = False
        self._cancel.set()
        self._clear_tts_queue()
        self._put_task(None)
