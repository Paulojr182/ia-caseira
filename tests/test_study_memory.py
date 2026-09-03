import unittest
from pathlib import Path
from unittest.mock import patch

from memory import teacher_progress_manager as progress
from study import material_search


class StudyMemoryTests(unittest.TestCase):
    def test_progress_is_persisted_as_summary(self):
        path = Path(__file__).parent / "runtime" / "teacher_progress.json"
        path.unlink(missing_ok=True)
        self.addCleanup(path.unlink, missing_ok=True)
        with patch.object(progress, "PROGRESS_FILE", path):
            progress.update_teacher_progress(
                "Matemática", "Porcentagem", "difficulty",
                "Entendeu a base.", "Revisar aumento percentual.",
            )
            saved = progress.get_teacher_progress("Matemática")
        self.assertEqual(
            saved["progress"]["topics"]["porcentagem"]["result"],
            "difficulty",
        )

    def test_search_returns_only_relevant_excerpt(self):
        runtime = Path(__file__).parent / "runtime"
        materials = runtime / "materials"
        exams = runtime / "exams"
        path = materials / "biologia.txt"
        path.write_text(
            "Fotossíntese converte energia luminosa em energia química.",
            encoding="utf-8",
        )
        self.addCleanup(path.unlink, missing_ok=True)
        with patch.object(material_search, "MATERIALS_DIR", materials), patch.object(
            material_search, "EXAMS_DIR", exams
        ):
            result = material_search.search_materials("energia fotossíntese")
        self.assertTrue(result["success"])
        self.assertEqual(result["snippets"][0]["arquivo"], "biologia.txt")


if __name__ == "__main__":
    unittest.main()
