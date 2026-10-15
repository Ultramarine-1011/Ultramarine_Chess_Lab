#include "ucl/evaluator.hpp"
#include "ucl/position.hpp"
#include "ucl/search.hpp"
#include "ucl/transposition.hpp"
#include <algorithm>
#include <iostream>
#include <random>
#include <sstream>
#include <stdexcept>
#include <string>

namespace {
int checks = 0;
void check(bool ok, const std::string& message) {
    ++checks;
    if (!ok) throw std::runtime_error(message);
}
std::vector<std::string> words(const std::string& s) {
    std::istringstream in(s);
    std::vector<std::string> t;
    for (std::string w; in >> w;) t.push_back(w);
    return t;
}
struct ConstantEvaluator : ucl::Evaluator {
    int evaluate(const chess::Board&) const override { return 42; }
    std::string_view name() const override { return "test-constant"; }
};
// Exhaustive reference has no alpha-beta pruning or move ordering.
int reference(chess::Board& b, const ucl::Evaluator& eval, int depth, int ply) {
    chess::Movelist moves;
    chess::movegen::legalmoves(moves, b);
    if (moves.empty()) return b.inCheck() ? -ucl::mate_score + ply : 0;
    if (b.isHalfMoveDraw() || b.isInsufficientMaterial() || b.isRepetition(2)) return 0;
    if (depth == 0) return eval.evaluate(b);
    int best = -32000;
    for (auto m : moves) {
        b.makeMove(m);
        best = std::max(best, -reference(b, eval, depth - 1, ply + 1));
        b.unmakeMove(m);
    }
    return best;
}
void unit() {
    ucl::HandcraftedFeatures f;
    ucl::HandcraftedEvaluator eval(f);
    chess::Board b;
    check(f.extract(b).size() == 8, "feature dimension");
    check(eval.evaluate(b) == 0, "start symmetry");
    chess::Board white("4k3/8/8/8/8/8/4Q3/4K3 w - - 0 1");
    chess::Board black("4k3/8/8/8/8/8/4Q3/4K3 b - - 0 1");
    check(eval.evaluate(white) == 900, "queen value");
    check(eval.evaluate(black) == -900, "side to move perspective");
    std::string error;
    check(ucl::parse_position(words("position startpos moves e2e4 e7e5 g1f3"), b, error), error);
    check(b.fullMoveNumber() == 2 && b.sideToMove() == chess::Color::BLACK, "move replay");
    const auto fen = b.getFen(); const auto hash = b.hash();
    for (const std::string bad : {
        "position startpos moves e2e4 e7e9", "position fen 8/8/8/8/8/8/8/8 w - - 0 1",
        "position fen 4k3/8/8/8/8/8/8/4K3 w - - -1 1",
        "position fen 4k3/8/8/8/8/8/8/4K3 w K - 0 1",
        "position fen 4k3/8/8/8/8/8/8/4K3 w - e6 0 1",
        "position fen 4k3/8/8/8/8/8/8/4K3 w - - 9999999999999 1",
        "position fen 9/8/8/8/8/8/8/4K2k w - - 0 1",
        "position fen 8/8/8/8/8/8/4k3/4K3 w - - 0 1"}) {
        check(!ucl::parse_position(words(bad), b, error), "reject invalid position");
        check(b.getFen() == fen && b.hash() == hash, "transaction preserves board");
    }
    check(ucl::parse_position(words("position fen r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1 moves e1g1 e8c8"), b, error), "castling replay");
    check(b.at(chess::Square::SQ_G1).type() == chess::PieceType::KING, "white castle");
    check(ucl::parse_position(words("position fen 4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1 moves e5d6"), b, error), "en passant");
    check(b.pieces(chess::PieceType::PAWN, chess::Color::BLACK).count() == 0, "ep captured pawn");
    check(ucl::parse_position(words("position fen 4k3/P7/8/8/8/8/8/4K3 w - - 0 1 moves a7a8n"), b, error), "underpromotion");
}
void perfts() {
    struct Case { const char* fen; int depth; std::uint64_t nodes; };
    for (const auto& c : {
        Case{chess::constants::STARTPOS, 0, 1}, Case{chess::constants::STARTPOS, 4, 197281},
        Case{"r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1", 3, 97862},
        Case{"8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1", 4, 43238},
        Case{"r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq - 0 1", 3, 9467},
        Case{"rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ - 1 8", 3, 62379},
        Case{"7k/6Q1/6K1/8/8/8/8/8 b - - 0 1", 1, 0}}) {
        chess::Board b(c.fen); const auto hash = b.hash(); const auto fen = b.getFen();
        check(ucl::perft(b, c.depth) == c.nodes, "perft " + std::string(c.fen));
        check(b.hash() == hash && b.getFen() == fen, "perft restores board");
    }
}
void searches() {
    ucl::HandcraftedFeatures features;
    ucl::HandcraftedEvaluator eval(features);
    ucl::AlphaBetaSearch search({.quiescence = false, .tt = false, .pv_ordering = false});
    for (const char* fen : {chess::constants::STARTPOS,
        "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",
        "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1"}) {
        chess::Board position(fen);
        auto actual = search.run(position, eval, {.depth = 2});
        check(actual.score == reference(position, eval, 2, 0), "alpha-beta matches exhaustive minimax");
    }
    chess::Board b;
    const auto fen = b.getFen();
    auto r = search.run(b, eval, {.depth = 3});
    check(r.depth == 3 && r.best_move && b.isLegal(*r.best_move), "legal depth search");
    check(b.getFen() == fen && b.hash() == b.zobrist(), "caller board preserved");
    auto again = search.run(b, eval, {.depth = 3});
    check(r.best_move == again.best_move && r.nodes == again.nodes && r.score == again.score, "deterministic search");
    for (auto m : r.pv) { check(b.isLegal(m), "legal PV"); b.makeMove(m); }
    ConstantEvaluator replacement;
    r = search.run(chess::Board(), replacement, {.depth = 1});
    check(r.score == -42, "evaluator substitution and negamax sign");
    chess::Board mate("7k/5Q2/6K1/8/8/8/8/8 w - - 0 1");
    r = search.run(mate, eval, {.depth = 1});
    check(r.score == ucl::mate_score - 1 && r.best_move, "mate at leaf");
    mate.makeMove(*r.best_move);
    check(mate.isGameOver().second == chess::GameResult::LOSE, "chosen move checkmates");
    chess::Board terminal("7k/6Q1/6K1/8/8/8/8/8 b - - 100 1");
    r = search.run(terminal, eval, {.depth = 2});
    check(!r.best_move && r.score == -ucl::mate_score, "mate precedes 50-move draw");
    r = search.run(chess::Board("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1"), eval, {.depth = 2});
    check(!r.best_move && r.score == 0, "stalemate");
    r = search.run(chess::Board("4k3/8/8/8/8/8/8/4K3 w - - 0 1"), eval, {.depth = 2});
    check(r.score == 0 && r.depth == 0, "insufficient material");
    r = search.run(chess::Board("4k3/8/8/8/8/8/4R3/4K3 w - - 100 1"), eval, {.depth = 2});
    check(r.score == 0 && r.depth == 0, "50-move draw");
    std::string error;
    check(ucl::parse_position(words("position startpos moves g1f3 g8f6 f3g1 f6g8 g1f3 g8f6 f3g1 f6g8"), b, error), "repetition setup");
    r = search.run(b, eval, {.depth = 3});
    check(r.score == 0 && r.depth == 0, "threefold history retained");
    for (std::uint64_t cap : {1ULL, 30ULL, 500ULL}) {
        r = search.run(chess::Board(), eval, {.depth = 20, .nodes = cap});
        check(r.nodes <= cap && r.best_move, "strict node cap with fallback");
    }
    ucl::AlphaBetaSearch qs({.tt = false, .pv_ordering = false});
    chess::Board poison("3rk3/8/8/3p4/8/8/8/3QK3 w - - 0 1");
    auto shallow = search.run(poison, eval, {.depth = 1});
    auto stable = qs.run(poison, eval, {.depth = 1});
    check(chess::uci::moveToUci(*shallow.best_move) == "d1d5", "reference horizon takes poisoned pawn");
    check(stable.best_move != shallow.best_move && stable.qnodes > 0, "QS sees rook recapture");
    check(shallow.qnodes == 0, "QS independently disabled");
    struct NoCheckEval : ucl::Evaluator {
        int evaluate(const chess::Board& board) const override {
            if (board.inCheck()) throw std::runtime_error("static evaluation in check");
            return 0;
        }
        std::string_view name() const override { return "no-check"; }
    } no_check;
    auto evasion = qs.run(chess::Board("k7/8/8/8/8/8/4R3/4K3 w - - 0 1"), no_check, {.depth = 1});
    check(evasion.depth == 1 && evasion.qnodes > 10, "QS searches quiet check evasions");
    for (auto fen_q : {"7k/6Q1/6K1/8/8/8/8/8 b - - 100 1", "7k/5Q2/6K1/8/8/8/8/8 b - - 0 1"}) {
        auto a = qs.run(chess::Board(fen_q), eval, {.depth = 1});
        auto c = search.run(chess::Board(fen_q), eval, {.depth = 1});
        check(a.score == c.score && a.best_move == c.best_move, "QS preserves terminal precedence");
    }
    for (std::uint64_t cap : {1ULL, 30ULL, 500ULL}) {
        auto limited = qs.run(poison, eval, {.depth = 20, .nodes = cap});
        check(limited.nodes <= cap && limited.best_move && poison.isLegal(*limited.best_move), "QS strict budget");
    }
    std::stop_source midway;
    auto interrupted = qs.run(chess::Board(), eval, {.depth = 20}, midway.get_token(),
        [&](const auto& completed) { if (completed.depth == 2) midway.request_stop(); });
    check(interrupted.depth == 2 && interrupted.pv.size() >= 2, "QS retains completed iteration on stop");
    for (int value : {123, -456, ucl::mate_score - 7, -ucl::mate_score + 9}) {
        check(ucl::score_from_tt(ucl::score_to_tt(value, 5), 5) == value, "TT mate round trip");
    }
    check(ucl::score_from_tt(ucl::score_to_tt(ucl::mate_score - 7, 5), 2) == ucl::mate_score - 4,
          "TT mate distance at different ply");
    check(ucl::score_from_tt(ucl::score_to_tt(-ucl::mate_score + 9, 5), 2) == -ucl::mate_score + 6,
          "TT losing mate distance at different ply");
    ucl::TranspositionTable table(1);
    check(!table.probe(42), "empty TT");
    check(table.store({42, 10, 3, 5, 123, 1, ucl::Bound::lower, chess::Move(1)}), "TT store");
    check(table.probe(42)->bound == ucl::Bound::lower, "TT bound retained");
    check(!table.store({42, 11, 4, 2, 321, 1, ucl::Bound::upper, chess::Move(2)}), "TT depth replacement");
    check(table.store({42, 11, 4, 2, 321, 2, ucl::Bound::upper, chess::Move(2)}), "TT age replacement");
    check(table.probe(42)->history == 11 && table.probe(42)->halfmoves == 4, "TT path metadata");
    const auto collision = 42 + 1024 * 1024 / sizeof(ucl::TTEntry);
    check(table.store({collision, 0, 0, 3, 111, 3, ucl::Bound::exact, chess::Move(3)}), "TT collision replacement");
    check(!table.probe(42) && table.probe(collision), "TT verifies full Zobrist key");
    for (bool quiescence : {false, true}) {
        ucl::AlphaBetaSearch cached({.quiescence = quiescence, .pv_ordering = false, .hash_mb = 1});
        ucl::AlphaBetaSearch uncached({.quiescence = quiescence, .tt = false, .pv_ordering = false});
        for (const char* position : {chess::constants::STARTPOS,
             "3rk3/8/8/3p4/8/8/8/3QK3 w - - 0 1",
             "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 97 1",
             "7k/5Q2/6K1/8/8/8/8/8 w - - 0 1"}) {
            chess::Board board(position);
            auto a = cached.run(board, eval, {.depth = 3});
            auto c = uncached.run(board, eval, {.depth = 3});
            check(a.score == c.score && a.depth == c.depth, "TT preserves depth semantics");
            for (auto m : a.pv) { check(board.isLegal(m), "TT legal PV prefix"); board.makeMove(m); }
            check(c.tt_probes == 0 && c.tt_hits == 0, "TT independent switch");
        }
        // Identical board/hash with different reversible history must not leak.
        chess::Board history;
        std::string err;
        check(ucl::parse_position(words("position startpos moves g1f3 g8f6 f3g1 f6g8"), history, err), err);
        for (auto board : {history, chess::Board(history.getFen())}) {
            auto a = cached.run(board, eval, {.depth = 4});
            auto c = uncached.run(board, eval, {.depth = 4});
            check(a.score == c.score, "TT repetition history isolation");
        }
        auto a = cached.run(chess::Board(), eval, {.depth = 4});
        check(a.tt_hits > 0 && a.tt_cutoffs > 0 && a.tt_stores > 0, "TT actually reuses cached results");
    }
    std::mt19937 random(20261015);
    chess::Board sample;
    for (int position = 0; position < 10; ++position) {
        for (int step = 0; step < 3; ++step) {
            chess::Movelist legal;
            chess::movegen::legalmoves(legal, sample);
            if (legal.empty() || sample.isGameOver().second != chess::GameResult::NONE) sample = chess::Board();
            chess::movegen::legalmoves(legal, sample);
            sample.makeMove(legal[static_cast<int>(random() % static_cast<unsigned>(legal.size()))]);
        }
        for (bool q : {false, true}) {
            ucl::AlphaBetaSearch reference_search({.quiescence = q, .tt = false, .pv_ordering = false});
            auto expected = reference_search.run(sample, eval, {.depth = 3});
            for (bool tt : {false, true}) for (bool pv : {false, true}) {
                ucl::AlphaBetaSearch variant({.quiescence = q, .tt = tt, .pv_ordering = pv, .hash_mb = 1});
                auto a = variant.run(sample, eval, {.depth = 3});
                check(a.score == expected.score && a.depth == expected.depth, "all eight switches preserve fixed-QS minimax score");
                check(a.best_move && sample.isLegal(*a.best_move), "all switches legal move");
                auto copy = sample;
                for (auto m : a.pv) { check(copy.isLegal(m), "all switches legal PV"); copy.makeMove(m); }
                check(pv || (a.pv_order_hits == 0 && a.tt_order_hits == 0), "ordering switch disables both hints");
                check(tt || (a.tt_probes == 0 && a.tt_order_hits == 0), "PV works without TT");
            }
        }
    }
    ucl::AlphaBetaSearch ordered;
    auto ordered_result = ordered.run(chess::Board(), eval, {.depth = 4});
    check(ordered_result.pv_order_hits > 0 && ordered_result.tt_order_hits > 0, "previous PV and TT ordering used");
    for (std::uint64_t cap : {1ULL, 50ULL, 1500ULL}) {
        auto a = ordered.run(chess::Board(), eval, {.depth = 20, .nodes = cap});
        check(a.nodes <= cap && a.best_move, "all optimizations strict node cap");
    }
    struct ObserveTactics : ucl::Evaluator {
        const ucl::Evaluator& base;
        mutable bool ep = false, promotion = false;
        explicit ObserveTactics(const ucl::Evaluator& e) : base(e) {}
        int evaluate(const chess::Board& board) const override {
            ep = ep || (board.at(chess::Square::SQ_D6) == chess::Piece(chess::PieceType::PAWN, chess::Color::WHITE) &&
                        board.at(chess::Square::SQ_D5) == chess::Piece::NONE);
            promotion = promotion || !board.pieces(chess::PieceType::QUEEN, chess::Color::BLACK).empty();
            return base.evaluate(board);
        }
        std::string_view name() const override { return "observe-tactics"; }
    } tactics(eval);
    qs.run(chess::Board("7k/3p4/8/4P3/8/8/8/K7 b - - 0 1"), tactics, {.depth = 1});
    check(tactics.ep, "QS includes en passant at horizon");
    qs.run(chess::Board("7k/8/8/8/8/8/p7/7K w - - 0 1"), tactics, {.depth = 1});
    check(tactics.promotion, "QS includes quiet promotions at horizon");
    for (bool tt : {false, true}) for (bool pv : {false, true}) {
        ucl::AlphaBetaSearch mate_search({.quiescence = false, .tt = tt, .pv_ordering = pv, .hash_mb = 1});
        auto two = mate_search.run(chess::Board("1Q6/8/8/8/8/3K4/8/k7 w - - 0 1"), eval, {.depth = 4});
        check(two.score == ucl::mate_score - 3, "mate in two distance independent of cache/order");
        auto board = chess::Board("1Q6/8/8/8/8/3K4/8/k7 w - - 0 1");
        for (auto m : two.pv) { check(board.isLegal(m), "mate distance PV legal"); board.makeMove(m); }
        check(two.pv.size() <= 3 && (two.pv.size() < 3 || board.isGameOver().second == chess::GameResult::LOSE), "mate PV terminal or cached prefix");
    }
    std::stop_source default_stop;
    auto stopped_default = ordered.run(chess::Board(), eval, {.depth = 20}, default_stop.get_token(),
        [&](const auto& completed) { if (completed.depth == 2) default_stop.request_stop(); });
    check(stopped_default.depth == 2 && stopped_default.best_move, "TT/PV search interruption retains complete iteration");
    auto fresh_default = ordered.run(chess::Board(), eval, {.depth = 3});
    auto repeat_default = ordered.run(chess::Board(), eval, {.depth = 3});
    check(fresh_default.score == repeat_default.score && fresh_default.nodes == repeat_default.nodes, "interrupted TT never leaks between runs");
    chess::Board repeated;
    std::string repetition_error;
    check(ucl::parse_position(words("position startpos moves g1f3 g8f6 f3g1 f6g8 g1f3 g8f6 f3g1 f6g8"), repeated, repetition_error), repetition_error);
    check(ordered.run(repeated, eval, {.depth = 3}).depth == 0, "all optimizations retain threefold history");
    std::stop_source stop; stop.request_stop();
    r = search.run(chess::Board(), eval, {.depth = 20}, stop.get_token());
    check(r.nodes == 0 && r.best_move && r.depth == 0, "immediate stop");
    r = search.run(chess::Board(), eval, {.depth = 20, .time = std::chrono::milliseconds(0)});
    check(r.nodes == 0 && r.best_move, "zero time");
}
} // namespace
int main(int argc, char** argv) {
    try {
        const std::string suite = argc > 1 ? argv[1] : "";
        if (suite == "unit") unit(); else if (suite == "perft") perfts(); else if (suite == "search") searches();
        else throw std::runtime_error("unknown test suite");
        std::cout << suite << ": " << checks << " checks passed\n";
        return 0;
    } catch (const std::exception& e) { std::cerr << "FAIL: " << e.what() << '\n'; return 1; }
}
