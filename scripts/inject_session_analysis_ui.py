#!/usr/bin/env python3
"""Inject the session-analysis presentation script into deployed public/index.html.

The source index remains the main dashboard template. The refresh workflow rebuilds
public/index.html from it, then this small injector adds the independent timeline UI.
"""
from pathlib import Path
import sys

path=Path(sys.argv[1] if len(sys.argv)>1 else 'public/index.html')
text=path.read_text(encoding='utf-8')

# Dashboard refresh copies index.html into public/index.html on every run.
# Refuse to publish an outdated template that silently drops technical analysis.
required=(
    "categoryHeading('Technical Analysis'",
    "ndWaveTrendCard",
    "nvda-wavetrend.js",
)
missing=[token for token in required if token not in text]
if missing:
    raise SystemExit("Canonical dashboard template is missing NVDA Technical Analysis: "+", ".join(missing))

tag='<script src="session-analysis.js?v=2"></script>'
if tag not in text:
    if '</body>' in text:
        text=text.replace('</body>',tag+'</body>',1)
    else:
        text+=tag
    path.write_text(text,encoding='utf-8')
