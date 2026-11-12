"""Offline tests for CNBC percent-change handling without importing live collectors."""
import ast
from pathlib import Path
import re
import unittest

source = Path(__file__).resolve().parents[1] / "scripts" / "refresh.py"
tree = ast.parse(source.read_text(encoding="utf-8"))
functions = [node for node in tree.body
             if isinstance(node, ast.FunctionDef) and node.name in ("num", "pct")]
scope = {"re": re}
exec(compile(ast.Module(body=functions, type_ignores=[]), str(source), "exec"), scope)
pct = scope["pct"]

class CNBCPercentChangeTests(unittest.TestCase):
    def test_explicit_unch(self):
        for raw in ("UNCH", "unch", "UNCHANGED", "UNCHG", "  UNCH  "):
            with self.subTest(raw=raw):
                self.assertEqual(pct({"change_pct": raw, "last": "104.72"}), 0.0)

    def test_numeric_zero(self):
        self.assertEqual(pct({"change_pct": "0.00%", "last": "104.72"}), 0.0)

    def test_equal_previous_close(self):
        self.assertEqual(pct({"last": "104.72", "previous_day_closing": "104.72"}), 0.0)

    def test_missing_reference_stays_missing(self):
        self.assertIsNone(pct({"last": "104.72", "change_pct": "n/a"}))

    def test_numeric_change_preferred(self):
        self.assertEqual(pct({"change_pct": "-1.25%", "last": "100", "previous_day_closing": "95"}), -1.25)

if __name__ == "__main__":
    unittest.main()
