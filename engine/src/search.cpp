#include "ucl/search.hpp"
#include <algorithm>
#include <stdexcept>

namespace ucl {
namespace {
using Clock = std::chrono::steady_clock;
constexpr int infinity = 32000;
bool drawn(const chess::Board& b) {
    return b.isHalfMoveDraw() || b.isInsufficientMaterial() || b.isRepetition(2);
}
int priority(const chess::Board& b, chess::Move m) {
    static constexpr int values[]{100, 320, 330, 500, 900, 20000, 0};
    int score = 0;
    if (b.isCapture(m)) {
        const int victim = m.typeOf() == chess::Move::ENPASSANT ? 100 :
            values[static_cast<int>(b.at(m.to()).type())];
        score += 10000 + 10 * victim - values[static_cast<int>(b.at(m.from()).type())];
    }
    if (m.typeOf() == chess::Move::PROMOTION) score += values[static_cast<int>(m.promotionType())];
    return score;
}
void order(chess::Movelist& moves, const chess::Board& b) {
    std::stable_sort(moves.begin(), moves.end(), [&](auto a, auto c) { return priority(b, a) > priority(b, c); });
}
struct Context {
    const Evaluator& eval;
    const SearchLimits& limits;
    const SearchOptions& options;
    std::stop_token stop;
    Clock::time_point start;
    std::uint64_t nodes = 0;
    std::uint64_t qnodes = 0;
    bool aborted = false;
    bool cancelled() {
        aborted = aborted || stop.stop_requested() || (limits.nodes && nodes >= *limits.nodes) ||
            (limits.time && Clock::now() - start >= *limits.time);
        return aborted;
    }
    int negamax(chess::Board& b, int depth, int ply, int alpha, int beta,
                std::vector<chess::Move>& pv) {
        if (cancelled()) return 0;
        ++nodes;
        const bool quiet = depth == 0 && options.quiescence;
        if (quiet) ++qnodes;
        chess::Movelist moves;
        chess::movegen::legalmoves(moves, b);
        // Mate takes precedence over 50-move and repetition claims, including at horizon.
        if (moves.empty()) return b.inCheck() ? -mate_score + ply : 0;
        if (drawn(b)) return 0;
        // Never claim a completed iteration after hitting the stack safety cap.
        if (ply >= max_search_ply) { aborted = true; return 0; }
        auto evaluate = [&] { return std::clamp(eval.evaluate(b), -mate_score + max_search_ply + 1,
                                                mate_score - max_search_ply - 1); };
        if (depth == 0 && !quiet) return evaluate();
        int best = -infinity;
        if (quiet && !b.inCheck()) {
            best = evaluate(); // Stand pat is invalid in check.
            if (best >= beta) return best;
            alpha = std::max(alpha, best);
        }
        order(moves, b);
        for (auto move : moves) {
            if (quiet && !b.inCheck() && !b.isCapture(move) && move.typeOf() != chess::Move::PROMOTION) continue;
            b.makeMove(move);
            std::vector<chess::Move> child;
            const int score = -negamax(b, std::max(0, depth - 1), ply + 1, -beta, -alpha, child);
            b.unmakeMove(move);
            if (aborted) return 0;
            if (score > best) {
                best = score;
                pv = {move};
                pv.insert(pv.end(), child.begin(), child.end());
            }
            alpha = std::max(alpha, score);
            if (alpha >= beta) break;
        }
        return best;
    }
};
} // namespace
SearchResult AlphaBetaSearch::run(chess::Board b, const Evaluator& eval, const SearchLimits& limits,
                                  std::stop_token stop, SearchObserver observer) {
    if (limits.depth < 1 || limits.depth > max_depth || (limits.nodes && *limits.nodes == 0) ||
        (limits.time && limits.time->count() < 0)) throw std::invalid_argument("invalid search limits");
    Context ctx{eval, limits, options_, stop, Clock::now()};
    SearchResult result;
    chess::Movelist moves;
    chess::movegen::legalmoves(moves, b);
    if (moves.empty()) { result.score = b.inCheck() ? -mate_score : 0; return result; }
    result.best_move = moves.front(); // Legal fallback even for immediate stop or zero time.
    if (drawn(b)) return result;
    for (int depth = 1; depth <= limits.depth; ++depth) {
        std::vector<chess::Move> pv;
        const int score = ctx.negamax(b, depth, 0, -infinity, infinity, pv);
        if (ctx.aborted) break;
        result.score = score;
        result.depth = depth;
        result.pv = std::move(pv);
        result.best_move = result.pv.front();
        result.nodes = ctx.nodes;
        result.qnodes = ctx.qnodes;
        result.elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(Clock::now() - ctx.start);
        if (observer) observer(result);
        if (std::abs(score) >= mate_score - depth) break;
    }
    result.nodes = ctx.nodes;
    result.qnodes = ctx.qnodes;
    result.elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(Clock::now() - ctx.start);
    return result;
}
std::uint64_t perft(chess::Board& b, int depth) {
    if (depth < 0) throw std::invalid_argument("perft depth must be nonnegative");
    if (depth == 0) return 1;
    chess::Movelist moves;
    chess::movegen::legalmoves(moves, b);
    if (depth == 1) return static_cast<std::uint64_t>(moves.size());
    std::uint64_t nodes = 0;
    for (auto m : moves) { b.makeMove(m); nodes += perft(b, depth - 1); b.unmakeMove(m); }
    return nodes;
}
} // namespace ucl
