#!/usr/bin/env python3
"""Offline unit-test fixtures only; these are NOT Harbor trial results."""
import json
import tempfile
import unittest
import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from check_declared_budget import check
from experiment_report import summarize, WEIGHTS
from groq_preflight import disabled_oversized_probe, cmd_budget


class EvidenceTests(unittest.TestCase):
    def test_budget_requires_fresh_sufficient_observation(self):
        now = datetime.now(timezone.utc)
        self.assertEqual(check(1000, now.isoformat(), now), 199000)
        for used, stamp in [(196407, now), (0, now - timedelta(hours=2)),
                            (-1, now), (0, now + timedelta(seconds=10))]:
            with self.assertRaises(ValueError):
                check(used, stamp.isoformat(), now)

    def test_oversized_commands_never_call_provider(self):
        with patch('groq_preflight.request', side_effect=AssertionError('network forbidden')):
            self.assertEqual(disabled_oversized_probe(None), 4)

    def test_missing_smoke_usage_stops(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = argparse.Namespace(smoke_summary=None, jobs_root=Path(tmp),
                                      daily_limit=200000, already_used=0,
                                      trials=6, safety=1.3, output=None)
            self.assertEqual(cmd_budget(args), 4)

    def test_report_and_rejection_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for i, flags in enumerate([(True, True, False), (True, False, False), (False, False, False)]):
                trial = root / str(i)
                (trial / 'verifier').mkdir(parents=True)
                (trial / 'agent').mkdir()
                checks = dict(zip(WEIGHTS, flags))
                dense = round(sum(WEIGHTS[k] for k, v in checks.items() if v), 2)
                (trial / 'result.json').write_text(json.dumps({'verifier_result': {'rewards': {'reward': 0}}}))
                (trial / 'verifier/details.json').write_text(json.dumps({'checks': checks, 'weights': WEIGHTS, 'reward': dense}))
                (trial / 'verifier/candidate.py').write_text('# test fixture only\n')
                (trial / 'agent/trajectory.json').write_text(json.dumps({'steps': [{'test_fixture': True}]}))
            report = summarize(root)
            self.assertAlmostEqual(report['means']['dense'], .7 / 3)
            self.assertEqual(report['means']['binary'], 0)
            self.assertAlmostEqual(sum(t['dense_advantage'] for t in report['trials']), 0)
            (root / '0/verifier/candidate.py').unlink()
            with self.assertRaises(FileNotFoundError):
                summarize(root)
            (root / '0/result.json').write_text(json.dumps({'exception_info': {'exception_type': 'RateLimitError'}}))
            with self.assertRaises(ValueError):
                summarize(root)


if __name__ == '__main__':
    unittest.main()
