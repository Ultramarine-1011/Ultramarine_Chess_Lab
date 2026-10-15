#include "ucl/evaluator.hpp"
#include <algorithm>
#include <array>
#include <cmath>

namespace ucl {
namespace {
// Enemy pawns strictly ahead on this or an adjacent file. Ranks on the same
// row do not prevent a passed pawn; edge files must not wrap around.
constexpr auto passed_masks() {
    std::array<std::array<std::uint64_t, 64>, 2> masks{};
    for (int color = 0; color < 2; ++color) {
        for (int sq = 0; sq < 64; ++sq) {
            for (int other = 0; other < 64; ++other) {
                const int delta = other % 8 - sq % 8;
                if (delta >= -1 && delta <= 1 &&
                    (color == 0 ? other / 8 > sq / 8 : other / 8 < sq / 8)) {
                    masks[static_cast<std::size_t>(color)][static_cast<std::size_t>(sq)] |= 1ULL << other;
                }
            }
        }
    }
    return masks;
}
constexpr auto passed = passed_masks();
} // namespace
std::vector<float> InterpretableFeatures::extract(const chess::Board& board) const {
    // Keep the v1 prefix exact while avoiding its temporary eight-element
    // allocation and the second allocation on resize. Handcrafted is unchanged.
    std::vector<float> f(14, 0.0F);
    int phase = 0;
    int king_centrality = 0;
    for (auto color : {chess::Color::WHITE, chess::Color::BLACK}) {
        const int sign = color == chess::Color::WHITE ? 1 : -1;
        constexpr std::array<int, 5> phase_weights{0, 1, 1, 2, 4};
        for (int pt = 0; pt < 5; ++pt) {
            const int count = board.pieces(chess::PieceType(static_cast<chess::PieceType::underlying>(pt)), color).count();
            f[static_cast<std::size_t>(pt)] += static_cast<float>(sign * count);
            phase += phase_weights[static_cast<std::size_t>(pt)] * count;
        }
        auto minors = board.pieces(chess::PieceType::KNIGHT, color) | board.pieces(chess::PieceType::BISHOP, color);
        while (minors) {
            const int sq = minors.pop();
            f[6] += static_cast<float>(sign * (std::min(sq % 8, 7 - sq % 8) + std::min(sq / 8, 7 - sq / 8)));
        }
        if (board.pieces(chess::PieceType::BISHOP, color).count() >= 2) f[7] += static_cast<float>(sign);
        std::array<int, 8> files{};
        auto pawns = board.pieces(chess::PieceType::PAWN, color);
        auto scan = pawns;
        while (scan) ++files[static_cast<std::size_t>(scan.pop() % 8)];
        for (int file = 0; file < 8; ++file) {
            f[9] += static_cast<float>(sign * std::max(0, files[static_cast<std::size_t>(file)] - 1));
        }
        const int king = board.kingSq(color).index();
        const auto enemy = board.pieces(chess::PieceType::PAWN, ~color);
        while (pawns) {
            const int sq = pawns.pop(), file = sq % 8, rank = sq / 8;
            if ((file == 0 || files[static_cast<std::size_t>(file - 1)] == 0) &&
                (file == 7 || files[static_cast<std::size_t>(file + 1)] == 0)) f[8] += static_cast<float>(sign);
            const int advancement = (color == chess::Color::WHITE ? rank : 7 - rank) - 1;
            f[5] += static_cast<float>(sign * advancement);
            if (!(enemy & passed[color == chess::Color::WHITE ? 0U : 1U][static_cast<std::size_t>(sq)])) {
                f[10] += static_cast<float>(sign * advancement);
            }
            const int forward = (rank - king / 8) * sign;
            if (std::abs(file - king % 8) <= 1 && (forward == 1 || forward == 2)) f[11] += static_cast<float>(sign);
        }
        auto ring = chess::attacks::king(chess::Square(king));
        while (ring) {
            if (board.isAttacked(chess::Square(ring.pop()), ~color)) f[12] += static_cast<float>(sign);
        }
        const int centrality = std::min(king % 8, 7 - king % 8) + std::min(king / 8, 7 - king / 8);
        king_centrality += sign * centrality;
    }
    // All factors are small exact integers, including promoted-piece phase>24.
    f[13] = static_cast<float>(king_centrality * (24 - std::min(24, phase)));
    return f;
}
} // namespace ucl
