# ALFRED

Assistente pessoal para Windows com conversa por voz usando Gemini Live, análise de tela e câmera, memória local e um quadro visual para explicações no modo professor.

Durante a conversa, a interface mostra a transcrição ao vivo do que o usuário diz e também da resposta falada pelo Alfred.

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

## Comandos de pesquisa

O Alfred também pode abrir pesquisas no navegador. Exemplos:

- “Alfred, pesquise inteligência artificial no navegador.”
- “Alfred, pesquise fotossíntese e depois dê uma aula detalhada no quadro.”

## Gerar o executável

Com o ambiente virtual ativo e o PyInstaller instalado, execute:

```powershell
python -m pip install pyinstaller
.\build_exe.ps1
```

O pacote será criado em `dist`. No outro computador, coloque um arquivo `.env` com a chave da API Gemini ao lado de `ALFRED.exe`.
