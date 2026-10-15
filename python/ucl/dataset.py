"""Bounded real-PGN acquisition and deterministic game-grouped R3 datasets."""
import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import io
import json
from pathlib import Path
import urllib.request

import chess
import chess.pgn

from .records import sha256, write_json, utc_now
from .report import CheckedGameBuilder, check_game_result

SEED = 20261015
SOURCE = "https://database.lichess.org/standard/lichess_db_standard_rated_2017-01.pgn.zst"


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def position_key(board):
    a = " ".join(board.fen().split()[:4])
    b = " ".join(board.mirror().fen().split()[:4])
    return digest(min(a, b))


def split_for(game_id, seed=SEED):
    bucket = int(digest(f"{seed}:{game_id}")[:8], 16) % 100
    return "train" if bucket < 70 else "validation" if bucket < 85 else "test"


def prepare(pgn_text, seed=SEED):
    counts, games, rows = Counter(), {}, []
    stream = io.StringIO(pgn_text)
    while True:
        try:
            game = chess.pgn.read_game(stream, Visitor=CheckedGameBuilder)
        except ValueError:
            counts["invalid_pgn"] += 1
            continue
        if game is None:
            break
        counts["source_games"] += 1
        try:
            check_game_result(game)
            h = game.headers
            if h.get("Variant", "Standard") != "Standard" or game.board().fen() != chess.STARTING_FEN:
                raise ValueError("nonstandard")
            if h.get("Termination", "").lower() != "normal":
                raise ValueError("termination")
            if h.get("White") == h.get("Black"):
                raise ValueError("self_play")
            if min(int(h.get("WhiteElo", "0")), int(h.get("BlackElo", "0"))) < 1500:
                raise ValueError("rating")
            if int(h.get("TimeControl", "0+0").split("+")[0]) < 180:
                raise ValueError("time_control")
            moves = list(game.mainline_moves())
            if len(moves) < 32:
                raise ValueError("short_game")
        except (ValueError, TypeError) as exc:
            counts[f"reject:{exc}"] += 1
            continue
        gid = digest(game.board().fen() + " " + " ".join(m.uci() for m in moves))
        if gid in games:
            counts["duplicate_game"] += 1
            continue
        split = split_for(gid, seed)
        games[gid] = {"split": split, "site": h.get("Site"), "plies": len(moves), "result": h["Result"]}
        label = {"1-0": 1.0, "1/2-1/2": 0.5, "0-1": 0.0}[h["Result"]]
        board, positions = game.board(), []
        for ply, move in enumerate(moves, 1):
            if move not in board.legal_moves:
                raise ValueError("unvalidated move")
            board.push(move)
            if 16 <= ply <= 160 and ply % 8 == 0 and not board.is_game_over(claim_draw=True):
                positions.append({"position_id": position_key(board), "game_id": gid,
                                  "fen": board.fen(), "ply": ply, "label": label, "split": split,
                                  "feature_version": "handcrafted-v1"})
        positions.sort(key=lambda r: digest(f"{seed}:{gid}:{r['ply']}"))
        rows.extend(positions[:8])
    memberships = defaultdict(set)
    for row in rows:
        memberships[row["position_id"]].add(row["split"])
    seen, clean = set(), []
    for row in sorted(rows, key=lambda r: (r["game_id"], r["ply"])):
        pid = row["position_id"]
        if len(memberships[pid]) > 1:
            counts["cross_split_position_removed"] += 1
        elif pid in seen:
            counts["duplicate_position_removed"] += 1
        else:
            clean.append(row)
            seen.add(pid)
    counts["accepted_games"] = len(games)
    counts["positions_before_dedup"] = len(rows)
    counts["positions"] = len(clean)
    counts.update({f"positions:{s}": sum(r["split"] == s for r in clean) for s in ("train", "validation", "test")})
    return clean, games, dict(counts)


def write_gzip(path, text):
    # Stable gzip metadata, independent of host/path/current time.
    Path(path).write_bytes(gzip.compress(text.encode(), mtime=0))


def acquire(output, max_bytes=2097152, max_games=3000):
    import zstandard
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    request = urllib.request.Request(SOURCE, headers={"Range": f"bytes=0-{max_bytes-1}", "User-Agent": "UCL-R3-research/1"})
    with urllib.request.urlopen(request, timeout=60) as response:
        raw = response.read(max_bytes + 1)
        if response.status != 206 or len(raw) > max_bytes:
            raise ValueError("server did not honor bounded Range request")
        headers = dict(response.headers)
    (output / "source-prefix.pgn.zst").write_bytes(raw)
    with zstandard.ZstdDecompressor().stream_reader(io.BytesIO(raw)) as reader:
        text = reader.read(32 * 1024 * 1024).decode("utf-8")
    blocks = text.split('\n\n[Event ')
    # Always discard last possibly truncated game.
    selected = '\n\n[Event '.join(blocks[:min(max_games, len(blocks)-1)]).rstrip() + '\n\n'
    write_gzip(output / "source.pgn.gz", selected)
    rows, games, counts = prepare(selected)
    write_gzip(output / "positions.jsonl.gz", ''.join(json.dumps(r, sort_keys=True) + '\n' for r in rows))
    write_json(output / "splits.json", games)
    manifest = {"schema_version": 1, "kind": "r3-dataset", "seed": SEED,
                "source": {"url": SOURCE, "license": "CC0-1.0", "license_url": "https://database.lichess.org/",
                           "acquired_at": utc_now(), "range": [0, max_bytes-1], "headers": headers},
                "protocol": "docs/r3/protocol.md", "counts": counts,
                "split_games": dict(Counter(g["split"] for g in games.values())),
                "files": {name: {"sha256": sha256(output / name), "bytes": (output / name).stat().st_size}
                          for name in ("source-prefix.pgn.zst", "source.pgn.gz", "positions.jsonl.gz", "splits.json")}}
    write_json(output / "manifest.json", manifest)
    return manifest


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    print(json.dumps(acquire(args.output), indent=2))


if __name__ == "__main__":
    main()


def validate_dataset(directory):
    """Rebuild splits and positions from retained real PGN, checking every hash."""
    directory = Path(directory)
    manifest = json.loads((directory / 'manifest.json').read_text())
    if manifest['schema_version'] != 1 or manifest['kind'] != 'r3-dataset':
        raise ValueError('dataset schema mismatch')
    for name, meta in manifest['files'].items():
        if Path(name).name != name:
            raise ValueError('unsafe dataset artifact path')
        path = directory / name
        if sha256(path) != meta['sha256'] or path.stat().st_size != meta['bytes']:
            raise ValueError('dataset artifact integrity mismatch: ' + name)
    rows, games, counts = prepare(gzip.decompress((directory / 'source.pgn.gz').read_bytes()).decode(), manifest['seed'])
    actual = [json.loads(line) for line in gzip.decompress((directory / 'positions.jsonl.gz').read_bytes()).decode().splitlines()]
    if rows != actual or games != json.loads((directory / 'splits.json').read_text()) or counts != manifest['counts']:
        raise ValueError('dataset reconstruction mismatch')
    return manifest
