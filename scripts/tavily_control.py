"""Repository-wide Tavily pause switch, independent of credentials."""
from pathlib import Path

PAUSE_MARKER = Path(__file__).resolve().parents[1] / ".tavily-paused"


def tavily_paused():
    return PAUSE_MARKER.exists()
