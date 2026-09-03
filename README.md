# ALFRED — Professor particular por voz

Aplicativo Windows com interface PySide6, voz, quadro didático, visão, memória local e inteligência principal baseada na API oficial da OpenAI.

## Recursos

- Microfone com detecção local de início e fim da fala.
- Transcrição por `gpt-4o-mini-transcribe`.
- Respostas em streaming pela Responses API.
- Voz por `gpt-4o-mini-tts`, dividida em blocos de frases.
- Interrupção da fala por detecção local de voz (barge-in experimental).
- Roteamento econômico entre GPT-5.6 Luna, Terra e Sol.
- Quadro local com conceitos, diagramas, fórmulas e exemplos.
- Pesquisa atual pela ferramenta oficial `web_search` da Responses API.
- Abertura segura de aplicativos e pesquisas no navegador.
- Análise sob demanda de tela e câmera.
- Memória e progresso de estudo persistidos localmente.
- Busca de trechos em PDF, TXT, MD e DOCX sem enviar o documento inteiro.

O cliente antigo do Gemini permanece em `gemini/` apenas para facilitar rollback, mas não é importado pelo aplicativo principal.

## Instalação

Requer Python 3.11 ou mais recente.

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Copie `.env.example` para `.env` e coloque uma chave nova da API OpenAI:

```env
OPENAI_API_KEY=sua_chave_nova
OPENAI_MODEL_MODE=auto
```

Nunca publique o `.env`. Uma chave colada em conversa, captura de tela ou repositório deve ser revogada.

## Executar

```powershell
python main_basic.py
```

Clique em **INICIAR CONEXÃO** e fale normalmente. A transcrição do usuário e do Alfred aparece na parte inferior.

## Professor e modelos

O modo professor é automático para pedidos educacionais. O botão **MODO PROFESSOR** abre diretamente o quadro.

- “Alfred, use o modo econômico.” — prioriza Luna.
- “Alfred, use o modo normal.” — Terra é o professor padrão.
- “Alfred, use o modo avançado.” — permite Sol em tarefas complexas.
- “Alfred, use Sol nesta pergunta.” — força Sol somente na próxima pergunta.

O modelo usado aparece discretamente na interface. Falhas técnicas nunca promovem automaticamente uma chamada para Sol.

## Materiais de estudo

Coloque materiais nestas pastas:

```text
study/materials/   PDF, TXT, MD e DOCX
study/exams/       provas e simulados anteriores
study/notes/       anotações criadas pelo Alfred
```

Quando solicitado, o Alfred seleciona apenas trechos relevantes para reduzir tokens. PDFs apenas com imagem precisam de OCR e ainda não são indexados.

## Memória e progresso

- `memory/memory.json`: fatos que o usuário pediu explicitamente para lembrar.
- `memory/teacher_progress.json`: resumo de matérias, dificuldades e próximo passo.
- `logs/api_usage.jsonl`: modelo e tokens por chamada, sem credenciais.

Esses arquivos são privados, ignorados pelo Git e ficam ao lado do executável na versão compilada.

## Pesquisa na internet

Diga “pesquise”, “mais recente”, “informação atual”, “edital” ou expressão equivalente. O roteador habilita `web_search` somente quando necessário. Para apenas abrir resultados no navegador, peça explicitamente para abrir a pesquisa.

## Build para Windows

```powershell
python -m pip install pyinstaller
.\build_exe.ps1
```

O resultado fica em `dist/ALFRED.exe`. Coloque `.env`, materiais e memórias ao lado do executável conforme `dist/LEIA-ME.txt`.

## Testes

```powershell
python -m unittest discover -s tests -v
```

## Solução de problemas

- **Erro de autenticação:** confira `OPENAI_API_KEY` e gere uma chave nova se ela foi exposta.
- **Sem voz ou microfone:** confira o dispositivo padrão e as permissões de microfone do Windows.
- **Interrupção dispara com o alto-falante:** reduza o volume, use fones ou aproxime-se do microfone; o cancelamento de eco é heurístico.
- **PDF sem resultados:** o arquivo pode conter somente imagens e exigir OCR.
- **Limite da API:** confira créditos, orçamento e limites no painel da OpenAI.
