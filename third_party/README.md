# Pinned dependencies

`chess-library/chess.hpp` is the unmodified single header from
[Disservin/chess-library](https://github.com/Disservin/chess-library), commit
`53e6a841dcda7059a2af363d85f785ef1817304a`. Its MIT license is included.
Vendoring makes engine builds independent of network access. Update the header,
license and commit together, then rerun perft and all tests.

fastchess is an external executable; `scripts/bootstrap_fastchess.py` pins
`ebfd64cb7fac80d4822c50b07dca4fe934779d21`. It is not linked into UCL.

`picosha2/picosha2.h` and MIT license are unmodified from
[okdshin/PicoSHA2](https://github.com/okdshin/PicoSHA2), commit
`161cb3fc4170fa7a3eca9e582cebd27cc4d1fe29`. Header SHA-256:
`b13c180161ffac8d0adc81e033e493c409457c4d1258ab9781ac80579ba3bdd8`. Used only for model-file integrity,
with no runtime/network dependency.

The local GUI vendors the unmodified runtime subset of
[shaack/cm-chessboard 8.12.7](https://github.com/shaack/cm-chessboard) under
`python/ucl/web/vendor/cm-chessboard`: core ES modules, Markers/PromotionDialog,
their CSS/SVG, and the standard Wikimedia piece sprite. Code license: MIT,
included in that directory. The standard sprite includes its original Wikimedia
attribution and [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/)
notice; the page also displays attribution. The Staunty set is not included.
Source: `https://registry.npmjs.org/cm-chessboard/-/cm-chessboard-8.12.7.tgz`;
archive SHA-256 `f5d1bab18a3e93ad5456917da681a4ab12e1a50582ebdf333f5b1e6f04821a6e`.
The archive's npm SHA-512 integrity was verified before copying. All files are
served locally; no npm install, bundler or CDN is used at runtime.
