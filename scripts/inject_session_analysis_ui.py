#!/usr/bin/env python3
"""Inject the session-analysis presentation script into deployed public/index.html.

The source index remains the main dashboard template. The refresh workflow rebuilds
public/index.html from it, then this small injector adds the independent timeline UI.
"""
from pathlib import Path
import sys

path=Path(sys.argv[1] if len(sys.argv)>1 else 'public/index.html')
text=path.read_text(encoding='utf-8')
tag='<script src="session-analysis.js?v=1"></script>'
if tag not in text:
    if '</body>' in text:
        text=text.replace('</body>',tag+'</body>',1)
    else:
        text+=tag
    path.write_text(text,encoding='utf-8')
