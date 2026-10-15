#include "ucl/evaluator.hpp"
#include <algorithm>
#include <array>
#include <cmath>

namespace ucl {
std::vector<float> InterpretableFeatures::extract(const chess::Board& board) const {
    auto f = HandcraftedFeatures{}.extract(board);
    f.resize(14, 0.0F);
    int phase = 0;
    for (auto color : {chess::Color::WHITE, chess::Color::BLACK}) {
        phase += board.pieces(chess::PieceType::KNIGHT, color).count() +
                 board.pieces(chess::PieceType::BISHOP, color).count() +
                 2 * board.pieces(chess::PieceType::ROOK, color).count() +
                 4 * board.pieces(chess::PieceType::QUEEN, color).count();
    }
    const int endgame = 24 - std::min(24, phase);
    for (auto color : {chess::Color::WHITE, chess::Color::BLACK}) {
        const int sign = color == chess::Color::WHITE ? 1 : -1;
        std::array<int, 8> files{};
        auto pawns = board.pieces(chess::PieceType::PAWN, color);
        auto scan = pawns;
        while (scan) ++files[static_cast<std::size_t>(scan.pop() % 8)];
        for (int file = 0; file < 8; ++file) {
            f[9] += static_cast<float>(sign * std::max(0, files[static_cast<std::size_t>(file)] - 1));
        }
        const int king = board.kingSq(color).index();
        while (pawns) {
            const int sq = pawns.pop(), file = sq % 8, rank = sq / 8;
            if ((file == 0 || files[static_cast<std::size_t>(file - 1)] == 0) &&
                (file == 7 || files[static_cast<std::size_t>(file + 1)] == 0)) f[8] += static_cast<float>(sign);
            bool passed = true;
            auto enemy = board.pieces(chess::PieceType::PAWN, ~color);
            while (enemy) {
                const int other = enemy.pop();
                if (std::abs(other % 8 - file) <= 1 &&
                    (color == chess::Color::WHITE ? other / 8 > rank : other / 8 < rank)) {
                    passed = false;
                    break;
                }
            }
            const int advancement = (color == chess::Color::WHITE ? rank : 7 - rank) - 1;
            if (passed) f[10] += static_cast<float>(sign * advancement);
            const int forward = (rank - king / 8) * sign;
            if (std::abs(file - king % 8) <= 1 && (forward == 1 || forward == 2)) f[11] += static_cast<float>(sign);
        }
        auto ring = chess::attacks::king(chess::Square(king));
        while (ring) {
            if (board.isAttacked(chess::Square(ring.pop()), ~color)) f[12] += static_cast<float>(sign);
        }
        const int centrality = std::min(king % 8, 7 - king % 8) + std::min(king / 8, 7 - king / 8);
        f[13] += static_cast<float>(sign * centrality * endgame);
    }
    return f;
}
} // namespace ucl
