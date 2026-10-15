from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
import subprocess
import sys
from unittest.mock import patch

from jsonschema import ValidationError

from ucl.match import command, run_match, run_process, validate_config
from ucl.records import new_record, validate_record, write_json
from ucl.report import summarize_pgn

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "experiments/configs/smoke.json").read_text())
SCHEMA = json.loads((ROOT / "schemas/experiment-v1.schema.json").read_text())


class ExperimentTests(unittest.TestCase):
    def test_configuration_and_argument_boundaries(self):
        validate_config(CONFIG)
        args = command(CONFIG, [Path("/engine one"), Path("/engine two")], Path("/fastchess"), Path("/run/games.pgn"))
        self.assertIn("cmd=/engine one", args)
        self.assertIn("-srand", args)
        self.assertIn("-strict", args)
        for field, value in (("rounds", 0), ("games", 1), ("seed", -1), ("depth", True)):
            bad = deepcopy(CONFIG); bad[field] = value
            with self.assertRaises(ValueError):
                validate_config(bad)

    def test_schema_and_atomic_json(self):
        with patch("ucl.records.git_state", return_value={"revision": "a" * 40, "dirty": False}):
            record = new_record(ROOT, CONFIG)
        validate_record(record, SCHEMA)
        for bad in ({**record, "seed": "wrong"}, {**record, "status": "completed"}, {**record, "surprise": 1}):
            with self.assertRaises(ValidationError):
                validate_record(bad, SCHEMA)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "record.json"
            write_json(path, record)
            self.assertEqual(json.loads(path.read_text()), record)
            self.assertEqual(len(list(Path(tmp).iterdir())), 1)

    def test_pgn_pair_statistics_and_truncation(self):
        with tempfile.TemporaryDirectory() as tmp:
            pgn = Path(tmp) / "games.pgn"
            text = ""
            for rnd in (1, 2):
                for white, black, result in (("A", "B", "1-0"), ("B", "A", "0-1")):
                    text += f'[Round "{rnd}"]\n[White "{white}"]\n[Black "{black}"]\n[Result "{result}"]\n\n1. e4 {result}\n\n'
            pgn.write_text(text)
            r = summarize_pgn(pgn, "A", "B", 4, seed=7)
            self.assertEqual((r["wins"], r["paired_rounds"], r["score"]), (4, 2, 1.0))
            self.assertEqual(r["score_ci95_paired_bootstrap"], [1.0, 1.0])
            self.assertEqual(r, summarize_pgn(pgn, "A", "B", 4, seed=7))
            with self.assertRaises(ValueError):
                summarize_pgn(pgn, "A", "B", 6)
            pgn.write_text(text.replace('[Result "1-0"]', '[Result "*"]', 1).replace('1. e4 1-0', '1. e4 *', 1))
            with self.assertRaises(ValueError):
                summarize_pgn(pgn, "A", "B")

    def test_failed_runner_retains_valid_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "failed"
            # A missing executable fails before any external process is launched.
            record = run_match(ROOT, ROOT / "experiments/configs/smoke.json", output,
                               fastchess="/missing/ucl-fastchess", allow_dirty=True)
            self.assertEqual(record["status"], "failed")
            validate_record(json.loads((output / "record.json").read_text()), SCHEMA)
            self.assertTrue((output / "report.md").exists())
            with self.assertRaises(FileExistsError):
                run_match(ROOT, ROOT / "experiments/configs/smoke.json", output, allow_dirty=True)

    def test_timeout_stops_process(self):
        with tempfile.TemporaryDirectory() as tmp:
            with (Path(tmp) / "log.txt").open("w") as log:
                with self.assertRaises(subprocess.TimeoutExpired):
                    run_process([sys.executable, "-c", "import time; time.sleep(30)"], tmp, log, 0.05)


if __name__ == "__main__":
    unittest.main()
