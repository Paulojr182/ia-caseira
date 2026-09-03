import os
import sys
from pathlib import Path

from dotenv import load_dotenv


# No código-fonte, lê o .env da raiz do projeto. No executável, lê o arquivo
# colocado ao lado de ALFRED.exe para que a chave nunca seja embutida no app.
if getattr(sys, "frozen", False):
    PASTA_APLICATIVO = Path(sys.executable).resolve().parent
else:
    PASTA_APLICATIVO = Path(__file__).resolve().parents[1]

load_dotenv(PASTA_APLICATIVO / ".env")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Provedor principal OpenAI. A chave deve existir somente no arquivo .env.
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL_LUNA = os.getenv("OPENAI_MODEL_LUNA", "gpt-5.6-luna")
OPENAI_MODEL_TERRA = os.getenv("OPENAI_MODEL_TERRA", "gpt-5.6-terra")
OPENAI_MODEL_SOL = os.getenv("OPENAI_MODEL_SOL", "gpt-5.6-sol")
OPENAI_MODEL_MODE = os.getenv("OPENAI_MODEL_MODE", "auto").strip().lower()
if OPENAI_MODEL_MODE not in {"auto", "luna", "terra", "sol"}:
    OPENAI_MODEL_MODE = "auto"

OPENAI_STT_MODEL = os.getenv("OPENAI_STT_MODEL", "gpt-4o-mini-transcribe")
OPENAI_TTS_MODEL = os.getenv("OPENAI_TTS_MODEL", "gpt-4o-mini-tts")
OPENAI_TTS_VOICE = os.getenv("OPENAI_TTS_VOICE", "cedar")

# Modelo usado pelo ALFRED
GEMINI_LIVE_MODEL = "gemini-3.1-flash-live-preview"

# ============================================================
# MODELOS DISPONÍVEIS PARA TESTE
# ============================================================
#MODELO = "gemini-2.5-flash-native-audio-preview-12-2025"
#MODELO = “gemini-2.5-flash-native-audio-preview-09-2025”
#MODELO = "gemini-3.1-flash-live-preview"


# Voz usada pelo ALFRED
GEMINI_VOICE = "Charon"

# ============================================================
# VOZES DISPONÍVEIS PARA TESTE
# ============================================================
#
# Zephyr   - brilhante
# Puck     - animada
# Charon   - informativa
# Kore     - feminia e firme
# Fenrir   - empolgada
# Leda     - jovem
# Orus     - firme
# Aoede    - leve
# Callirrhoe - descontraída
# Autonoe  - brilhante
# Enceladus - suave/sussurrante
# Iapetus  - clara
# Umbriel  - descontraída
# Algieba  - suave
# Despina  - suave
# Erinome  - clara
# Algenib  - rouca
# Rasalgethi - informativa
# Laomedeia - animada
# Achernar - suave
# Alnilam  - firme
# Schedar  - equilibrada
# Gacrux   - madura
# Pulcherrima - direta
# Achird   - amigável
# Zubenelgenubi - casual
# Vindemiatrix - feminina gentil
# Sadachbia - animada
# Sadaltager - experiente
# Sulafat  - calorosa
