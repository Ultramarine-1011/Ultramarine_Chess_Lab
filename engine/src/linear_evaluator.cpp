#include "ucl/evaluator.hpp"
#include <picosha2.h>
#include <algorithm>
#include <charconv>
#include <cmath>
#include <fstream>
#include <sstream>
#include <stdexcept>

namespace ucl {
namespace {
bool valid_hash(const std::string& value) {
    return value.size() == 64 && std::all_of(value.begin(), value.end(), [](char c) {
        return (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f');
    });
}
}
LinearEvaluator LinearEvaluator::load(const FeatureExtractor& features, const std::string& path,
                                      const std::string& expected_sha256) {
    if (features.name() != "handcrafted-v1") throw std::invalid_argument("linear feature version mismatch");
    if (!valid_hash(expected_sha256)) throw std::invalid_argument("expected model SHA-256 required");
    std::ifstream file(path, std::ios::binary);
    if (!file) throw std::invalid_argument("cannot open model file");
    std::array<char, 4097> bytes{};
    file.read(bytes.data(), static_cast<std::streamsize>(bytes.size()));
    const auto count = file.gcount();
    if (count < 1 || count > 4096 || file.bad()) throw std::invalid_argument("model size/read error");
    const std::string text(bytes.data(), static_cast<std::size_t>(count));
    if (picosha2::hash256_hex_string(text) != expected_sha256) throw std::invalid_argument("model SHA-256 mismatch");
    std::istringstream in(text);
    std::vector<std::string> tokens;
    for (std::string token; in >> token;) tokens.push_back(token);
    const bool expanded = tokens.size() > 2 && tokens[0] == "ucl-linear-v2" && tokens[2] == "interpretable-v2";
    const std::size_t dimension = expanded ? 14 : 8;
    const std::array<std::string_view, 11> prefix{expanded ? "ucl-linear-v2" : "ucl-linear-v1", "features",
        expanded ? "interpretable-v2" : "handcrafted-v1", "perspective", "white", "temperature", "400",
        "intercept", "0", "weights", expanded ? "14" : "8"};
    if (tokens.size() != dimension + 16 || !std::equal(prefix.begin(), prefix.end(), tokens.begin()) ||
        tokens[11 + dimension] != "dataset_sha256" || tokens[13 + dimension] != "split_sha256" ||
        tokens[15 + dimension] != "end" || !valid_hash(tokens[12 + dimension]) || !valid_hash(tokens[14 + dimension]))
        throw std::invalid_argument("model schema/version mismatch");
    std::vector<double> weights(dimension);
    for (std::size_t i = 0; i < weights.size(); ++i) {
        const auto& token = tokens[i + 11];
        const auto [end, error] = std::from_chars(token.data(), token.data() + token.size(), weights[i]);
        if (error != std::errc{} || end != token.data() + token.size() || !std::isfinite(weights[i]) ||
            std::abs(weights[i]) > 10000) throw std::invalid_argument("invalid model weight");
    }
    static const InterpretableFeatures extended;
    return LinearEvaluator(expanded ? static_cast<const FeatureExtractor&>(extended) : features,
                           std::move(weights), expected_sha256);
}
double LinearEvaluator::white_score(const chess::Board& board) const {
    const auto values = features_.extract(board);
    if (values.size() != weights_.size()) throw std::invalid_argument("linear feature dimension mismatch");
    double score = 0;
    for (std::size_t i = 0; i < weights_.size(); ++i) {
        if (!std::isfinite(values[i])) throw std::invalid_argument("nonfinite linear feature");
        score += static_cast<double>(values[i]) * weights_[i];
    }
    // Valid handcrafted-v1 chess features are far below this conversion bound.
    if (!std::isfinite(score) || std::abs(score) > 100000000) throw std::invalid_argument("linear score out of range");
    return score;
}
int LinearEvaluator::evaluate(const chess::Board& board) const {
    const int cp = static_cast<int>(std::lround(white_score(board)));
    return board.sideToMove() == chess::Color::WHITE ? cp : -cp;
}
} // namespace ucl
