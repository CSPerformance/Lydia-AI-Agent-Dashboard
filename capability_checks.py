#!/usr/bin/env python3
"""Run isolated regressions and save an honest machine-readable scorecard."""
import argparse
import contextlib
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import unittest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('/tmp/lydia-capabilities/offline.json'))
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    suite = unittest.defaultTestLoader.discover(str(root / 'tests'))
    captured = io.StringIO()
    with contextlib.redirect_stdout(captured), contextlib.redirect_stderr(captured):
        result = unittest.TextTestRunner(stream=captured, verbosity=1).run(suite)
    report = {
        'recorded_at': datetime.now(timezone.utc).isoformat(),
        'scope': 'isolated regression tests; not live capability acceptance',
        'status': 'pass' if result.wasSuccessful() else 'fail',
        'tests_run': result.testsRun,
        'passed': result.testsRun - len(result.failures) - len(result.errors) - len(result.skipped),
        'failures': [{'test': case.id(), 'detail': detail} for case, detail in result.failures],
        'errors': [{'test': case.id(), 'detail': detail} for case, detail in result.errors],
        'skipped': [{'test': case.id(), 'reason': reason} for case, reason in result.skipped],
        'live_tests': 'not run by this command',
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(f"{report['status'].upper()}: {report['passed']}/{result.testsRun} passed; report: {args.output}")
    for item in report['failures'] + report['errors']:
        print(item['test'])
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
