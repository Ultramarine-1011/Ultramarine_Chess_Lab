from copy import deepcopy
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import tempfile
import unittest
import subprocess
import sys
from unittest.mock import patch

from jsonschema import ValidationError

from ucl.match import command, capture_engine, run_match, run_process, validate_config, validate_comparison
from ucl.records import new_record, prepare_output, validate_record, write_json, sha256
from ucl.integrity import validate_bundle
from ucl.report import summarize_pgn
from ucl.benchmark import uci_score_cp

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import elo

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
            # New runs retain one compressed-file hash in artifacts.
            record['artifacts']['engine.log.gz']={}
            record['tools']['telemetry']={'file':'engine.log.gz'}
            validate_telemetry(record,p)

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

    def test_r5_paired_statistics_and_real_node_trace(self):
        from ucl.r5_analysis import bootstrap, trace_queries
        sample = [0, .25, .5, .75, 1]
        a = bootstrap(sample)
        self.assertEqual(a, bootstrap(sample))
        self.assertEqual(a['score'], .5)
        self.assertLessEqual(a['ci98_75_bonferroni_four'][0], a['ci95'][0])
        self.assertGreaterEqual(a['ci98_75_bonferroni_four'][1], a['ci95'][1])
        directory = ROOT/'experiments/results/r5-preflight-v2-b'
        queries, options = trace_queries(directory, ['OriginalFull14', 'Handcrafted'])
        self.assertEqual(sum(map(len, queries.values())), 12)
        self.assertEqual(options['OriginalFull14']['Evaluator'], 'Linear')
        self.assertTrue(all(q['stats']['nodes']==50000 and 'nodes 50000' in q['go']
                            for rows in queries.values() for q in rows))
        with self.assertRaises(ValueError): trace_queries(directory, ['OriginalFull14'])

    def test_node_stop_reason_with_claimable_next_move(self):
        import chess
        from ucl.r5_analysis import node_stop_reason
        board = chess.Board()
        for move in 'g1f3 g8f6 f3g1 f6g8 g1f3 g8f6 f3g1'.split():
            board.push_uci(move)
        self.assertTrue(board.can_claim_threefold_repetition())
        self.assertFalse(board.is_repetition(3))
        self.assertEqual(node_stop_reason({'depth': 128, 'nodes': 256, 'score_cp': 0}, board), 'max_depth')
        self.assertIsNone(node_stop_reason({'depth': 5, 'nodes': 9000, 'score_cp': 0}, board))
        self.assertEqual(node_stop_reason({'depth': 4, 'nodes': 100, 'score_cp': 29997}, board), 'mate_proven')
        board.push_uci('f6g8')
        self.assertTrue(board.is_repetition(3))
        self.assertEqual(node_stop_reason({'depth': 0, 'nodes': 0, 'score_cp': 0}, board), 'root_draw')

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
                               fastchess="/missing/ucl-fastchess")
            self.assertEqual(record["status"], "failed")
            validate_record(json.loads((output / "record.json").read_text()), SCHEMA)
            self.assertTrue((output / "report.md").exists())
            with self.assertRaises(FileExistsError):
                run_match(ROOT, ROOT / "experiments/configs/smoke.json", output)
            # Ordinary dirty runs can retry in place, including after failure.
            record = run_match(ROOT, ROOT / "experiments/configs/smoke.json", output,
                               fastchess="/missing/ucl-fastchess", overwrite=True)
            self.assertEqual(record['mode'], 'exploratory')
            self.assertEqual(record['status'], 'failed')

    def test_overwrite_preserves_archived_and_tracked_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            subprocess.run(['git','init',str(root)],check=True,capture_output=True)
            output=root/'run'
            prepare_output(root,output)
            for record in ({'status':'failed'}, {'mode':'formal'}):
                write_json(output/'record.json',record)
                with self.assertRaisesRegex(ValueError,'only exploratory'):
                    prepare_output(root,output,overwrite=True)
            write_json(output/'record.json',{'mode':'exploratory'})
            subprocess.run(['git','-C',str(root),'add','run/record.json'],check=True)
            with self.assertRaisesRegex(ValueError,'tracked'):
                prepare_output(root,output,overwrite=True)
            self.assertTrue((output/'record.json').exists())

    def test_build_provenance_is_recorded_without_blocking_exploration(self):
        engine={**CONFIG['engines'][0], 'path':sys.executable, 'ucl_build_info':True}
        info={'revision':'a'*40,'dirty':True}
        with patch('ucl.match.subprocess.check_output',return_value=json.dumps(info)):
            entry=capture_engine(ROOT,engine,'b'*40)
            self.assertEqual(entry['revision'],info['revision'])
            self.assertEqual(entry['build_info'],info)
            with self.assertRaisesRegex(ValueError,'formal comparison'):
                capture_engine(ROOT,engine,'b'*40,formal=True)

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
                record = run_match(ROOT, source, output, fastchess=sys.executable)
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


class DailyEloTests(unittest.TestCase):
    def test_defaults_and_unlimited_search(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(elo, "STATE", Path(tmp)):
            with patch.object(elo, "baseline_binary", return_value=("a" * 40, Path("baseline"))) as baseline, \
                    patch.object(elo, "build_candidate", return_value=Path("candidate")), \
                    patch.object(elo, "executable", return_value=Path(sys.executable)), \
                    patch.object(elo, "run_match", return_value={"status": "failed", "error": "test stop"}) as match:
                with self.assertRaises(SystemExit) as stopped:
                    elo.main([])
                self.assertEqual(stopped.exception.code, 1)
            self.assertEqual(baseline.call_args.args, ("HEAD",))
            config = json.loads((Path(tmp) / "match.json").read_text())
            self.assertEqual((config["rounds"], config["games"], config["tc"], config["concurrency"]),
                             (64, 2, "2+0.02", 4))
            self.assertEqual(config["engines"][0]["revision"], "HEAD")
            self.assertEqual(config["engines"][1]["revision"], "a" * 40)
            self.assertTrue(match.call_args.kwargs["overwrite"])
            self.assertNotIn("depth", config)
            self.assertNotIn("nodes", config)
            validate_config(config)
            args = command(config, ["candidate", "baseline"], "fastchess", "games.pgn", elo.OPENINGS)
            self.assertFalse(any(a.startswith(("depth=", "nodes=")) for a in args))

    def test_baseline_cache_and_set_baseline(self):
        with tempfile.TemporaryDirectory(prefix="ucl elo ") as tmp, patch.object(elo, "STATE", Path(tmp)):
            full = "b" * 40
            def build(revision, output):
                output.mkdir(parents=True)
                binary = output / elo.BINARY
                binary.write_bytes(b"cached baseline")
                write_json(output / "manifest.json", {"sha256": sha256(binary), "build_info": {
                    "revision": revision, "dirty": False, "build_type": "Release"}})
            with patch.object(elo.subprocess, "check_output", return_value=full), \
                    patch.object(elo, "build_revision", side_effect=build) as builder, \
                    patch.object(elo, "build_candidate") as candidate, patch.object(elo, "run_match") as match:
                elo.main(["--set-baseline", "HEAD~1"])
                _, binary = elo.baseline_binary(full)
                builder.assert_called_once()
                candidate.assert_not_called()
                match.assert_not_called()
                self.assertEqual(json.loads((Path(tmp) / "baseline.json").read_text()), {"revision": full})
                binary.write_bytes(b"corrupted")
                with self.assertRaisesRegex(ValueError, "cache mismatch"):
                    elo.baseline_binary(full)
                builder.assert_called_once()

    def test_candidate_reconfigures_and_builds_incrementally(self):
        info = {"revision": "a" * 40, "dirty": True, "build_type": "Release"}
        with tempfile.TemporaryDirectory(prefix="ucl elo ") as tmp, patch.object(elo, "STATE", Path(tmp)):
            binary = Path(tmp) / "candidate-build" / elo.BINARY
            binary.parent.mkdir()
            binary.write_bytes(b"dirty workspace binary")
            with patch.object(elo.subprocess, "check_output", return_value=json.dumps(info)), \
                    patch.object(elo.subprocess, "run") as run:
                self.assertEqual(elo.build_candidate(), binary)
                self.assertEqual(elo.build_candidate(), binary)
                self.assertEqual(run.call_count, 4)
                self.assertEqual([c.args for c in run.call_args_list[:2]],
                                 [c.args for c in run.call_args_list[2:]])
                commands = [c.args[0] for c in run.call_args_list[:2]]
                self.assertIn("-DCMAKE_BUILD_TYPE=Release", commands[0])
                self.assertIn("--build", commands[1])
                self.assertNotIn("--clean-first", commands[1])
            self.assertEqual(json.loads((Path(tmp) / "candidate.json").read_text())["build_info"], info)

    def test_arguments_reject_invalid_values_before_build(self):
        with patch.object(elo, "build_candidate") as build:
            for args in (["--games", "3"], ["--games", "0"], ["--concurrency", "0"],
                         ["--tc", "0+0"], ["--tc", "nan"], ["--tc", "2+inf"]):
                with self.subTest(args=args), self.assertRaises(SystemExit) as failed:
                    elo.main(args)
                self.assertEqual(failed.exception.code, 2)
            build.assert_not_called()
        config = elo.match_config(Path("C:/candidate with spaces.exe"), Path("baseline"), "a" * 40,
                                  8, elo.time_control("0:02+0.02"), 2)
        self.assertEqual((config["rounds"], config["tc"], config["concurrency"]), (4, "0:02+0.02", 2))

    def test_elo_uses_existing_paired_score_interval_and_boundary_scores(self):
        from ucl.report import elo_equivalent
        from ucl.r4_results import elo_equivalent as historical_elo
        self.assertIs(elo_equivalent, historical_elo)
        r = {"candidate": "Candidate", "baseline": "Baseline", "wins": 5, "draws": 2, "losses": 1,
             "games": 8, "score": .75, "paired_rounds": 4,
             "score_ci95_paired_bootstrap": [.25, .9], "interpretation": "development"}
        record = {"id": "test", "code": {"revision": "a" * 40, "dirty": True}, "results": r}
        text = elo.result_report(record)
        self.assertIn("W/D/L: 5/2/1; score: 75.00%", text)
        self.assertIn("Relative Elo: +190.85", text)
        self.assertIn("95% CI: [-190.85, +381.70]", text)
        r.update(score=0, score_ci95_paired_bootstrap=[0, 1])
        self.assertIn("Relative Elo: -inf", elo.result_report(record))
        self.assertIn("95% CI: [-inf, +inf]", elo.result_report(record))
        r.update(score=1, score_ci95_paired_bootstrap=None)
        self.assertIn("Relative Elo: +inf", elo.result_report(record))
        self.assertIn("unavailable (fewer than two pairs)", elo.result_report(record))

    def test_development_openings_are_legal_unique_and_separate(self):
        import chess
        positions = elo.OPENINGS.read_text().splitlines()
        metadata = json.loads(elo.OPENINGS.with_suffix(".json").read_text())
        self.assertEqual(sha256(elo.OPENINGS), metadata["sha256"])
        self.assertEqual(len(positions), metadata["positions"])
        self.assertEqual(len(set(positions)), len(positions))
        self.assertGreaterEqual(len(positions), 64)
        white_to_move = 0
        for position in positions:
            board = chess.Board(position + " 0 1")
            self.assertTrue(board.is_valid())
            self.assertFalse(board.is_game_over())
            white_to_move += board.turn
        self.assertEqual(white_to_move * 2, len(positions))
        for other in (ROOT / "experiments").rglob("*.epd"):
            if other == elo.OPENINGS:
                continue
            old = {" ".join(line.split()[:4]) for line in other.read_text().splitlines() if line.strip()}
            self.assertFalse(set(positions) & old, str(other))


if __name__ == "__main__":
    unittest.main()
