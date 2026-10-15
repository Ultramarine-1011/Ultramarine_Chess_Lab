#include "ucl/evaluator.hpp"
#include <algorithm>
#include <cmath>
#include <stdexcept>

namespace ucl {
std::vector<float> HandcraftedFeatures::extract(const chess::Board& board) const {
    std::vector<float> f(8, 0.0F);
    for (auto color : {chess::Color::WHITE, chess::Color::BLACK}) {
        const float sign = color == chess::Color::WHITE ? 1.0F : -1.0F;
        for (int pt = 0; pt < 5; ++pt) {
            f[static_cast<std::size_t>(pt)] += sign * static_cast<float>(
                board.pieces(chess::PieceType(static_cast<chess::PieceType::underlying>(pt)), color).count());
        }
        auto pawns = board.pieces(chess::PieceType::PAWN, color);
        while (pawns) {
            const int sq = pawns.pop();
            const int rank = color == chess::Color::WHITE ? sq / 8 : 7 - sq / 8;
            f[5] += sign * static_cast<float>(rank - 1);
        }
        auto minors = board.pieces(chess::PieceType::KNIGHT, color) |
                      board.pieces(chess::PieceType::BISHOP, color);
        while (minors) {
            const int sq = minors.pop();
            const int centrality = std::min(sq % 8, 7 - sq % 8) + std::min(sq / 8, 7 - sq / 8);
            f[6] += sign * static_cast<float>(centrality);
        }
        if (board.pieces(chess::PieceType::BISHOP, color).count() >= 2) f[7] += sign;
    }
    return f;
}
int HandcraftedEvaluator::evaluate(const chess::Board& board) const {
    const auto f = features_.extract(board);
    if (f.size() != weights.size()) throw std::invalid_argument("handcrafted-v1 requires 8 features");
    float score = 0;
    for (std::size_t i = 0; i < f.size(); ++i) score += f[i] * weights[i];
    const int cp = static_cast<int>(std::lround(score));
    return board.sideToMove() == chess::Color::WHITE ? cp : -cp;
}
} // namespace ucl
