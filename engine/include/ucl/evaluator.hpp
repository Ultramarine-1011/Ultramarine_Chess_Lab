#pragma once
#include <chess.hpp>
#include <array>
#include <string_view>
#include <string>
#include <utility>
#include <vector>

namespace ucl {
// Stable feature order and perspective are part of an experiment's model contract.
class FeatureExtractor {
public:
    virtual ~FeatureExtractor() = default;
    [[nodiscard]] virtual std::vector<float> extract(const chess::Board&) const = 0;
    [[nodiscard]] virtual std::string_view name() const = 0;
};

class HandcraftedFeatures final : public FeatureExtractor {
public:
    [[nodiscard]] std::vector<float> extract(const chess::Board&) const override;
    [[nodiscard]] std::string_view name() const override { return "handcrafted-v1"; }
};

class Evaluator {
public:
    virtual ~Evaluator() = default;
    // Centipawns, positive for side to move. Terminal scores belong to Search.
    [[nodiscard]] virtual int evaluate(const chess::Board&) const = 0;
    [[nodiscard]] virtual std::string_view name() const = 0;
};

class HandcraftedEvaluator final : public Evaluator {
public:
    explicit HandcraftedEvaluator(const FeatureExtractor& features) : features_(features) {}
    [[nodiscard]] int evaluate(const chess::Board&) const override;
    [[nodiscard]] std::string_view name() const override { return "handcrafted-v1"; }
    static constexpr std::array<float, 8> weights{100, 320, 330, 500, 900, 5, 4, 30};
private:
    const FeatureExtractor& features_; // Must outlive this evaluator.
};

class LinearEvaluator final : public Evaluator {
public:
    // Loading is transactional: this function returns a fully validated value or throws.
    [[nodiscard]] static LinearEvaluator load(const FeatureExtractor&, const std::string& path,
                                               const std::string& expected_sha256);
    [[nodiscard]] int evaluate(const chess::Board&) const override;
    [[nodiscard]] std::string_view name() const override { return "linear-v1"; }
    [[nodiscard]] const std::string& model_sha256() const { return sha256_; }
    [[nodiscard]] double white_score(const chess::Board&) const;
private:
    LinearEvaluator(const FeatureExtractor& features, std::array<double, 8> weights, std::string hash)
        : features_(features), weights_(weights), sha256_(std::move(hash)) {}
    const FeatureExtractor& features_;
    std::array<double, 8> weights_;
    std::string sha256_;
};
} // namespace ucl
