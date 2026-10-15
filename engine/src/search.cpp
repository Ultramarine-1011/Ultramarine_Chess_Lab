#include "ucl/search.hpp"
#include "ucl/transposition.hpp"
#include <memory>
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
void order(chess::Movelist& moves, const chess::Board& b, chess::Move pv, chess::Move tt) {
    auto rank = [&](auto m) { return m == pv ? 1000000 : m == tt ? 900000 : priority(b, m); };
    std::stable_sort(moves.begin(), moves.end(), [&](auto a, auto c) { return rank(a) > rank(c); });
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
    std::unique_ptr<TranspositionTable> table;
    int generation = 0;
    std::uint64_t probes = 0, hits = 0, cutoffs = 0, stores = 0;
    std::uint64_t pv_order_hits = 0, tt_order_hits = 0;
    std::vector<chess::Move> previous_pv;
    Context(const Evaluator& evaluator, const SearchLimits& search_limits,
            const SearchOptions& search_options, std::stop_token token)
        : eval(evaluator), limits(search_limits), options(search_options), stop(token), start(Clock::now()),
          table(options.tt ? std::make_unique<TranspositionTable>(options.hash_mb) : nullptr) {}
    bool cancelled() {
        aborted = aborted || stop.stop_requested() || (limits.nodes && nodes >= *limits.nodes) ||
            (limits.time && Clock::now() - start >= *limits.time);
        return aborted;
    }
    int negamax(chess::Board& b, int depth, int ply, int alpha, int beta,
                std::vector<chess::Move>& pv, std::uint64_t history, bool follows_pv) {
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
        const int original_alpha = alpha;
        chess::Move tt_move{chess::Move::NO_MOVE};
        if (table && depth > 0) {
            ++probes;
            if (const auto* entry = table->probe(b.hash())) {
                ++hits;
                tt_move = entry->move;
                const int value = score_from_tt(entry->score, ply);
                const bool legal = std::find(moves.begin(), moves.end(), entry->move) != moves.end();
                if (ply > 0 && legal && entry->depth == depth && entry->history == history &&
                    entry->halfmoves == static_cast<int>(b.halfMoveClock()) &&
                    (entry->bound == Bound::exact || (entry->bound == Bound::lower && value >= beta) ||
                     (entry->bound == Bound::upper && value <= alpha))) {
                    ++cutoffs;
                    pv = {entry->move}; // A legal cached prefix; no fabricated continuation.
                    return value;
                }
            }
        }
        int best = -infinity;
        if (quiet && !b.inCheck()) {
            best = evaluate(); // Stand pat is invalid in check.
            if (best >= beta) return best;
            alpha = std::max(alpha, best);
        }
        chess::Move pv_move{chess::Move::NO_MOVE};
        if (options.pv_ordering) {
            if (follows_pv && static_cast<std::size_t>(ply) < previous_pv.size()) pv_move = previous_pv[static_cast<std::size_t>(ply)];
            if (std::find(moves.begin(), moves.end(), pv_move) != moves.end()) ++pv_order_hits;
            if (std::find(moves.begin(), moves.end(), tt_move) != moves.end()) ++tt_order_hits;
        } else tt_move = chess::Move(chess::Move::NO_MOVE);
        order(moves, b, pv_move, tt_move);
        for (auto move : moves) {
            if (quiet && !b.inCheck() && !b.isCapture(move) && move.typeOf() != chess::Move::PROMOTION) continue;
            const auto parent_hash = b.hash();
            b.makeMove(move);
            const auto child_history = b.halfMoveClock() == 0 ? 0 : history + history_mix(parent_hash);
            std::vector<chess::Move> child;
            const int score = -negamax(b, std::max(0, depth - 1), ply + 1, -beta, -alpha, child, child_history, follows_pv && move == pv_move);
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
        if (table && depth > 0 && !pv.empty()) {
            const auto bound = best <= original_alpha ? Bound::upper : best >= beta ? Bound::lower : Bound::exact;
            if (table->store({b.hash(), history, static_cast<int>(b.halfMoveClock()), depth,
                              score_to_tt(best, ply), generation, bound, pv.front()})) ++stores;
        }
        return best;
    }
};
} // namespace
SearchResult AlphaBetaSearch::run(chess::Board b, const Evaluator& eval, const SearchLimits& limits,
                                  std::stop_token stop, SearchObserver observer) {
    if (limits.depth < 1 || limits.depth > max_depth || (limits.nodes && *limits.nodes == 0) ||
        (limits.time && limits.time->count() < 0)) throw std::invalid_argument("invalid search limits");
    Context ctx{eval, limits, options_, stop};
    SearchResult result;
    chess::Movelist moves;
    chess::movegen::legalmoves(moves, b);
    if (moves.empty()) { result.score = b.inCheck() ? -mate_score : 0; return result; }
    result.best_move = moves.front(); // Legal fallback even for immediate stop or zero time.
    if (drawn(b)) return result;
    for (int depth = 1; depth <= limits.depth; ++depth) {
        std::vector<chess::Move> pv;
        ctx.generation = depth;
        const auto history = b.halfMoveClock() == 0 ? 0 : history_mix(0x55434c524f4f54ULL);
        const int score = ctx.negamax(b, depth, 0, -infinity, infinity, pv, history, true);
        if (ctx.aborted) break;
        result.score = score;
        result.depth = depth;
        result.pv = std::move(pv);
        ctx.previous_pv = result.pv;
        result.best_move = result.pv.front();
        result.nodes = ctx.nodes;
        result.qnodes = ctx.qnodes;
        result.tt_probes = ctx.probes; result.tt_hits = ctx.hits;
        result.tt_cutoffs = ctx.cutoffs; result.tt_stores = ctx.stores;
        result.pv_order_hits = ctx.pv_order_hits; result.tt_order_hits = ctx.tt_order_hits;
        result.elapsed_us = std::chrono::duration_cast<std::chrono::microseconds>(Clock::now() - ctx.start);
        result.elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(result.elapsed_us);
        if (observer) observer(result);
        if (std::abs(score) >= mate_score - depth) break;
    }
    result.nodes = ctx.nodes;
    result.qnodes = ctx.qnodes;
    result.tt_probes = ctx.probes; result.tt_hits = ctx.hits;
    result.tt_cutoffs = ctx.cutoffs; result.tt_stores = ctx.stores;
    result.pv_order_hits = ctx.pv_order_hits; result.tt_order_hits = ctx.tt_order_hits;
    result.elapsed_us = std::chrono::duration_cast<std::chrono::microseconds>(Clock::now() - ctx.start);
    result.elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(result.elapsed_us);
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
