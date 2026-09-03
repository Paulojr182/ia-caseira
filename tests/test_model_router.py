import unittest

from ai.model_router import ModelRouter


class ModelRouterTests(unittest.TestCase):
    def test_uses_luna_for_simple_message(self):
        self.assertEqual(ModelRouter().choose("Boa noite").tier, "LUNA")

    def test_uses_terra_for_lesson(self):
        self.assertEqual(
            ModelRouter().choose("Professor, explique fotossíntese detalhadamente").tier,
            "TERRA",
        )

    def test_sol_is_one_shot(self):
        router = ModelRouter()
        router.consume_mode_command("Alfred, use Sol nesta pergunta")
        self.assertEqual(router.choose("Resolva isto").tier, "SOL")
        self.assertNotEqual(router.choose("Boa noite").tier, "SOL")

    def test_detects_current_web_request(self):
        self.assertTrue(ModelRouter.should_search_web("Pesquise o edital mais recente"))


if __name__ == "__main__":
    unittest.main()
