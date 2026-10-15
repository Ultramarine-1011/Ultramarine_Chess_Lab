"""PGN validation and descriptive statistics; paired bootstrap resamples rounds."""
import math
from pathlib import Path
import random
import statistics

import chess.pgn


class CheckedGameBuilder(chess.pgn.GameBuilder):
    def begin_game(self):
        self.saw_result = False
        return super().begin_game()

    def end_game(self):
        if not self.saw_result:
            raise ValueError("missing PGN movetext result")
        super().end_game()

    def visit_result(self, result):
        self.saw_result = True
        if self.game.headers.get("Result", "*") != result:
            raise ValueError("PGN header/movetext result mismatch")
        super().visit_result(result)


def check_game_result(game, require_natural=False):
    """Check forced board outcomes; external resignations/adjudications stay distinct."""
    result = game.headers.get("Result")
    if game.errors or result not in ("1-0", "0-1", "1/2-1/2"):
        raise ValueError("invalid or unfinished PGN")
    final = game.end().board()
    forced = final.outcome(claim_draw=False)
    if forced is not None and forced.result() != result:
        raise ValueError("PGN result contradicts terminal board")
    if require_natural and game.headers.get("Termination") == "normal":
        outcome = final.outcome(claim_draw=True)
        if outcome is None or outcome.result() != result:
            raise ValueError("natural termination contradicts final board")
    return final


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
            check_game_result(game, require_natural=True)
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
