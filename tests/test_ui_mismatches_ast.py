"""
tests/test_ui_mismatches_ast.py — Regression test scanning main.py for JarvisUI attributes.

Asserts:
1. Every attribute accessed via `self.ui.X` or `ui.X` in main.py exists on JarvisUI.
2. `JarvisUI.set_media_arbiter` has the expected signature `(self, arbiter)`.
"""

import ast
import inspect
import os
import sys
import unittest
from pathlib import Path

# Ensure workspace root is in sys.path
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))


class TestUiMismatchesAST(unittest.TestCase):

    def test_all_ui_attributes_exist_on_jarvis_ui(self):
        """Scan main.py AST for all ui attribute accesses and assert they exist on JarvisUI."""
        main_path = WORKSPACE_ROOT / "main.py"
        self.assertTrue(main_path.exists(), "main.py must exist")

        with open(main_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename="main.py")

        ui_attrs = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                # match self.ui.X
                if isinstance(node.value, ast.Attribute) and node.value.attr == "ui":
                    ui_attrs.add(node.attr)
                # match ui.X where ui is a local/global identifier
                elif isinstance(node.value, ast.Name) and node.value.id == "ui":
                    ui_attrs.add(node.attr)

        self.assertGreater(len(ui_attrs), 0, "Should have detected ui attribute accesses in main.py")

        import ui
        jarvis_ui_cls = ui.JarvisUI

        # Collect all class-level attributes, methods, and properties
        cls_members = set(dir(jarvis_ui_cls))

        # Known attributes dynamically set in __init__ (like self._win, self.root)
        instance_init_attrs = {"_win", "root"}
        known_attrs = cls_members | instance_init_attrs

        missing = {attr for attr in ui_attrs if attr not in known_attrs}
        self.assertEqual(
            missing,
            set(),
            f"Attributes accessed on ui in main.py but missing on JarvisUI: {sorted(missing)}"
        )

    def test_set_media_arbiter_signature(self):
        """Assert that set_media_arbiter exists on JarvisUI with signature (self, arbiter)."""
        import ui
        self.assertTrue(
            hasattr(ui.JarvisUI, "set_media_arbiter"),
            "JarvisUI must define set_media_arbiter"
        )
        fn = getattr(ui.JarvisUI, "set_media_arbiter")
        sig = inspect.signature(fn)
        params = list(sig.parameters.keys())
        self.assertEqual(params, ["self", "arbiter"], f"Expected (self, arbiter), got {params}")


if __name__ == "__main__":
    unittest.main()
