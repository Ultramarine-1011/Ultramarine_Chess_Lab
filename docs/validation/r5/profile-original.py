"""Component-removal microprofile of frozen Original; diagnostic, not additive costs.

Run from an MSVC dev shell after committing this script. Every generated source,
compile command and raw timing remains in .tools/r5-profile. Component deletion
changes only this standalone diagnostic; no experiment engine is modified.
"""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'python'))
from ucl.r5_study import ORIGINAL
from ucl.records import git_state, sha256, write_json

out = ROOT/'.tools/r5-profile'
out.mkdir(exist_ok=False)
source = subprocess.check_output(['git', 'show', f'{ORIGINAL}:engine/src/extended_features.cpp'], cwd=ROOT, text=True)
begin = source.index('std::vector<float> InterpretableFeatures::extract')
body = source[begin:source.rindex('} // namespace ucl')].replace('InterpretableFeatures::extract', 'all').replace(') const {', ') {')
ring_start, ring_end = body.index('        auto ring = '), body.index('        const int centrality = ')
no_ring = body[:ring_start] + body[ring_end:]
pass_start, pass_end = body.index('            bool passed = true;'), body.index('            const int advancement = ')
no_pass = body[:pass_start] + '            bool passed = false;\n' + body[pass_end:]
prefix = '#include "ucl/evaluator.hpp"\n#include <algorithm>\n#include <array>\n#include <cmath>\n#include <chrono>\n#include <iostream>\n#include <random>\n'
functions = '\nnamespace ucl {\n' + body + no_ring.replace(' all(', ' no_ring(') + no_pass.replace(' all(', ' no_pass(') + '\n}\n'
main = r'''
int main() {
  using Function = std::vector<float>(*)(const chess::Board&);
  const std::array<Function,3> functions{ucl::all, ucl::no_ring, ucl::no_pass};
  const std::array<const char*,3> names{"all", "no_ring", "no_pass"};
  std::mt19937 rng(20261016);
  for (std::string fen; std::getline(std::cin,fen);) {
    chess::Board board(fen);
    for (int repeat=0; repeat<7; ++repeat) {
      std::array<int,3> order{0,1,2}; std::shuffle(order.begin(),order.end(),rng);
      for (int variant: order) {
        double checksum=0;
        auto start=std::chrono::steady_clock::now();
        for (int i=0;i<100000;++i) {
          auto f=functions[static_cast<std::size_t>(variant)](board);
          for (float v:f) checksum+=v;
        }
        auto ns=std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now()-start).count();
        std::cout<<"{\"variant\":\""<<names[static_cast<std::size_t>(variant)]<<"\",\"repeat\":"<<repeat
                 <<",\"ns\":"<<ns<<",\"iterations\":100000,\"checksum\":"<<checksum<<"}\n";
      }
    }
  }
}
'''
(out/'profile.cpp').write_text(prefix+functions+main)
evaluator = subprocess.check_output(['git', 'show', f'{ORIGINAL}:engine/src/evaluator.cpp'], cwd=ROOT)
(out/'evaluator.cpp').write_bytes(evaluator)
command = ['cl', '/nologo', '/std:c++20', '/EHsc', '/O2', '/Ob2', '/DNDEBUG', '/DWIN32', '/D_WINDOWS', '/utf-8',
           '/I'+str(ROOT/'engine/include'), '/I'+str(ROOT/'third_party/chess-library'),
           str(out/'profile.cpp'), str(out/'evaluator.cpp'), '/Fe:'+str(out/'profile.exe')]
with (out/'build.log').open('w') as log:
    subprocess.run(command, cwd=out, stdout=log, stderr=subprocess.STDOUT, check=True)
suite = json.loads((ROOT/'experiments/positions/r2-v1.json').read_text())
result = subprocess.run([str(out/'profile.exe')], input='\n'.join(p['fen'] for p in suite['positions'])+'\n',
                        text=True, capture_output=True, check=True)
rows = [dict(json.loads(line), position=suite['positions'][i//21]['id']) for i,line in enumerate(result.stdout.splitlines())]
write_json(ROOT/'docs/validation/r5/profile-original.json', {'code': git_state(ROOT), 'original': ORIGINAL,
    'method': 'alternating component-removal microprofile; deltas include compiler/code interactions, not an additive decomposition',
    'commands': [command, [str(out/'profile.exe')]], 'profile_source_sha256': sha256(out/'profile.cpp'),
    'binary_sha256': sha256(out/'profile.exe'), 'rows': rows})
print('profile complete:', len(rows), 'raw rows')
