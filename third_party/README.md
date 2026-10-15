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
