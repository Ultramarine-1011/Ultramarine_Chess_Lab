#include "ucl/uci.hpp"
#include "ucl/build_info.hpp"
#include <iostream>
#include <string>
#include <string_view>
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
