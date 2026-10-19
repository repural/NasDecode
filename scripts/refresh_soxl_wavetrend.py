"""Incrementally update SOXL confirmed history using Massive historical access."""
import datetime as dt
import json
import os
from pathlib import Path
from scripts.research_soxl_wavetrend import load_extended_bars, NY
from scripts.refresh_nvda_wavetrend import refresh

SOURCE = Path("data/research/soxl-wavetrend.json")


def main():
    now = dt.datetime.now(NY)
    key = os.getenv("MASSIVE_API_KEY", "").strip()
    if not key:
        raise RuntimeError("MASSIVE_API_KEY unavailable")
    original = json.loads(SOURCE.read_text())
    last = dt.datetime.fromisoformat(original["timeframes"]["4h"]["latest"]["endET"]).date()
    # Catch up the whole gap; retain all stored historical candles and warm-up.
    span = max(3, (now.date() - last).days + 3)
    bars, errors = load_extended_bars(span, now.date(), key)
    if errors:
        raise RuntimeError("Provider historical fetch incomplete: " + str(errors))
    candidate, advanced = refresh(original, bars, now, symbol="SOXL")
    if advanced:
        SOURCE.write_text(json.dumps(candidate, indent=2) + "\n")
    print("SOXL historical refresh:", "advanced" if advanced else "unchanged",
          candidate["timeframes"]["4h"]["lastEndET"])


if __name__ == "__main__":
    main()
