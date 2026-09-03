import json
import unittest
from unittest.mock import patch

from ai.tools import ToolExecutor


class ToolExecutorTests(unittest.TestCase):
    def setUp(self):
        self.boards = []
        self.statuses = []
        self.executor = ToolExecutor(self.boards.append, self.statuses.append)

    def test_board_is_structured_and_emitted(self):
        arguments = {
            "titulo": "Fotossíntese",
            "objetivo": "Compreender",
            "resumo": "Processo das plantas.",
            "topicos": ["Luz"],
            "diagrama": ["Sol", "Planta"],
            "etapas": [],
            "exemplo": "Uma folha ao sol.",
            "formula": "",
            "erros_comuns": [],
            "destaque": "Energia química.",
        }
        result = json.loads(
            self.executor.execute("mostrar_conteudo_visual", json.dumps(arguments))
        )
        self.assertTrue(result["sucesso"])
        self.assertEqual(self.boards[0]["titulo"], "Fotossíntese")

    @patch("ai.tools.abrir_aplicativo")
    def test_local_action_stays_in_safe_layer(self, action):
        action.return_value = {"sucesso": True}
        self.executor.execute("abrir_aplicativo", '{"nome":"calculadora"}')
        action.assert_called_once_with("calculadora")


if __name__ == "__main__":
    unittest.main()
