#include "ucl/uci.hpp"
#include "ucl/position.hpp"
#include "ucl/search.hpp"
#include <algorithm>
#include <charconv>
#include <condition_variable>
#include <iostream>
#include <mutex>
#include <memory>
#include <sstream>
#include <stdexcept>
#include <thread>

namespace ucl {
namespace {
std::int64_t integer(const std::string& s, std::int64_t lo, std::int64_t hi) {
    std::int64_t n = 0;
    const auto [end, ec] = std::from_chars(s.data(), s.data() + s.size(), n);
    if (ec != std::errc{} || end != s.data() + s.size() || n < lo || n > hi)
        throw std::invalid_argument("invalid numeric argument");
    return n;
}
struct Go { SearchLimits limits; bool infinite = false; };
Go parse_go(const std::vector<std::string>& t, chess::Color side, int overhead) {
    Go go;
    go.limits.depth = max_depth;
    std::optional<std::int64_t> remaining, movetime;
    std::int64_t increment = 0, moves = 30;
    bool limited = false;
    for (std::size_t i = 1; i < t.size(); ++i) {
        const auto key = t[i];
        if (key == "infinite") { go.infinite = true; continue; }
        if (key != "depth" && key != "nodes" && key != "movetime" && key != "wtime" && key != "btime" &&
            key != "winc" && key != "binc" && key != "movestogo") throw std::invalid_argument("unsupported go field: " + key);
        if (++i == t.size()) throw std::invalid_argument("missing go value");
        const auto n = integer(t[i], key == "depth" || key == "nodes" || key == "movestogo" ? 1 : 0, 1000000000000LL);
        if (key == "depth") { go.limits.depth = static_cast<int>(std::min<std::int64_t>(n, max_depth)); limited = true; }
        else if (key == "nodes") { go.limits.nodes = static_cast<std::uint64_t>(n); limited = true; }
        else if (key == "movetime") movetime = n;
        else if (key == "movestogo") moves = n;
        else if ((key == "wtime" && side == chess::Color::WHITE) || (key == "btime" && side == chess::Color::BLACK)) remaining = n;
        else if ((key == "winc" && side == chess::Color::WHITE) || (key == "binc" && side == chess::Color::BLACK)) increment = n;
    }
    if (!go.infinite) {
        if (movetime) go.limits.time = std::chrono::milliseconds(std::max<std::int64_t>(0, *movetime - overhead));
        else if (remaining) {
            const auto available = std::max<std::int64_t>(0, *remaining - overhead);
            go.limits.time = std::chrono::milliseconds(std::min(available, available / moves + increment / 2));
        } else if (!limited) go.limits.depth = 5;
    }
    return go;
}
} // namespace
int run_uci(std::istream& in, std::ostream& out) {
    std::mutex output_mutex;
    auto emit = [&](const std::string& line) { const std::lock_guard lock(output_mutex); out << line << '\n' << std::flush; };
    HandcraftedFeatures features;
    auto handcrafted = std::make_shared<HandcraftedEvaluator>(features);
    std::shared_ptr<LinearEvaluator> linear;
    std::shared_ptr<const Evaluator> evaluator = handcrafted;
    std::string expected_model_hash;
    auto identity = [&] {
        return std::string("{\"evaluator\":\"") + std::string(evaluator->name()) + "\",\"model_sha256\":" +
            (evaluator == linear ? "\"" + linear->model_sha256() + "\"" : "null");
    };
    chess::Board board;
    int overhead = 10;
    SearchOptions options;
    std::jthread worker;
    auto stop = [&] { if (worker.joinable()) { worker.request_stop(); worker.join(); } };
    std::string line;
    while (std::getline(in, line)) {
        if (!line.empty() && line.back() == '\r') line.pop_back();
        std::istringstream stream(line);
        std::vector<std::string> t;
        for (std::string word; stream >> word;) t.push_back(word);
        if (t.empty()) continue;
        try {
            if (t[0] == "uci") {
                emit("id name Ultramarine Chess Lab " UCL_VERSION);
                emit("id author UCL contributors");
                emit("option name MoveOverhead type spin default 10 min 0 max 5000");
                emit("option name Quiescence type check default true");
                emit("option name UseTT type check default true");
                emit("option name Hash type spin default 16 min 1 max 1024");
                emit("option name PVOrdering type check default true");
                emit("option name Evaluator type combo default Handcrafted var Handcrafted var Linear");
                emit("option name ModelSHA256 type string default <empty>");
                emit("option name ModelFile type string default <empty>");
                emit("uciok");
            } else if (t[0] == "isready") emit("readyok");
            else if (t[0] == "stop") stop();
            else if (t[0] == "quit") { stop(); break; }
            else if (t[0] == "ucinewgame") { stop(); board = chess::Board(); }
            else if (t[0] == "evalinfo") emit("info string ucl_evaluator " + identity() + "}");
            else if (t[0] == "eval") emit("info string ucl_eval " + identity() + ",\"score_cp\":" + std::to_string(evaluator->evaluate(board)) + "}");
            else if (t[0] == "setoption") {
                if (t.size() == 5 && t[1] == "name" && t[2] == "Evaluator" && t[3] == "value") {
                    if (t[4] != "Handcrafted" && t[4] != "Linear") throw std::invalid_argument("unknown Evaluator");
                    if (t[4] == "Linear" && !linear) throw std::invalid_argument("Linear requires a validated ModelFile and ModelSHA256");
                    stop();
                    evaluator = t[4] == "Handcrafted" ? std::shared_ptr<const Evaluator>(handcrafted) : linear;
                } else if (t.size() == 5 && t[1] == "name" && t[2] == "ModelSHA256" && t[3] == "value") {
                    if (t[4].size() != 64 || !std::all_of(t[4].begin(), t[4].end(), [](char c) {
                        return (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f');
                    })) throw std::invalid_argument("expected 64 lowercase hex SHA-256");
                    expected_model_hash = t[4];
                } else if (t.size() >= 5 && t[1] == "name" && t[2] == "ModelFile" && t[3] == "value") {
                    // Keep spaces in paths; only the fixed UCI prefix is parsed as tokens.
                    const auto value_at = line.find(" value ");
                    if (value_at == std::string::npos) throw std::invalid_argument("ModelFile requires value");
                    const auto path = line.substr(value_at + 7);
                    auto candidate = std::make_shared<LinearEvaluator>(LinearEvaluator::load(features, path, expected_model_hash));
                    const bool active_linear = evaluator == linear;
                    stop();
                    linear = std::move(candidate);
                    if (active_linear) evaluator = linear;
                    emit("info string model loaded SHA256 " + linear->model_sha256());
                } else if (t.size() == 5 && t[1] == "name" && t[2] == "MoveOverhead" && t[3] == "value")
                    overhead = static_cast<int>(integer(t[4], 0, 5000));
                else if (t.size() == 5 && t[1] == "name" && t[3] == "value" && (t[2] == "Quiescence" || t[2] == "UseTT" || t[2] == "PVOrdering")) {
                    if (t[4] != "true" && t[4] != "false") throw std::invalid_argument("expected true/false");
                    if (t[2] == "Quiescence") options.quiescence = t[4] == "true";
                    else if (t[2] == "UseTT") options.tt = t[4] == "true";
                    else options.pv_ordering = t[4] == "true";
                } else if (t.size() == 5 && t[1] == "name" && t[3] == "value" && t[2] == "Hash")
                    options.hash_mb = static_cast<std::size_t>(integer(t[4], 1, 1024));
                else emit("info string unsupported option");
            } else if (t[0] == "position") {
                stop();
                std::string error;
                if (!parse_position(t, board, error)) emit("info string position rejected: " + error);
            } else if (t[0] == "go") {
                auto go = parse_go(t, board.sideToMove(), overhead);
                stop();
                worker = std::jthread([&, position = board, go, search_options = options, active_eval = evaluator](std::stop_token token) {
                    try {
                        AlphaBetaSearch search(search_options);
                        auto result = search.run(position, *active_eval, go.limits, token, [&](const SearchResult& r) {
                            std::ostringstream s;
                            s << "info depth " << r.depth << " score ";
                            if (std::abs(r.score) >= mate_score - max_search_ply) {
                                const int plies = mate_score - std::abs(r.score);
                                s << "mate " << (r.score >= 0 ? 1 : -1) * ((plies + 1) / 2);
                            } else s << "cp " << r.score;
                            s << " nodes " << r.nodes << " time " << r.elapsed.count()
                              << " nps " << r.nodes * 1000 / static_cast<std::uint64_t>(std::max<std::int64_t>(1, r.elapsed.count())) << " pv";
                            for (auto move : r.pv) s << ' ' << chess::uci::moveToUci(move);
                            emit(s.str());
                        });
                        // UCI infinite searches publish only after stop, even when mate is found.
                        if (go.infinite && !token.stop_requested()) {
                            std::mutex wait_mutex;
                            std::condition_variable_any wake;
                            std::unique_lock lock(wait_mutex);
                            wake.wait(lock, token, [] { return false; });
                        }
                        std::ostringstream stats;
                        stats << "info string ucl_stats {\"depth\":" << result.depth << ",\"score_cp\":" << result.score
                              << ",\"nodes\":" << result.nodes << ",\"qnodes\":" << result.qnodes
                              << ",\"tt_probes\":" << result.tt_probes << ",\"tt_hits\":" << result.tt_hits
                              << ",\"tt_cutoffs\":" << result.tt_cutoffs << ",\"tt_stores\":" << result.tt_stores
                              << ",\"pv_order_hits\":" << result.pv_order_hits << ",\"tt_order_hits\":" << result.tt_order_hits
                              << ",\"elapsed_us\":" << result.elapsed_us.count() << "}";
                        emit(stats.str());
                        emit("bestmove " + (result.best_move ? chess::uci::moveToUci(*result.best_move) : "0000"));
                    } catch (const std::exception& e) { emit(std::string("info string search error: ") + e.what()); emit("bestmove 0000"); }
                });
            }
        } catch (const std::exception& e) { emit(std::string("info string command rejected: ") + e.what()); }
    }
    stop();
    return 0;
}
} // namespace ucl
