"""PGN validation and descriptive statistics; paired bootstrap resamples rounds."""
import math
from pathlib import Path
import random
import statistics

import chess.pgn


class CheckedGameBuilder(chess.pgn.GameBuilder):
    def visit_result(self, result):
        if self.game.headers.get("Result", "*") != result:
            raise ValueError("PGN header/movetext result mismatch")
        super().visit_result(result)


def summarize_pgn(path, candidate, baseline, expected_games=None, seed=0, samples=2000):
    outcomes, pairs = [], {}
    terminations = {}
    with Path(path).open(encoding="utf-8") as stream:
        while (game := chess.pgn.read_game(stream, Visitor=CheckedGameBuilder)) is not None:
            if game.errors:
                raise ValueError(f"invalid PGN: {game.errors[0]}")
            white, black = game.headers["White"], game.headers["Black"]
            if {white, black} != {candidate, baseline}:
                raise ValueError("PGN engine names do not match configuration")
            result = game.headers["Result"]
            if result not in ("1-0", "0-1", "1/2-1/2"):
                raise ValueError("unfinished game")
            score = 0.5 if result == "1/2-1/2" else float((result == "1-0") == (white == candidate))
            outcomes.append(score)
            # fastchess writes one Round value per color-swapped pair.
            round_id = game.headers.get("Round", "?")
            pairs.setdefault(round_id, []).append((white, score, game.board().fen()))
            final = game.end().board()
            outcome = final.outcome(claim_draw=True)
            if outcome is not None and outcome.result() != result:
                raise ValueError("PGN result contradicts terminal board")
            reason = game.headers.get("Termination", "unknown")
            terminations[reason] = terminations.get(reason, 0) + 1
    if not outcomes or (expected_games is not None and len(outcomes) != expected_games):
        raise ValueError(f"expected {expected_games} games, found {len(outcomes)}")
    paired = all(len(p) == 2 and {w for w, _, _ in p} == {candidate, baseline} and p[0][2] == p[1][2] for p in pairs.values())
    ci = None
    if paired and len(pairs) >= 2:
        means = [statistics.mean(s for _, s, _ in pair) for pair in pairs.values()]
        rng = random.Random(seed)
        boot = sorted(statistics.mean(rng.choices(means, k=len(means))) for _ in range(samples))
        ci = [boot[math.floor(0.025 * (samples - 1))], boot[math.ceil(0.975 * (samples - 1))]]
    counts = [0] * 5
    if paired:
        for pair in pairs.values():
            counts[int(2 * sum(s for _, s, _ in pair))] += 1
    return {"paired_score_counts": counts if paired else None, "candidate": candidate, "baseline": baseline, "games": len(outcomes),
            "wins": outcomes.count(1.0), "draws": outcomes.count(0.5), "losses": outcomes.count(0.0),
            "score": statistics.mean(outcomes), "paired_rounds": len(pairs) if paired else 0,
            "score_ci95_paired_bootstrap": ci, "bootstrap_seed": seed,
            "terminations": terminations,
            "interpretation": "Descriptive smoke/baseline statistics; not evidence of Elo improvement."}


def markdown_report(record):
    r = record["results"]
    if r is None:
        return f"# UCL experiment {record['id']}\n\nStatus: {record['status']}\n\n{record['error'] or ''}\n"
    return (f"# UCL experiment {record['id']}\n\n"
            f"Revision: `{record['code']['revision']}`; dirty: `{record['code']['dirty']}`\n\n"
            f"{r['candidate']} vs {r['baseline']}: {r['wins']} W / {r['draws']} D / {r['losses']} L "
            f"({r['games']} games), score {r['score']:.3f}.\n\n"
            f"Paired rounds: {r['paired_rounds']}; paired bootstrap score CI95: "
            f"{r['score_ci95_paired_bootstrap']}.\n\n"
            f"Pair scores (0, 0.5, 1, 1.5, 2): {r.get('paired_score_counts', 'not retained')}.\n\n{r['interpretation']}\n")
