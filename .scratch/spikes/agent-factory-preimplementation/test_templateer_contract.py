"""Contract checks for the investigated Templateer Python boundary."""

from __future__ import annotations

import ast
import tempfile
import unittest
from pathlib import Path

from pydantic import BaseModel
from templateer.renderer import render_template
from templateer_probe import VALID_FRAGMENT, run_probe


class TemplateerBoundaryProbeTests(unittest.TestCase):
    """Lock the current observations and the bounded workaround."""

    def test_current_and_comparison_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            results = run_probe(Path(directory) / "artifacts")
        self.assertTrue(results["probe_passed"], results)


class FutureTemplateerRawPythonContract(unittest.TestCase):
    """Executable contract for a future first-class upstream fragment type."""

    @unittest.expectedFailure
    def test_raw_fragment_is_explicit_and_ordinary_strings_stay_escaped(self) -> None:
        from templateer.fragments import PythonFragment

        class Model(BaseModel):
            label: str
            body: PythonFragment

        with tempfile.TemporaryDirectory() as directory:
            template_path = Path(directory) / "template.j2"
            template_path.write_text(
                'LABEL = "{{ label }}"\n\n{{ body }}', encoding="utf-8"
            )
            artifact = render_template(
                template_path,
                Model(
                    label='safe"\nINJECTED = True\n#',
                    body=PythonFragment(VALID_FRAGMENT),
                ),
                "python",
            )

        tree = ast.parse(artifact)
        assigned_names = {
            node.targets[0].id
            for node in tree.body
            if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
        }
        self.assertEqual(assigned_names, {"LABEL"})
        self.assertIn(VALID_FRAGMENT, artifact)


if __name__ == "__main__":
    unittest.main()
