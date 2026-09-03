# asyncio permite executar várias tarefas assíncronas ao mesmo tempo.
# Neste arquivo, ele coordena microfone, recebimento de áudio,
# reprodução da resposta e chamadas de funções do Gemini Live.
import asyncio
# time é utilizado para controlar intervalos e medir o tempo
# entre chamadas de funções visuais.
import time

# array converte os bytes de áudio em amostras numéricas.
# Isso permite calcular o nível de volume da voz do ALFRED.
from array import array

# sounddevice captura o áudio do microfone e reproduz
# o áudio recebido do Gemini.
import sounddevice as sd

# QThread executa o cliente Gemini Live em uma thread separada,
# evitando que a interface PySide6 fique travada.
# Signal permite enviar status, erros e níveis de áudio para a interface.
from PySide6.QtCore import QThread, Signal
# genai é o cliente oficial usado para se conectar à API do Gemini.
from google import genai
# types contém as estruturas usadas pela API,
# como configurações, ferramentas, conteúdos, partes e respostas.
from google.genai import types

# Importa as configurações centrais do projeto,
# incluindo chave da API, modelo Live e voz escolhida.
from core.config import (
    GEMINI_API_KEY,
    GEMINI_LIVE_MODEL,
    GEMINI_VOICE,
)
from core.local_actions import abrir_aplicativo, pesquisar_no_navegador

# Função responsável por capturar a tela e retornar a imagem em bytes.
from vision.screen_capture import capturar_tela_bytes
# Função responsável por capturar a webcam e retornar a imagem em bytes.
from vision.camera_capture import capturar_camera_bytes

# Importa as funções da memória persistente do ALFRED.
from memory.memory_manager import (
    salvar_memoria,
    listar_memorias,
    esquecer_memoria,
    contexto_memorias,
)


# Taxa de amostragem do microfone em 16 kHz.
TAXA_ENTRADA = 16000
# Taxa de amostragem do áudio de resposta em 24 kHz.
TAXA_SAIDA = 24000
# O áudio é mono, portanto utiliza apenas um canal.
CANAIS = 1
# Quantidade de amostras processadas por bloco de áudio.
BLOCO = 1024

# Tempo de segurança, em segundos, antes de reabrir o microfone
# depois que o assistente termina de falar.
# Um valor maior ajuda computadores com retorno de áudio ou drivers lentos.
ATRASO_REABRIR_MICROFONE = 0.8

# Limite de blocos aguardando envio. Evita acúmulo excessivo
# caso o computador ou a conexão fiquem temporariamente lentos.
LIMITE_FILA_MICROFONE = 50

# Intervalo mínimo, em segundos, entre chamadas visuais repetidas.
# Isso evita capturas duplicadas para o mesmo pedido.
COOLDOWN_FUNCAO_VISUAL = 8.0


# Classe principal responsável pela sessão em tempo real com o Gemini.
# Como herda de QThread, roda separadamente da interface gráfica.
class GeminiLiveWorker(QThread):

    # Sinal usado para enviar mensagens de status para a interface.
    status_recebido = Signal(str)
    # Sinal usado para enviar mensagens de erro para a interface.
    erro_recebido = Signal(str)
    # Sinal emitido quando a sessão termina.
    chamada_encerrada = Signal()

    # Sinal utilizado para animar a interface de acordo com o volume da voz.
    nivel_audio = Signal(float)

    # Envia conteúdo educacional estruturado para o painel visual.
    conteudo_visual_recebido = Signal(dict)

    # Envia legendas em tempo real: papel, texto, finalizada e substituição.
    transcricao_recebida = Signal(str, str, bool, bool)

    # Solicita que a interface encerre a chamada
    # usando o mesmo método acionado pelo botão.
    # Sinal emitido quando o usuário pede para encerrar a chamada por voz.
    solicitou_encerramento = Signal()

    # Inicializa os estados internos do worker.
    def __init__(self):
        super().__init__()

        # Controla se a sessão continua em execução.
        self.ativo = True
        # Guardará o loop assíncrono criado pela thread.
        self.loop = None
        # Guardará a sessão ativa do Gemini Live.
        self.sessao = None

        # Indica quando o ALFRED está reproduzindo áudio.
        # Enquanto isso, o microfone é ignorado para evitar eco.
        self.alfred_falando = False
        # Referência para a tarefa que libera o microfone após a fala.
        self.tarefa_liberar_microfone = None
        # Referência para a tarefa que encerra a chamada após a despedida.
        self.tarefa_encerramento = None

        # Impede duas análises visuais simultâneas.
        self.executando_funcao_visual = False
        self.ultima_funcao_visual = None
        self.tempo_ultima_funcao_visual = 0.0

    # Método chamado automaticamente quando a thread é iniciada.
    def run(self):
        try:
            # Cria e executa o ambiente assíncrono desta thread.
            asyncio.run(
                self.executar()
            )

        except Exception as erro:
            self.erro_recebido.emit(
                str(erro)
            )

        # Este bloco sempre é executado, mesmo se ocorrer erro.
        finally:
            self.nivel_audio.emit(
                0.0
            )

            self.chamada_encerrada.emit()

    # Configura o Gemini Live, cria as filas de áudio
    # e mantém a sessão funcionando enquanto o worker estiver ativo.
    async def executar(self):
        # Impede a conexão quando a chave da API não foi configurada.
        if not GEMINI_API_KEY:
            raise ValueError(
                "GEMINI_API_KEY não encontrada no arquivo .env"
            )

        # Obtém o loop assíncrono atual para permitir chamadas
        # futuras vindas dos botões da interface.
        self.loop = asyncio.get_running_loop()

        # Cria o cliente autenticado do Gemini.
        client = genai.Client(
            api_key=GEMINI_API_KEY
        )

        # Lista de ferramentas que o modelo pode chamar por voz.
        # Cada FunctionDeclaration descreve quando e como usar uma função.
        tools = [
            types.Tool(
                function_declarations=[
                    types.FunctionDeclaration(
                        name="analisar_tela",
                        description=(
                            "Use esta função somente quando o usuário pedir "
                            "explicitamente para analisar, ver, observar ou "
                            "explicar a tela do computador. Não use "
                            "espontaneamente e não repita para o mesmo pedido."
                        ),
                    ),

                    types.FunctionDeclaration(
                        name="analisar_camera",
                        description=(
                            "Use esta função somente quando o usuário pedir "
                            "explicitamente para analisar, ver, observar ou "
                            "explicar a webcam ou câmera. Não use "
                            "espontaneamente e não repita para o mesmo pedido."
                        ),
                    ),

                    types.FunctionDeclaration(
                        name="salvar_memoria",
                        description=(
                            "Salva uma informação curta e útil na memória "
                            "persistente entre sessões. Use somente quando "
                            "o usuário pedir claramente para lembrar, guardar "
                            "ou memorizar algo. Não salve conversas "
                            "automaticamente e não salve suposições."
                        ),
                        parameters=types.Schema(
                            type="OBJECT",
                            properties={
                                "texto": types.Schema(
                                    type="STRING",
                                    description=(
                                        "Informação curta e objetiva que "
                                        "o usuário pediu para lembrar."
                                    ),
                                )
                            },
                            required=["texto"],
                        ),
                    ),

                    types.FunctionDeclaration(
                        name="listar_memorias",
                        description=(
                            "Lista as memórias persistentes salvas. Use quando "
                            "o usuário perguntar o que o ALFRED lembra ou pedir "
                            "para mostrar as memórias."
                        ),
                    ),

                    types.FunctionDeclaration(
                        name="esquecer_memoria",
                        description=(
                            "Remove uma memória persistente específica. Use "
                            "somente quando o usuário pedir claramente para "
                            "esquecer uma informação. Pode usar o número da "
                            "memória ou um trecho específico do texto."
                        ),
                        parameters=types.Schema(
                            type="OBJECT",
                            properties={
                                "referencia": types.Schema(
                                    type="STRING",
                                    description=(
                                        "Número da memória ou trecho específico "
                                        "da informação que deve ser esquecida."
                                    ),
                                )
                            },
                            required=["referencia"],
                        ),
                    ),

                    types.FunctionDeclaration(
                        name="abrir_aplicativo",
                        description=(
                            "Abre um aplicativo local permitido no Windows. "
                            "Use somente quando o usuário pedir explicitamente "
                            "para abrir um aplicativo. Aplicativos permitidos: "
                            "calculadora, bloco de notas, explorador de arquivos, "
                            "paint, configurações e navegador."
                        ),
                        parameters=types.Schema(
                            type="OBJECT",
                            properties={
                                "nome": types.Schema(
                                    type="STRING",
                                    description="Nome do aplicativo que deve ser aberto.",
                                )
                            },
                            required=["nome"],
                        ),
                    ),

                    types.FunctionDeclaration(
                        name="pesquisar_no_navegador",
                        description=(
                            "Abre o navegador padrão e pesquisa no Google o tema informado. "
                            "Use quando o usuário pedir para pesquisar, procurar ou buscar "
                            "algo na internet. Se ele também pedir uma explicação ou aula, "
                            "marque explicacao_detalhada como true."
                        ),
                        parameters=types.Schema(
                            type="OBJECT",
                            properties={
                                "tema": types.Schema(
                                    type="STRING",
                                    description="Consulta que será pesquisada no navegador.",
                                ),
                                "explicacao_detalhada": types.Schema(
                                    type="BOOLEAN",
                                    description=(
                                        "True quando, além de pesquisar, o usuário quiser "
                                        "uma aula detalhada no quadro."
                                    ),
                                ),
                            },
                            required=["tema", "explicacao_detalhada"],
                        ),
                    ),

                    types.FunctionDeclaration(
                        name="mostrar_conteudo_visual",
                        description=(
                            "Monta uma explicação em um quadro de sala de aula na interface. "
                            "É obrigatório usar antes de toda explicação educacional, aula, "
                            "revisão ou resposta a uma dúvida sobre matéria. Também atualize "
                            "o quadro nas perguntas de continuação. Monte uma aula completa, "
                            "com conceitos, diagrama, exemplo e conclusão."
                        ),
                        parameters=types.Schema(
                            type="OBJECT",
                            properties={
                                "titulo": types.Schema(
                                    type="STRING",
                                    description="Título curto da explicação.",
                                ),
                                "objetivo": types.Schema(
                                    type="STRING",
                                    description="O que o aluno compreenderá ao final da aula.",
                                ),
                                "resumo": types.Schema(
                                    type="STRING",
                                    description=(
                                        "Definição introdutória clara em duas ou três frases, "
                                        "sem ser superficial."
                                    ),
                                ),
                                "topicos": types.Schema(
                                    type="ARRAY",
                                    description=(
                                        "De quatro a sete conceitos essenciais em frases "
                                        "completas, claras e informativas."
                                    ),
                                    items=types.Schema(type="STRING"),
                                ),
                                "diagrama": types.Schema(
                                    type="ARRAY",
                                    description=(
                                        "De três a seis rótulos curtos que formam um diagrama "
                                        "visual em sequência, da causa ao resultado."
                                    ),
                                    items=types.Schema(type="STRING"),
                                ),
                                "etapas": types.Schema(
                                    type="ARRAY",
                                    description="Até seis etapas ordenadas do processo, quando houver.",
                                    items=types.Schema(type="STRING"),
                                ),
                                "exemplo": types.Schema(
                                    type="STRING",
                                    description=(
                                        "Exemplo concreto ou exercício resolvido que demonstre "
                                        "a ideia explicada."
                                    ),
                                ),
                                "formula": types.Schema(
                                    type="STRING",
                                    description="Fórmula, equação ou relação simbólica opcional.",
                                ),
                                "erros_comuns": types.Schema(
                                    type="ARRAY",
                                    description="Até quatro erros ou confusões comuns dos alunos.",
                                    items=types.Schema(type="STRING"),
                                ),
                                "destaque": types.Schema(
                                    type="STRING",
                                    description="Conclusão principal que o aluno deve guardar.",
                                ),
                            },
                            required=[
                                "titulo", "objetivo", "resumo", "topicos",
                                "diagrama", "exemplo", "destaque",
                            ],
                        ),
                    ),

                    types.FunctionDeclaration(
                        name="encerrar_chamada",
                        description=(
                            "Encerra a chamada atual do ALFRED. Use somente "
                            "quando o usuário pedir claramente para encerrar, "
                            "finalizar, desligar ou terminar a chamada, sessão "
                            "ou conexão. Exemplos: 'encerrar chamada', "
                            "'encerre a sessão', 'finalizar conversa', "
                            "'pode desligar', 'termine a chamada'."
                        ),
                    ),
                ]
            )
        ]

        # Carrega as memórias persistentes e inclui o conteúdo
        # no contexto inicial da conversa.
        memorias_atuais = contexto_memorias()

        # Define identidade, personalidade, início da conversa,
        # limites, regras de memória, visão e encerramento.
        instrucao_sistema = (

            # IDENTIDADE
            "Seu nome é ALFRED. "
            "Você é uma inteligência artificial avançada, capaz de conversar, "
            "analisar contextos e imagens em tempo real. "
            "Converse sempre em português do Brasil. "

            # INÍCIO DA CONVERSA
            "O usuário já está autorizado a conversar com você. "
            "Comece a conversa imediatamente e responda normalmente ao que ele disser. "
            "Nunca solicite palavra-chave, senha, código, confirmação de identidade "
            "ou qualquer outra forma de autenticação. "

            # PERSONALIDADE E RACIOCÍNIO
            "Seja inteligente, natural, prestativo, elegante e intelectualmente rigoroso. "
            "Antes de responder, identifique a intenção e os conhecimentos prévios "
            "necessários para compreender o assunto. "
            "Relacione ideias, destaque causas e consequências e corrija equívocos "
            "com respeito. Não invente fatos; quando houver incerteza, deixe isso claro. "
            "Use humor, ironia e sarcasmo de forma sutil e ocasional. "
            "Não concorde automaticamente com tudo. "
            "Se uma ideia for ruim, arriscada ou pouco eficiente, "
            "diga isso com elegância. "
            "Discorde educadamente quando necessário. "
            "A ironia deve complementar a inteligência, "
            "nunca substituir a utilidade. "
            "Chame o usuário ocasionalmente de senhor "
            "ou pelo primeiro nome quando natural. "
            "Se o usuário lhe ofender ou provocar, você pode responder "
            "com ironia ou sarcasmo, sem ameaças e sem perder a utilidade. "

            # VELOCIDADE E ESTILO DE RESPOSTA
            "Comece a responder assim que entender o pedido, sem saudações, "
            "avisos ou introduções desnecessárias. Vá direto ao assunto. "
            "Para comandos simples, responda de forma curta. "
            "Para perguntas, estudos e explicações, seja detalhado e didático. "
            "Fale em ritmo natural e claro, usando frases bem construídas e "
            "evitando repetições que não acrescentem conhecimento. "

            # MODO PROFESSOR
            "Em assuntos educacionais, comporte-se como um excelente professor particular. "
            "Descubra o nível do usuário pelo contexto; se ele não estiver claro, "
            "comece com linguagem acessível e avance progressivamente. "
            "Primeiro apresente a ideia central. Depois explique os conceitos fundamentais "
            "em uma sequência lógica, conectando cada etapa à anterior. "
            "Use exemplos concretos, analogias intuitivas e aplicações práticas. "
            "Quando houver cálculo, mostre o raciocínio e explique o significado de cada passo. "
            "Quando houver termos técnicos, defina-os na primeira vez que forem usados. "
            "Aponte erros comuns e diferenças que costumam causar confusão. "
            "Conclua com um resumo dos pontos essenciais. Em aulas mais longas, "
            "faça uma pergunta curta no final para verificar a compreensão e permita "
            "que o usuário escolha qual ponto deseja aprofundar. "

            # CONTROLE LOCAL SEGURO
            "Você pode abrir aplicativos usando abrir_aplicativo. "
            "Use essa função apenas quando o usuário pedir explicitamente. "
            "Você pode pesquisar um tema no Google usando pesquisar_no_navegador. "
            "Quando o usuário pedir apenas a pesquisa, abra os resultados e confirme. "
            "Quando ele pedir para pesquisar e também explicar, marque explicacao_detalhada "
            "como verdadeira e, depois da pesquisa, monte uma aula usando "
            "mostrar_conteudo_visual. "
            "Somente calculadora, bloco de notas, explorador de arquivos, Paint, "
            "configurações e navegador estão autorizados. "
            "Você não pode executar comandos de terminal, excluir arquivos, "
            "instalar programas nem realizar outras ações locais. "
            "Nunca afirme que uma ação foi concluída antes de receber o resultado. "

            # EXPLICAÇÕES VISUAIS
            "Ao reconhecer uma pergunta educacional, responda imediatamente com uma "
            "frase curta apresentando a ideia central enquanto prepara o quadro. "
            "Antes de começar qualquer aula ou explicação de matéria, conceito, "
            "processo, cálculo ou sequência, é obrigatório chamar "
            "mostrar_conteudo_visual para atualizar o quadro de sala de aula. "
            "Não dê a explicação completa sem primeiro atualizar o quadro. "
            "Em perguntas de continuação, chame a função novamente com o conteúdo "
            "revisado e inclua o novo ponto solicitado pelo usuário. "
            "Use o quadro como um professor usa a lousa: escreva o objetivo, uma definição "
            "precisa, de quatro a sete conceitos essenciais, um diagrama que mostre as "
            "relações ou a sequência, um exemplo concreto ou exercício resolvido, erros "
            "comuns e uma conclusão. Não produza apenas palavras soltas ou um resumo raso. "
            "Depois de montar o quadro, obrigatoriamente continue falando. Narre a aula em "
            "ordem: ideia central, definição dos termos, explicação de cada conceito, leitura "
            "do diagrama, exemplo explicado passo a passo, erros comuns e conclusão. "
            "A fala deve desenvolver e conectar o que está escrito, não apenas ler o quadro. "
            "Se o tema for amplo, ensine primeiro a base necessária e depois aprofunde. "
            "Adapte a linguagem ao nível demonstrado pelo usuário e verifique a compreensão "
            "com uma pergunta curta ao final. "

            # MEMÓRIA
            "Não memorize informações automaticamente. "
            "Só chame salvar_memoria quando o usuário pedir explicitamente "
            "para lembrar, guardar ou memorizar algo. "
            "Ao salvar, guarde somente o fato útil e objetivo, sem suposições. "
            "Só chame esquecer_memoria quando o usuário pedir claramente "
            "para esquecer algo específico. "
            "Use listar_memorias quando o usuário perguntar o que você lembra "
            "ou pedir para mostrar as memórias. "

            # VISÃO
            "Só chame analisar_tela quando o usuário pedir explicitamente "
            "para ver, analisar, observar ou explicar a tela. "
            "Só chame analisar_camera quando o usuário pedir explicitamente "
            "para ver, analisar, observar ou explicar a câmera, webcam "
            "ou algo mostrado nela. "
            "Nunca use função visual espontaneamente. "
            "Para cada pedido visual, execute no máximo uma captura. "

            # ENCERRAMENTO
            "Quando o usuário pedir claramente para encerrar, finalizar, "
            "desligar ou terminar a chamada, sessão ou conexão, "
            "chame encerrar_chamada. "
            "Não encerre apenas porque o usuário disse tchau, até mais "
            "ou obrigado, salvo se indicar claramente que deseja finalizar. "

            # RETORNO DAS FUNÇÕES
            "Após qualquer função, explique em voz o que foi feito "
            "de forma curta e natural. "

            "\n\n"
            + memorias_atuais
        )

        # Monta a configuração da sessão Live,
        # incluindo áudio, voz, ferramentas e instrução do sistema.
        config = types.LiveConnectConfig(
            response_modalities=[
                "AUDIO"
            ],

            # Gera legendas tanto do microfone quanto da voz do ALFRED.
            input_audio_transcription=types.AudioTranscriptionConfig(
                language_codes=["pt-BR"],
            ),
            output_audio_transcription=types.AudioTranscriptionConfig(
                language_codes=["pt-BR"],
            ),

            # Reduz o intervalo entre o fim da pergunta e o início da resposta.
            realtime_input_config=types.RealtimeInputConfig(
                automatic_activity_detection=types.AutomaticActivityDetection(
                    disabled=False,
                    start_of_speech_sensitivity=(
                        types.StartSensitivity.START_SENSITIVITY_HIGH
                    ),
                    end_of_speech_sensitivity=(
                        types.EndSensitivity.END_SENSITIVITY_HIGH
                    ),
                    prefix_padding_ms=40,
                    silence_duration_ms=250,
                )
            ),

            # MINIMAL prioriza o menor tempo até o início da resposta.
            thinking_config=types.ThinkingConfig(
                thinking_level=types.ThinkingLevel.MINIMAL,
            ),

            # Mantém espaço suficiente para aulas e explicações completas.
            max_output_tokens=4096,

            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=GEMINI_VOICE
                    )
                )
            ),

            tools=tools,

            system_instruction=types.Content(
                parts=[
                    types.Part(
                        text=instrucao_sistema
                    )
                ]
            ),
        )

        # Fila que recebe os blocos capturados pelo microfone.
        fila_microfone = asyncio.Queue(
            maxsize=LIMITE_FILA_MICROFONE
        )
        # Fila que recebe os blocos de áudio enviados pelo Gemini.
        fila_saida = asyncio.Queue()

        self.status_recebido.emit(
            "Conectando ao Gemini Live..."
        )

        # Abre a conexão assíncrona com o modelo Gemini Live.
        # O bloco with encerra a conexão automaticamente ao final.
        async with client.aio.live.connect(
            model=GEMINI_LIVE_MODEL,
            config=config,
        ) as sessao:
            self.sessao = sessao

            self.status_recebido.emit(
                "ALFRED conectado. Pode falar."
            )

            # Inicia três tarefas simultâneas:
            # enviar microfone, receber respostas e reproduzir áudio.
            tarefas = [
                asyncio.create_task(
                    self.enviar_microfone(
                        sessao,
                        fila_microfone,
                    )
                ),

                asyncio.create_task(
                    self.receber_audio(
                        sessao,
                        fila_saida,
                        fila_microfone,
                    )
                ),

                asyncio.create_task(
                    self.reproduzir_audio(
                        fila_saida,
                        fila_microfone,
                    )
                ),
            ]

            # Mantém a sessão viva até que parar() altere self.ativo.
            while self.ativo:
                await asyncio.sleep(
                    0.1
                )

            # Cancela as tarefas quando a chamada está sendo encerrada.
            for tarefa in tarefas:
                tarefa.cancel()

            if self.tarefa_liberar_microfone:
                self.tarefa_liberar_microfone.cancel()

            if self.tarefa_encerramento:
                self.tarefa_encerramento.cancel()

            await asyncio.gather(
                *tarefas,
                return_exceptions=True,
            )

        # Guardará a sessão ativa do Gemini Live.
        self.sessao = None

    # Captura o microfone continuamente e envia os blocos
    # de áudio em tempo real para o Gemini.
    async def enviar_microfone(
        self,
        sessao,
        fila_microfone,
    ):
        # Obtém o loop desta tarefa para inserir áudio na fila
        # a partir do callback do sounddevice.
        loop = asyncio.get_running_loop()

        # Função chamada automaticamente pelo sounddevice
        # sempre que um novo bloco de áudio é capturado.
        def callback(
            indata,
            frames,
            time_info,
            status,
        ):
            if not self.ativo:
                return

            # Ignora o microfone enquanto o ALFRED fala,
            # evitando que ele escute a própria voz.
            if self.alfred_falando:
                return

            if status:
                print(
                    "Aviso microfone:",
                    status,
                )

            # Converte os dados capturados para bytes.
            audio_bytes = bytes(
                indata
            )

            # Envia os bytes para a fila assíncrona com segurança
            # a partir do callback de áudio.
            # Se a fila estiver cheia, o bloco mais novo é descartado
            # para impedir atraso e acúmulo de áudio antigo.
            def adicionar_audio():
                if self.alfred_falando or not self.ativo:
                    return

                try:
                    fila_microfone.put_nowait(
                        audio_bytes
                    )

                except asyncio.QueueFull:
                    pass

            loop.call_soon_threadsafe(
                adicionar_audio
            )

        # Abre o fluxo de entrada bruto do microfone.
        with sd.RawInputStream(
            samplerate=TAXA_ENTRADA,
            blocksize=BLOCO,
            dtype="int16",
            channels=CANAIS,
            callback=callback,
        ):
            # Mantém a sessão viva até que parar() altere self.ativo.
            while self.ativo:
                audio_bytes = await fila_microfone.get()

                # O bloco pode ter entrado na fila poucos milissegundos
                # antes de o assistente começar a falar.
                # Fazemos uma segunda verificação para garantir que o
                # usuário nunca interrompa o assistente durante a resposta.
                if self.alfred_falando:
                    continue

                # Envia o bloco de áudio atual para o Gemini Live.
                await sessao.send_realtime_input(
                    audio=types.Blob(
                        data=audio_bytes,
                        mime_type=(
                            f"audio/pcm;rate={TAXA_ENTRADA}"
                        ),
                    )
                )

    # Recebe as respostas da sessão Gemini.
    # Pode receber áudio e também pedidos de chamadas de ferramentas.
    async def receber_audio(
        self,
        sessao,
        fila_saida,
        fila_microfone,
    ):
        while self.ativo:
            # Percorre continuamente as respostas enviadas pela sessão.
            async for resposta in sessao.receive():
                if not self.ativo:
                    break

                conteudo_servidor = resposta.server_content
                if conteudo_servidor:
                    # O texto interino é cumulativo e substitui a legenda atual.
                    entrada_interina = (
                        conteudo_servidor.interim_input_transcription
                    )
                    if entrada_interina and entrada_interina.text:
                        self.transcricao_recebida.emit(
                            "usuario",
                            entrada_interina.text,
                            bool(entrada_interina.finished),
                            True,
                        )

                    entrada_final = conteudo_servidor.input_transcription
                    if entrada_final and entrada_final.text:
                        self.transcricao_recebida.emit(
                            "usuario",
                            entrada_final.text,
                            bool(entrada_final.finished),
                            True,
                        )

                    saida = conteudo_servidor.output_transcription
                    if saida and saida.text:
                        self.transcricao_recebida.emit(
                            "alfred",
                            saida.text,
                            bool(saida.finished),
                            False,
                        )

                    if conteudo_servidor.turn_complete:
                        self.transcricao_recebida.emit(
                            "alfred", "", True, False
                        )

                # Quando chega o primeiro bloco de resposta, bloqueia
                # imediatamente o microfone antes mesmo da reprodução.
                # Também elimina qualquer áudio antigo que tenha sido
                # capturado pouco antes do início da resposta.
                if resposta.data:
                    self.alfred_falando = True

                    if self.tarefa_liberar_microfone:
                        self.tarefa_liberar_microfone.cancel()

                    self.limpar_fila_microfone(
                        fila_microfone
                    )

                    await fila_saida.put(
                        resposta.data
                    )

                # Quando o Gemini solicita uma ferramenta,
                # encaminha para o processador de funções.
                if resposta.tool_call:
                    await self.processar_chamada_de_funcao(
                        sessao,
                        resposta.tool_call,
                    )

    # Executa as ferramentas solicitadas pelo Gemini
    # e devolve os resultados para a sessão.
    async def processar_chamada_de_funcao(
        self,
        sessao,
        tool_call,
    ):
        # Armazena as respostas de todas as funções solicitadas.
        function_responses = []
        # Indica se a sessão deve ser encerrada após a resposta falada.
        encerrar_depois = False
        # Indica que o quadro precisa ser seguido por explicação em áudio.
        garantir_fala_depois = False
        # Continua no modo professor quando a pesquisa também solicitar uma aula.
        pesquisa_com_aula = False

        # Uma mesma resposta pode conter uma ou mais chamadas de função.
        for chamada in tool_call.function_calls:
            nome = chamada.name
            # Converte os argumentos recebidos para um dicionário comum.
            args = dict(
                chamada.args or {}
            )

            if nome in (
                "analisar_tela",
                "analisar_camera",
            ):
                resultado = await self.processar_funcao_visual(
                    nome
                )

            elif nome == "salvar_memoria":
                texto = args.get(
                    "texto",
                    "",
                )

                self.status_recebido.emit(
                    "Salvando memória..."
                )

                resultado = salvar_memoria(
                    texto
                )

            elif nome == "listar_memorias":
                self.status_recebido.emit(
                    "Consultando memórias..."
                )

                resultado = listar_memorias()

            elif nome == "esquecer_memoria":
                referencia = args.get(
                    "referencia",
                    "",
                )

                self.status_recebido.emit(
                    "Removendo memória..."
                )

                resultado = esquecer_memoria(
                    referencia
                )

            elif nome == "abrir_aplicativo":
                aplicativo = args.get(
                    "nome",
                    "",
                )

                self.status_recebido.emit(
                    f"Abrindo {aplicativo}..."
                )

                resultado = abrir_aplicativo(
                    aplicativo
                )

            elif nome == "pesquisar_no_navegador":
                tema = args.get("tema", "")
                explicar = bool(args.get("explicacao_detalhada", False))

                self.status_recebido.emit(
                    f"Pesquisando {tema} no navegador..."
                )
                resultado = pesquisar_no_navegador(tema)
                pesquisa_com_aula = pesquisa_com_aula or explicar

            elif nome == "mostrar_conteudo_visual":
                conteudo = {
                    "titulo": args.get("titulo", "Explicação visual"),
                    "objetivo": args.get("objetivo", ""),
                    "resumo": args.get("resumo", ""),
                    "topicos": args.get("topicos", []),
                    "diagrama": args.get("diagrama", []),
                    "etapas": args.get("etapas", []),
                    "exemplo": args.get("exemplo", ""),
                    "formula": args.get("formula", ""),
                    "erros_comuns": args.get("erros_comuns", []),
                    "destaque": args.get("destaque", ""),
                }

                self.status_recebido.emit(
                    "Montando explicação visual..."
                )
                self.conteudo_visual_recebido.emit(
                    conteudo
                )

                resultado = (
                    "O quadro da aula foi atualizado. Continue agora por voz, sem chamar "
                    "outra ferramenta. Dê a aula completa e detalhada: desenvolva cada "
                    "conceito, narre o diagrama, resolva o exemplo e conclua."
                )
                garantir_fala_depois = True

            elif nome == "encerrar_chamada":
                self.status_recebido.emit(
                    "Encerrando chamada por comando de voz..."
                )

                resultado = (
                    "Solicitação de encerramento recebida. "
                    "Diga de forma curta que a chamada será encerrada."
                )

                encerrar_depois = True

            else:
                resultado = (
                    "Função desconhecida. Nenhuma ação foi executada."
                )

            # Cria a resposta estruturada que será devolvida ao Gemini.
            function_responses.append(
                types.FunctionResponse(
                    id=chamada.id,
                    name=nome,
                    response={
                        "result": resultado
                    },
                )
            )

        # Envia todos os resultados das ferramentas para o modelo.
        if function_responses:
            await sessao.send_tool_response(
                function_responses=(
                    function_responses
                )
            )

        if garantir_fala_depois:
            self.status_recebido.emit(
                "Continuando explicação por voz..."
            )
            await sessao.send_realtime_input(
                text=(
                    "O quadro já está atualizado. Não chame nenhuma ferramenta. "
                    "Fale agora e dê uma aula detalhada, como um ótimo professor particular. "
                    "Comece pela definição, conecte e aprofunde cada conceito escrito, "
                    "descreva o diagrama na ordem, desenvolva o exemplo passo a passo, "
                    "alerte sobre os erros comuns e termine com uma síntese e uma pergunta "
                    "para verificar se o aluno compreendeu. Não apenas leia o quadro e não "
                    "termine depois de uma frase curta."
                )
            )
        elif pesquisa_com_aula:
            self.status_recebido.emit(
                "Preparando aula detalhada sobre a pesquisa..."
            )
            await sessao.send_realtime_input(
                text=(
                    "A pesquisa já foi aberta no navegador. Agora chame obrigatoriamente "
                    "mostrar_conteudo_visual para montar uma aula completa sobre o tema "
                    "pesquisado. Depois do quadro, explique tudo detalhadamente por voz."
                )
            )

        # Agenda o encerramento somente depois da resposta de despedida.
        if encerrar_depois:
            if self.tarefa_encerramento:
                self.tarefa_encerramento.cancel()

            self.tarefa_encerramento = asyncio.create_task(
                self.encerrar_apos_resposta()
            )

    # Aguarda alguns segundos para o ALFRED concluir a despedida
    # antes de pedir que a interface finalize a chamada.
    async def encerrar_apos_resposta(self):
        """
        Aguarda a resposta de despedida do ALFRED
        e só depois solicita o encerramento à interface.
        """

        try:
            await asyncio.sleep(
                2.8
            )

            if self.ativo:
                self.solicitou_encerramento.emit()

        except asyncio.CancelledError:
            pass

    # Controla as capturas de tela e câmera,
    # impedindo repetição e chamadas simultâneas.
    async def processar_funcao_visual(
        self,
        nome,
    ):
        if self.executando_funcao_visual:
            return (
                "Uma análise visual já está em andamento. "
                "Use a última imagem recebida e responda ao usuário."
            )

        # time.monotonic() mede intervalos sem ser afetado
        # por alterações no relógio do computador.
        agora = time.monotonic()

        # Verifica se a mesma função visual foi chamada
        # novamente dentro do período de cooldown.
        repetido = (
            nome == self.ultima_funcao_visual
            and agora - self.tempo_ultima_funcao_visual
            < COOLDOWN_FUNCAO_VISUAL
        )

        if repetido:
            return (
                "Chamada visual duplicada ignorada. "
                "A imagem já foi capturada para este pedido. "
                "Use a última imagem recebida e responda sem "
                "chamar função novamente."
            )

        # Bloqueia novas capturas enquanto esta estiver em andamento.
        self.executando_funcao_visual = True
        self.ultima_funcao_visual = nome
        self.tempo_ultima_funcao_visual = agora

        try:
            if nome == "analisar_tela":
                self.status_recebido.emit(
                    "Comando de voz detectado: analisar tela."
                )

                await self.enviar_tela_para_gemini(
                    origem="voz"
                )

                return (
                    "A tela foi capturada e enviada. "
                    "Responda usando exatamente a última imagem recebida."
                )

            if nome == "analisar_camera":
                self.status_recebido.emit(
                    "Comando de voz detectado: analisar câmera."
                )

                await self.enviar_camera_para_gemini(
                    origem="voz"
                )

                return (
                    "A câmera foi capturada e enviada. "
                    "Responda usando exatamente a última imagem recebida."
                )

            return "Função visual desconhecida."

        # Este bloco sempre é executado, mesmo se ocorrer erro.
        finally:
            self.executando_funcao_visual = False

    # Reproduz os blocos de áudio enviados pelo Gemini
    # e atualiza o nível visual da interface.
    async def reproduzir_audio(
        self,
        fila_saida,
        fila_microfone,
    ):
        # Abre o dispositivo de saída de áudio no formato PCM.
        with sd.RawOutputStream(
            samplerate=TAXA_SAIDA,
            blocksize=BLOCO,
            dtype="int16",
            channels=CANAIS,
        ) as saida:
            # Mantém a sessão viva até que parar() altere self.ativo.
            while self.ativo:
                audio_bytes = await fila_saida.get()

                # Mantém o microfone bloqueado durante toda a reprodução
                # e descarta qualquer bloco antigo que ainda tenha sobrado.
                self.alfred_falando = True
                self.limpar_fila_microfone(
                    fila_microfone
                )

                # Calcula o volume aproximado do bloco atual.
                nivel = self.calcular_nivel_audio(
                    audio_bytes
                )

                self.nivel_audio.emit(
                    nivel
                )

                # Reproduz o bloco em uma thread auxiliar.
                # Isso evita que drivers de áudio mais lentos bloqueiem
                # o loop que recebe os próximos blocos do Gemini.
                await asyncio.to_thread(
                    saida.write,
                    audio_bytes,
                )

                # Não adicionar asyncio.sleep aqui.
                # Uma pausa por bloco deixa a voz picotando.

                if self.tarefa_liberar_microfone:
                    self.tarefa_liberar_microfone.cancel()

                self.tarefa_liberar_microfone = asyncio.create_task(
                    self.liberar_microfone_apos_fala()
                )

    @staticmethod
    def limpar_fila_microfone(
        fila_microfone,
    ):
        """
        Descarta todos os blocos de áudio que ainda aguardavam envio.
        Isso impede que um trecho capturado antes da resposta seja
        enviado ao Gemini enquanto o assistente já está falando.
        """

        while True:
            try:
                fila_microfone.get_nowait()

            except asyncio.QueueEmpty:
                break

    # O método abaixo não utiliza self, por isso é estático.
    @staticmethod
    # Calcula um valor entre 0 e 1 com base no pico
    # das amostras do áudio recebido.
    def calcular_nivel_audio(
        audio_bytes,
    ):
        if not audio_bytes:
            return 0.0

        try:
            # Interpreta os bytes como inteiros de 16 bits.
            amostras = array(
                "h",
                audio_bytes,
            )

            if not amostras:
                return 0.0

            # Obtém a maior amplitude presente no bloco.
            pico = max(
                abs(amostra)
                for amostra in amostras
            )

            # Normaliza a amplitude para a faixa aproximada de 0 a 1.
            nivel = pico / 32768.0
            # Ajusta a curva para deixar a animação visual mais sensível.
            nivel = nivel ** 0.55

            return max(
                0.0,
                min(
                    1.0,
                    nivel,
                ),
            )

        except (
            ValueError,
            OverflowError,
        ):
            return 0.0

    # Aguarda um pequeno intervalo depois da fala
    # antes de liberar o microfone novamente.
    async def liberar_microfone_apos_fala(
        self,
    ):
        try:
            await asyncio.sleep(
                ATRASO_REABRIR_MICROFONE
            )

            self.alfred_falando = False

            self.nivel_audio.emit(
                0.0
            )

        except asyncio.CancelledError:
            pass

    # Método chamado pela interface quando o botão
    # de análise de tela é pressionado.
    def solicitar_analise_tela(
        self,
    ):
        if not self.loop or not self.sessao:
            self.erro_recebido.emit(
                "Sessão Gemini ainda não está pronta."
            )

            return

        # Agenda a função assíncrona dentro do loop da thread.
        asyncio.run_coroutine_threadsafe(
            self.enviar_tela_para_gemini(
                origem="botao"
            ),
            self.loop,
        )

    # Captura a tela, envia a imagem ao Gemini
    # e adiciona instruções específicas para a análise.
    async def enviar_tela_para_gemini(
        self,
        origem="botao",
    ):
        try:
            self.status_recebido.emit(
                "Capturando tela..."
            )

            # Captura a tela atual no formato JPEG em bytes.
            imagem_bytes = capturar_tela_bytes()

            # Envia uma nova mensagem contendo imagem e instrução textual.
            await self.sessao.send_client_content(
                turns=[
                    types.Content(
                        role="user",
                        parts=[
                            types.Part(
                                inline_data=types.Blob(
                                    data=imagem_bytes,
                                    mime_type="image/jpeg",
                                )
                            ),

                            types.Part(
                                text=(
                                    "Analise exatamente esta imagem da tela "
                                    "enviada neste turno. Ignore imagens "
                                    "anteriores. Use somente esta imagem como "
                                    "base. Não chame nenhuma função visual. "
                                    "Não chute. Se a imagem não estiver clara, "
                                    "diga que não conseguiu ver bem. Explique "
                                    "de forma objetiva o que está vendo."
                                )
                            ),
                        ],
                    )
                ],
                turn_complete=True,
            )

            self.status_recebido.emit(
                "Tela enviada para análise."
            )

        except Exception as erro:
            self.erro_recebido.emit(
                f"Erro ao analisar tela: {erro}"
            )

    # Método chamado pela interface quando o botão
    # de análise da câmera é pressionado.
    def solicitar_analise_camera(
        self,
    ):
        if not self.loop or not self.sessao:
            self.erro_recebido.emit(
                "Sessão Gemini ainda não está pronta."
            )

            return

        # Agenda a função assíncrona dentro do loop da thread.
        asyncio.run_coroutine_threadsafe(
            self.enviar_camera_para_gemini(
                origem="botao"
            ),
            self.loop,
        )

    # Captura uma imagem da webcam e envia
    # o conteúdo para análise do Gemini.
    async def enviar_camera_para_gemini(
        self,
        origem="botao",
    ):
        try:
            self.status_recebido.emit(
                "Capturando imagem da câmera..."
            )

            # Captura o quadro atual da webcam como JPEG em bytes.
            imagem_bytes = capturar_camera_bytes()

            # Envia uma nova mensagem contendo imagem e instrução textual.
            await self.sessao.send_client_content(
                turns=[
                    types.Content(
                        role="user",
                        parts=[
                            types.Part(
                                inline_data=types.Blob(
                                    data=imagem_bytes,
                                    mime_type="image/jpeg",
                                )
                            ),

                            types.Part(
                                text=(
                                    "Analise exatamente esta imagem da câmera "
                                    "enviada neste turno. Ignore imagens "
                                    "anteriores. Use somente esta imagem como "
                                    "base. Não chame nenhuma função visual. "
                                    "Não chute. Se a imagem não estiver clara, "
                                    "diga que não conseguiu ver bem. Explique "
                                    "de forma objetiva o que está vendo."
                                )
                            ),
                        ],
                    )
                ],
                turn_complete=True,
            )

            self.status_recebido.emit(
                "Imagem da câmera enviada para análise."
            )

        except Exception as erro:
            self.erro_recebido.emit(
                f"Erro ao analisar câmera: {erro}"
            )

    # Encerra o loop principal da sessão e zera o nível de áudio.
    def parar(self):
        self.ativo = False

        self.nivel_audio.emit(
            0.0
        )
