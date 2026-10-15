from copy import deepcopy
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import tempfile
import unittest
import subprocess
import sys
from unittest.mock import patch

from jsonschema import ValidationError

from ucl.match import command, run_match, run_process, validate_config
from ucl.records import new_record, validate_record, write_json, sha256, utc_now
from ucl.integrity import validate_bundle
from ucl.report import summarize_pgn

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "experiments/configs/smoke.json").read_text())
SCHEMA = json.loads((ROOT / "schemas/experiment-v1.schema.json").read_text())


class ExperimentTests(unittest.TestCase):
    def test_configuration_and_argument_boundaries(self):
        validate_config(CONFIG)
        args = command(CONFIG, [PureWindowsPath("C:/engine one.exe"), PurePosixPath("/engine two")],
                       PurePosixPath("/fastchess"), PurePosixPath("/run/games.pgn"))
        self.assertIn(r"cmd=C:\engine one.exe", args)
        self.assertIn("cmd=/engine two", args)
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

    def test_bundle_integrity_and_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "bundle"
            config = deepcopy(CONFIG)
            for e in config["engines"]:
                e["ucl_build_info"] = False
                e["path"] = sys.executable
            source = Path(tmp) / "input.json"
            write_json(source, config)

            def fake_match(args, directory, log, timeout):
                # Reproduce fastchess's filename collision.
                write_json(directory / "config.json", {"fastchess": "generated"})
                text = ""
                a, b = [e["name"] for e in config["engines"]]
                for rnd in (1, 2):
                    for white, black in ((a, b), (b, a)):
                        text += f'[Round "{rnd}"]\n[White "{white}"]\n[Black "{black}"]\n[Result "1/2-1/2"]\n[Termination "adjudication"]\n\n1. e4 1/2-1/2\n\n'
                (directory / "games.pgn").write_text(text)
                return 0

            check_output = subprocess.check_output
            def output_for(args, **kwargs):
                return "fake-fastchess" if args[-1] == "--version" else check_output(args, **kwargs)

            with patch("ucl.match.run_process", side_effect=fake_match), patch(
                    "ucl.match.subprocess.check_output", side_effect=output_for):
                record = run_match(ROOT, source, output, fastchess=sys.executable, allow_dirty=True)
            self.assertEqual(record["status"], "completed", record["error"])
            self.assertEqual(json.loads((output / "match-config.json").read_text()), config)
            path = output / "record.json"
            validate_bundle(path, SCHEMA)
            for name in record["artifacts"]:
                artifact = output / name
                original = artifact.read_bytes()
                artifact.write_bytes(original + b"tampered")
                with self.assertRaisesRegex(ValueError, "integrity"):
                    validate_bundle(path, SCHEMA)
                artifact.write_bytes(original)
            for mutate in (lambda r: r["results"].update(wins=1),
                           lambda r: r["results"].update(score_ci95_paired_bootstrap=[0, 1]),
                           lambda r: r.update(seed=0),
                           lambda r: r["engines"][0].update(revision="b" * 40),
                           lambda r: r["artifacts"].pop("games.pgn"),
                           lambda r: r["artifacts"].update({"../outside": {"sha256": "a" * 64, "bytes": 0}})):
                bad = deepcopy(record); mutate(bad); write_json(path, bad)
                with self.assertRaises(ValueError):
                    validate_bundle(path, SCHEMA)
            write_json(path, record)
            pgn = output / "games.pgn"
            pgn.write_text(pgn.read_text().replace('1. e4 1/2-1/2', '1. e4 1-0', 1))
            record["artifacts"]["games.pgn"] = {"sha256": sha256(pgn), "bytes": pgn.stat().st_size}
            write_json(path, record)
            with self.assertRaisesRegex(ValueError, "result mismatch"):
                validate_bundle(path, SCHEMA)

    def test_timeout_stops_process(self):
        with tempfile.TemporaryDirectory() as tmp:
            with (Path(tmp) / "log.txt").open("w") as log:
                with self.assertRaises(subprocess.TimeoutExpired):
                    run_process([sys.executable, "-c", "import time; time.sleep(30)"], tmp, log, 0.05)


if __name__ == "__main__":
    unittest.main()
