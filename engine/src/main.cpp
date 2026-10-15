#include "ucl/uci.hpp"
#include "ucl/build_info.hpp"
#include "ucl/evaluator.hpp"
#include "ucl/position.hpp"
#include <iostream>
#include <string>
#include <string_view>
#include <sstream>
#include <iomanip>
#include <optional>
#include <chrono>
namespace {
std::string json_string(std::string_view text) {
    std::string result = "\"";
    for (char c : text) {
        if (c == '\\' || c == '"') result += '\\';
        if (c == '\n') result += "\\n";
        else if (c == '\r') result += "\\r";
        else if (c == '\t') result += "\\t";
        else result += c;
    }
    return result + '"';
}
}
int main(int argc, char** argv) {
    if ((argc == 2 && (std::string_view(argv[1]) == "--features" || std::string_view(argv[1]) == "--features-v2")) ||
        (argc == 4 && (std::string_view(argv[1]) == "--infer" || std::string_view(argv[1]) == "--eval-benchmark"))) {
        ucl::HandcraftedFeatures features;
        ucl::InterpretableFeatures extended;
        ucl::HandcraftedEvaluator evaluator(features);
        std::optional<ucl::LinearEvaluator> linear;
        if (argc == 4) {
            try { linear.emplace(ucl::LinearEvaluator::load(features, argv[2], argv[3])); }
            catch (const std::exception& e) { std::cerr << "model rejected: " << e.what() << '\n'; return 1; }
        }
        std::cout << std::setprecision(17);
        for (std::string fen; std::getline(std::cin, fen);) {
            std::istringstream words("position fen " + fen);
            std::vector<std::string> tokens;
            for (std::string word; words >> word;) tokens.push_back(word);
            chess::Board board;
            std::string error;
            if (!ucl::parse_position(tokens, board, error)) {
                std::cerr << "feature export rejected: " << error << '\n';
                return 1;
            }
            const auto& active_features = argc == 2 && std::string_view(argv[1]) == "--features-v2"
                ? static_cast<const ucl::FeatureExtractor&>(extended) : features;
            const auto values = active_features.extract(board);
            if (linear && std::string_view(argv[1]) == "--eval-benchmark") {
                constexpr int iterations = 100000;
                for (int repeat = 0; repeat < 7; ++repeat) {
                    std::int64_t checksum = 0;
                    auto measure = [&](const ucl::Evaluator& active) {
                        const auto start = std::chrono::steady_clock::now();
                        for (int i = 0; i < iterations; ++i) checksum += active.evaluate(board);
                        return std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now()-start).count();
                    };
                    std::int64_t hand_ns = 0, linear_ns = 0;
                    if (repeat % 2 == 0) { hand_ns = measure(evaluator); linear_ns = measure(*linear); }
                    else { linear_ns = measure(*linear); hand_ns = measure(evaluator); }
                    std::cout << "{\"repeat\":" << repeat << ",\"iterations\":" << iterations
                              << ",\"handcrafted_ns\":" << hand_ns << ",\"linear_ns\":" << linear_ns
                              << ",\"checksum\":" << checksum << ",\"model_sha256\":\"" << linear->model_sha256() << "\"}\n";
                }
                continue;
            }
            if (linear) {
                std::cout << "{\"score_cp\":" << linear->evaluate(board) << ",\"white_score\":"
                          << linear->white_score(board) << ",\"model_sha256\":\"" << linear->model_sha256() << "\"}\n";
                continue;
            }
            std::cout << "{\"feature_version\":\"" << active_features.name() << "\",\"features\":[";
            for (std::size_t i = 0; i < values.size(); ++i) {
                if (i) std::cout << ',';
                std::cout << values[i];
            }
            std::cout << "],\"handcrafted_cp\":" << evaluator.evaluate(board) << "}\n";
        }
        return 0;
    }
    if (argc == 2 && std::string_view(argv[1]) == "--build-info") {
        std::cout << "{\"version\":" << json_string(UCL_VERSION)
                  << ",\"revision\":" << json_string(UCL_BUILD_REVISION)
                  << ",\"dirty\":" << (UCL_BUILD_DIRTY ? "true" : "false")
                  << ",\"compiler\":" << json_string(UCL_BUILD_COMPILER)
                  << ",\"build_type\":" << json_string(UCL_BUILD_TYPE)
                  << ",\"flags\":" << json_string(UCL_BUILD_FLAGS) << "}\n";
        return 0;
    }
    return ucl::run_uci(std::cin, std::cout);
}
