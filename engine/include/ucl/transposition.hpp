#pragma once
#include "ucl/search.hpp"
#include <stdexcept>

namespace ucl {
enum class Bound { exact, lower, upper };
inline int score_to_tt(int score, int ply) {
    return score >= mate_score - max_search_ply ? score + ply :
           score <= -mate_score + max_search_ply ? score - ply : score;
}
inline int score_from_tt(int score, int ply) {
    return score >= mate_score - max_search_ply ? score - ply :
           score <= -mate_score + max_search_ply ? score + ply : score;
}
// Commutative multiset fingerprint: repetition depends on occurrence counts,
// not the order of reversible history. Root prehistory is opaque but fixed for
// the lifetime of a run; never share this table between runs.
inline std::uint64_t history_mix(std::uint64_t key) {
    key += 0x9e3779b97f4a7c15ULL;
    key = (key ^ (key >> 30)) * 0xbf58476d1ce4e5b9ULL;
    key = (key ^ (key >> 27)) * 0x94d049bb133111ebULL;
    return key ^ (key >> 31);
}
struct TTEntry {
    std::uint64_t key = 0, history = 0;
    int halfmoves = 0, depth = -1, score = 0, generation = 0;
    Bound bound = Bound::exact;
    chess::Move move{chess::Move::NO_MOVE};
};
class TranspositionTable {
public:
    explicit TranspositionTable(std::size_t megabytes) {
        if (megabytes < 1 || megabytes > 1024) throw std::invalid_argument("Hash must be 1..1024 MB");
        entries_.resize(megabytes * 1024 * 1024 / sizeof(TTEntry));
    }
    const TTEntry* probe(std::uint64_t key) const {
        const auto& e = entries_[key % entries_.size()];
        return e.depth >= 0 && e.key == key ? &e : nullptr;
    }
    bool store(TTEntry value) {
        auto& e = entries_[value.key % entries_.size()];
        // Prefer deeper entries in this iteration; age at each root iteration.
        if (e.depth >= 0 && e.generation == value.generation && e.depth > value.depth) return false;
        e = value;
        return true;
    }
private:
    std::vector<TTEntry> entries_;
};
} // namespace ucl
