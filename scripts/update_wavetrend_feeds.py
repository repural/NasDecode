"""Collect both tickers, reconcile saved observations and publish latest complete WT."""
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path
from zoneinfo import ZoneInfo


def run(*args):
    subprocess.run([sys.executable, *args], check=True)


def main():
    now = dt.datetime.now(ZoneInfo('America/New_York'))
    prior = now.date() - dt.timedelta(days=1)
    while prior.weekday() >= 5:
        prior -= dt.timedelta(days=1)
    errors = []
    for symbol in ('NVDA', 'SOXL'):
        name = symbol.lower()
        path = Path('data/research/' + name + '-wavetrend.json')
        # Capture Yahoo against the old baseline before Massive replaces those dates.
        run('-m', 'scripts.shadow_nvda_yahoo_wavetrend', '--symbol', symbol)
        source = json.loads(path.read_text())
        if source['timeframes']['4h']['latest']['endET'][:10] < prior.isoformat():
            try:
                run('-m', 'scripts.refresh_' + name + '_wavetrend')
            except subprocess.CalledProcessError:
                # Historical-provider failures must not block a complete Yahoo overlay.
                errors.append({'symbol': symbol, 'stage': 'Massive refresh'})
        run('-m', 'scripts.reconcile_nvda_yahoo_wavetrend', '--symbol', symbol)
        if symbol == 'SOXL':
            run('scripts/backtest_wavetrend.py')
        run('-m', 'scripts.publish_' + name + '_wavetrend')
    report = {'checkedAtET': now.isoformat(), 'errors': errors}
    Path('audit-output').mkdir(exist_ok=True)
    Path('audit-output/wavetrend-publication.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
