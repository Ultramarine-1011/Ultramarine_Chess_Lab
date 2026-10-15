#pragma once
#include "ucl/evaluator.hpp"
#include <chrono>
#include <cstdint>
#include <functional>
#include <optional>
#include <stop_token>
#include <vector>

namespace ucl {
inline constexpr int mate_score = 30000;
inline constexpr int max_depth = 128;
inline constexpr int max_search_ply = 256;
struct SearchOptions {
    bool quiescence = true;
};
struct SearchLimits {
    int depth = 5;
    std::optional<std::uint64_t> nodes;
    std::optional<std::chrono::milliseconds> time;
};
struct SearchResult {
    std::optional<chess::Move> best_move;
    int score = 0;
    int depth = 0; // Last fully completed iteration; zero means fallback.
    std::uint64_t nodes = 0;
    std::uint64_t qnodes = 0;
    std::chrono::milliseconds elapsed{0};
    std::vector<chess::Move> pv;
};
using SearchObserver = std::function<void(const SearchResult&)>;
class Search {
public:
    virtual ~Search() = default;
    // A private board copy preserves the caller's position and repetition history.
    virtual SearchResult run(chess::Board board, const Evaluator&, const SearchLimits&,
                             std::stop_token = {}, SearchObserver = {}) = 0;
};
class AlphaBetaSearch final : public Search {
public:
    explicit AlphaBetaSearch(SearchOptions options = {}) : options_(options) {}
    SearchResult run(chess::Board, const Evaluator&, const SearchLimits&,
                     std::stop_token = {}, SearchObserver = {}) override;
private:
    SearchOptions options_;
};
[[nodiscard]] std::uint64_t perft(chess::Board& board, int depth);
} // namespace ucl
