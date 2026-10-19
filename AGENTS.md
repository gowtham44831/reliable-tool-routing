# Agent notes for this repository

## Environment setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[data]"
```

On macOS Apple Silicon with a very new macOS version and a Homebrew
Python that predates it, `pip`/`ensurepip` can crash inside
`pip._vendor.truststore` (`platform.mac_ver()` returns `''`), and
`import xml.parsers.expat` can fail with `Symbol not found:
_XML_SetAllocTrackerActivationThreshold` (Homebrew Python's `pyexpat.so`
links against `/usr/lib/libexpat.1.dylib`, which on very new macOS lacks a
symbol it expects). Fix:

```bash
brew install expat
export DYLD_LIBRARY_PATH=/opt/homebrew/opt/expat/lib
```

Export `DYLD_LIBRARY_PATH` in every shell used for this project (or add it
to your shell rc) before running `pip`, `python -m tool_routing.cli`, or
`pytest`.

## Commands

* Tests: `python -m pytest -q` (fast, no network, 41 tests as of writing).
* Toy end-to-end smoke test: `python -m tool_routing.cli smoke-test`.
* Download real data: `python scripts/download_toolret.py --queries <subsets...>`
  (needs `pip install -e ".[data]"` and network access).
* Full pilot run: `python -m tool_routing.cli run --config configs/pilot_toolret.yaml`.

## Conventions

* Raw/downloaded datasets (`data/raw/`), caches (`data/cache/`), and run
  outputs (`results/`) are git-ignored. Never commit them.
* Every new metric/abstention/scenario behavior should get a test in
  `tests/` using the toy fixture (`tool_routing.data.toy_fixture`) or a
  small inline fixture -- avoid requiring real ToolRet data in tests.
* Don't claim benchmark results from the toy fixture; it exists only for
  pipeline testing (see its module docstring).
