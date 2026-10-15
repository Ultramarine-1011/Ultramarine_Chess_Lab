#include "ucl/position.hpp"
#include <algorithm>
#include <array>
#include <charconv>
#include <cctype>
#include <string_view>

namespace ucl {
namespace {
bool number(std::string_view s, int low, int high) {
    int n = 0;
    auto [end, ec] = std::from_chars(s.data(), s.data() + s.size(), n);
    return ec == std::errc{} && end == s.data() + s.size() && n >= low && n <= high;
}
bool valid_fen(const std::vector<std::string>& t) {
    if (t.size() < 8 || (t[3] != "w" && t[3] != "b") ||
        !number(t[6], 0, 100) || !number(t[7], 1, 32767)) return false;
    std::array<char, 64> squares{};
    int rank = 7, file = 0, wk = 0, bk = 0, wp = 0, bp = 0, white = 0, black = 0;
    for (char c : t[2]) {
        if (c == '/') { if (file != 8 || rank == 0) return false; --rank; file = 0; }
        else if (c >= '1' && c <= '8') { file += c - '0'; if (file > 8) return false; }
        else {
            if (std::string_view("PNBRQKpnbrqk").find(c) == std::string_view::npos || file >= 8) return false;
            if ((c == 'p' || c == 'P') && (rank == 0 || rank == 7)) return false;
            squares[static_cast<std::size_t>(8 * rank + file++)] = c;
            wk += c == 'K'; bk += c == 'k'; wp += c == 'P'; bp += c == 'p';
            if (std::isupper(static_cast<unsigned char>(c))) ++white; else ++black;
        }
    }
    if (rank != 0 || file != 8 || wk != 1 || bk != 1 || wp > 8 || bp > 8 || white > 16 || black > 16) return false;
    if (t[4] != "-") {
        std::string seen;
        for (char c : t[4]) {
            if (std::string_view("KQkq").find(c) == std::string_view::npos || seen.find(c) != std::string::npos) return false;
            seen += c;
            const bool w = c == 'K' || c == 'Q';
            const int k = w ? 4 : 60;
            const int r = c == 'K' ? 7 : c == 'Q' ? 0 : c == 'k' ? 63 : 56;
            if (squares[static_cast<std::size_t>(k)] != (w ? 'K' : 'k') ||
                squares[static_cast<std::size_t>(r)] != (w ? 'R' : 'r')) return false;
        }
    }
    if (t[5] != "-") {
        if (t[5].size() != 2 || t[5][0] < 'a' || t[5][0] > 'h' || t[5][1] != (t[3] == "w" ? '6' : '3')) return false;
        const int ep = (t[5][1] - '1') * 8 + t[5][0] - 'a';
        const int pawn = ep + (t[3] == "w" ? -8 : 8);
        const int origin = ep + (t[3] == "w" ? 8 : -8);
        if (squares[static_cast<std::size_t>(ep)] || squares[static_cast<std::size_t>(origin)] ||
            squares[static_cast<std::size_t>(pawn)] != (t[3] == "w" ? 'p' : 'P') || t[6] != "0") return false;
    }
    return true;
}
} // namespace
bool parse_position(const std::vector<std::string>& tokens, chess::Board& board, std::string& error) {
    try {
        chess::Board next;
        std::size_t i = 2;
        if (tokens.size() < 2) { error = "missing position"; return false; }
        if (tokens[1] == "fen") {
            if (!valid_fen(tokens)) { error = "invalid FEN"; return false; }
            std::string fen;
            for (std::size_t j = 2; j < 8; ++j) { if (j != 2) fen += ' '; fen += tokens[j]; }
            if (!next.setFen(fen) || next.isAttacked(next.kingSq(~next.sideToMove()), next.sideToMove())) {
                error = "illegal FEN"; return false;
            }
            i = 8;
        } else if (tokens[1] != "startpos") { error = "expected startpos or fen"; return false; }
        if (i < tokens.size()) {
            if (tokens[i++] != "moves") { error = "expected moves"; return false; }
            for (; i < tokens.size(); ++i) {
                // Match against generated moves; never pass arbitrary text to makeMove.
                chess::Movelist legal;
                chess::movegen::legalmoves(legal, next);
                auto found = std::find_if(legal.begin(), legal.end(), [&](auto move) {
                    return chess::uci::moveToUci(move) == tokens[i];
                });
                if (found == legal.end()) { error = "illegal move " + tokens[i]; return false; }
                next.makeMove(*found);
            }
        }
        board = std::move(next);
        error.clear();
        return true;
    } catch (const std::exception& e) { error = e.what(); return false; }
}
} // namespace ucl
