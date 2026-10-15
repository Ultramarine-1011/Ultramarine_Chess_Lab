#pragma once
#include <chess.hpp>
#include <array>
#include <string_view>
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
} // namespace ucl
