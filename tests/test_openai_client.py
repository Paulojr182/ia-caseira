import json
import unittest
from types import SimpleNamespace

from ai.openai_client import OpenAIProfessorClient


class FakeItem(SimpleNamespace):
    def model_dump(self, **_kwargs):
        return dict(self.__dict__)


class FakeStream:
    def __init__(self, deltas, response):
        self.events = [
            SimpleNamespace(type="response.output_text.delta", delta=delta)
            for delta in deltas
        ]
        self.response = response

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def __iter__(self):
        return iter(self.events)

    def get_final_response(self):
        return self.response


class FakeResponses:
    def __init__(self, streams):
        self.streams = list(streams)
        self.requests = []

    def stream(self, **kwargs):
        self.requests.append(kwargs)
        return self.streams.pop(0)


class FakeClient:
    def __init__(self, streams):
        self.responses = FakeResponses(streams)


def response(output=None, output_text=""):
    return SimpleNamespace(
        output=output or [], output_text=output_text, usage=None, model="fake-model"
    )


class OpenAIClientTests(unittest.TestCase):
    def test_streams_text(self):
        fake = FakeClient([FakeStream(["Olá", ", senhor."], response())])
        deltas = []
        models = []
        provider = OpenAIProfessorClient(
            on_board=lambda _content: None,
            on_status=lambda _status: None,
            on_model=models.append,
            client=fake,
        )
        result = provider.respond("Boa noite", deltas.append, lambda: False)
        self.assertEqual(result[0], "Olá, senhor.")
        self.assertEqual(models, ["LUNA"])

    def test_executes_board_then_continues_response(self):
        arguments = {
            "titulo": "Fotossíntese", "objetivo": "Entender", "resumo": "Processo",
            "topicos": ["Luz"], "diagrama": ["Sol", "Planta"], "etapas": [],
            "exemplo": "Folha", "formula": "", "erros_comuns": [],
            "destaque": "Energia",
        }
        call = FakeItem(
            type="function_call", name="mostrar_conteudo_visual",
            arguments=json.dumps(arguments), call_id="call-1",
        )
        fake = FakeClient([
            FakeStream([], response([call])),
            FakeStream(["A fotossíntese transforma luz."], response()),
        ])
        boards = []
        provider = OpenAIProfessorClient(
            on_board=boards.append,
            on_status=lambda _status: None,
            on_model=lambda _model: None,
            client=fake,
        )
        result = provider.respond(
            "Explique fotossíntese", lambda _delta: None, lambda: False
        )
        self.assertEqual(boards[0]["titulo"], "Fotossíntese")
        self.assertIn("fotossíntese", result[0].lower())
        second_input = fake.responses.requests[1]["input"]
        self.assertEqual(second_input[-1]["type"], "function_call_output")


if __name__ == "__main__":
    unittest.main()
