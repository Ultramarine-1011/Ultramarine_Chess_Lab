#pragma once
#include <chess.hpp>
#include <string>
#include <vector>

namespace ucl {
// Transactional parsing: invalid FEN or moves never modify the current board.
[[nodiscard]] bool parse_position(const std::vector<std::string>& tokens,
                                  chess::Board& board, std::string& error);
} // namespace ucl
