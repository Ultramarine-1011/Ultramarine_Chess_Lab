from copy import deepcopy
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import tempfile
import unittest
import subprocess
import sys
from unittest.mock import patch

from jsonschema import ValidationError

from ucl.match import command, run_match, run_process, validate_config, validate_comparison
from ucl.records import new_record, validate_record, write_json, sha256, utc_now
from ucl.integrity import validate_bundle
from ucl.report import summarize_pgn
from ucl.benchmark import uci_score_cp

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
        telemetry={**CONFIG,'pgn_telemetry':True}
        validate_config(telemetry)
        detailed=command(telemetry,[Path('/engine1'),Path('/engine2')],Path('/fastchess'),Path('/run/games.pgn'))
        for item in ('nodes=true','nps=true','-log',f"file={Path('/run')/'engine.log'}",'engine=true'):
            self.assertIn(item,detailed)
        for field, value in (("rounds", 0), ("games", 1), ("seed", -1), ("depth", True), ('pgn_telemetry',1)):
            bad = deepcopy(CONFIG); bad[field] = value
            with self.assertRaises(ValueError):
                validate_config(bad)

    def test_compressed_raw_telemetry_integrity(self):
        import gzip,hashlib
        from ucl.match import validate_telemetry
        raw=b'engine raw protocol\n'
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'engine.log.gz').write_bytes(gzip.compress(raw,mtime=0))
            record={'parameters':{'pgn_telemetry':True},'artifacts':{'engine.log.gz':{}},
                    'tools':{'telemetry':{'file':'engine.log.gz','raw_bytes':len(raw),'raw_sha256':hashlib.sha256(raw).hexdigest()}}}
            validate_telemetry(record,p)
            record['tools']['telemetry']['raw_bytes']+=1
            with self.assertRaisesRegex(ValueError,'raw telemetry'):validate_telemetry(record,p)
            record['artifacts'].clear()
            with self.assertRaisesRegex(ValueError,'missing match telemetry'):validate_telemetry(record,p)

    def test_failed_prefix_requires_explicit_opt_in(self):
        import shutil
        source=ROOT/'experiments/results/r4-telemetry-smoke'
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'prefix';shutil.copytree(source,p)
            record=json.loads((p/'record.json').read_text())
            record['status']='failed';record['error']='simulated protocol warning';record['results']=None
            record['parameters']['rounds']=3
            write_json(p/'match-config.json',record['parameters'])
            record['artifacts']['match-config.json']={'sha256':sha256(p/'match-config.json'),'bytes':(p/'match-config.json').stat().st_size}
            write_json(p/'record.json',record)
            before=(p/'record.json').read_bytes()
            with self.assertRaisesRegex(ValueError,'failed'):validate_bundle(p/'record.json',SCHEMA)
            checked=validate_bundle(p/'record.json',SCHEMA,completed_prefix_games=4)
            self.assertEqual(checked['status'],'failed')
            self.assertEqual(checked['tools']['completed_prefix']['results']['paired_rounds'],2)
            self.assertEqual(before,(p/'record.json').read_bytes())
            for count in (2,3,6):
                with self.assertRaises(ValueError):validate_bundle(p/'record.json',SCHEMA,completed_prefix_games=count)

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
            self.assertNotIn(b'\r\n', path.read_bytes())
            self.assertEqual(len(list(Path(tmp).iterdir())), 1)

    def test_r5_windows_bundles_preserve_hashed_bytes(self):
        for group in 'abcd':
            path = ROOT / f'experiments/results/r5-preflight-v2-{group}/record.json'
            self.assertEqual(validate_bundle(path, SCHEMA)['status'], 'completed')

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

    def test_revision_and_ablation_identity_guards(self):
        a = {"revision": "a" * 40, "sha256": "1" * 64, "options": {},
             "build_info": {"revision": "a" * 40, "dirty": False, "compiler": "same", "build_type": "Release", "flags": "-O3"}}
        b = deepcopy(a)
        with self.assertRaisesRegex(ValueError, "distinct"):
            validate_comparison({"comparison": "revision"}, [a, b])
        b["revision"] = "b" * 40
        with self.assertRaisesRegex(ValueError, "distinct"):
            validate_comparison({"comparison": "revision"}, [a, b])
        b["sha256"] = "2" * 64
        validate_comparison({"comparison": "revision"}, [a, b])
        b["build_info"]["flags"] = "-O0"
        with self.assertRaisesRegex(ValueError, "build control"):
            validate_comparison({"comparison": "revision"}, [a, b])
        b = deepcopy(a)
        with self.assertRaisesRegex(ValueError, "different explicit options"):
            validate_comparison({"comparison": "ablation"}, [a, b])
        b["options"] = {"UseTT": False}
        validate_comparison({"comparison": "ablation"}, [a, b])

    def test_uci_mate_moves_to_ply_score(self):
        import chess.engine
        for score, expected in ((chess.engine.Cp(-42), -42), (chess.engine.Mate(1), 29999),
                                (chess.engine.Mate(2), 29997), (chess.engine.Mate(-1), -29998),
                                (chess.engine.Mate(-2), -29996), (chess.engine.Mate(0), -30000),
                                (chess.engine.MateGiven, 30000)):
            self.assertEqual(uci_score_cp(score), expected)

    def test_timeout_stops_process(self):
        with tempfile.TemporaryDirectory() as tmp:
            with (Path(tmp) / "log.txt").open("w") as log:
                with self.assertRaises(subprocess.TimeoutExpired):
                    run_process([sys.executable, "-c", "import time; time.sleep(30)"], tmp, log, 0.05)


if __name__ == "__main__":
    unittest.main()
