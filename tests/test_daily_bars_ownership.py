"""Guard against competing writers of the canonical per-ticker OHLCV/VWAP/SMA archive."""
import ast
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]

class DailyBarsOwnershipTests(unittest.TestCase):
    def test_refresh_never_writes_per_ticker_archive(self):
        source=(ROOT/"scripts/refresh.py").read_text(encoding="utf-8")
        tree=ast.parse(source)
        function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=="main")
        # A dedicated history writer belongs in collect_daily_bars.py, not the dashboard main().
        self.assertNotIn("history_path=os.path.join(HISTORY_DIR,f'{ticker.lower()}-daily.json')",source)
        self.assertFalse(any(isinstance(n,ast.Call) and isinstance(n.func,ast.Name)
                             and n.func.id=="open" and n.args
                             and isinstance(n.args[0],ast.Name) and n.args[0].id=="history_path"
                             for n in ast.walk(function)))

if __name__=="__main__":
    unittest.main()
