#include "ucl/evaluator.hpp"
#include "ucl/position.hpp"
#include "ucl/search.hpp"
#include <iostream>
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
    ucl::AlphaBetaSearch search;
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
