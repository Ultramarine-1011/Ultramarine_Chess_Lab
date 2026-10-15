#include "ucl/uci.hpp"
#include "ucl/build_info.hpp"
#include "ucl/evaluator.hpp"
#include "ucl/position.hpp"
#include <iostream>
#include <string>
#include <string_view>
#include <sstream>
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
    if (argc == 2 && std::string_view(argv[1]) == "--features") {
        ucl::HandcraftedFeatures features;
        ucl::HandcraftedEvaluator evaluator(features);
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
            const auto values = features.extract(board);
            std::cout << "{\"feature_version\":\"handcrafted-v1\",\"features\":[";
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
