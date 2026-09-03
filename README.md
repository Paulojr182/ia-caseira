# ALFRED

Assistente pessoal para Windows com conversa por voz usando Gemini Live, análise de tela e câmera, memória local e um quadro visual para explicações no modo professor.

## Preparação

1. Instale Python 3.11 ou mais recente.
2. Crie e ative um ambiente virtual:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

3. Instale as dependências:

```powershell
python -m pip install -r requirements.txt
```

4. Copie `.env.example` para `.env` e informe sua chave do Gemini:

```env
GEMINI_API_KEY=sua_chave
```

## Executar

```powershell
python main_basic.py
```

O arquivo `.env`, o ambiente virtual e as memórias pessoais ficam somente no computador do usuário e não são enviados ao repositório.
