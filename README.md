# nova-time-decoder

Encode and decode **NOvA DAQ timestamps** in pure Python — no third-party
dependencies.

`nova-time-decoder` converts between:

- **NOvA base time** — an unsigned 64-bit count of 64 MHz clock ticks since the
  NOvA epoch (01-Jan-2010 00:00:00 UTC),
- **UNIX time** — seconds and nanoseconds since 01-Jan-1970 UTC, and
- **civil calendar dates** (UTC).

It is a self-contained reimplementation of the NOvA DAQ `NovaTimingUtilities`
package (`novadaq::timeutils` C++ library and its `NovaTimeConvert` tool),
providing both a **command-line utility** (`nova-time-convert`) and an
importable **library** (`nova_time_decoder`). NOvA time contains no leap
seconds; UNIX time does, so post-epoch leap seconds are added or removed during
conversion.

## Quick start

```bash
./bootstrap.sh
source venv/bin/activate

nova-time-convert 1120208640000000
```

```console
A NOvA base time of 1120208640000000 corresponds to...
  a UNIX time of 1279807260 sec, 0 nsec
  a calendar date of 2010-Jul-22 14:01:00.000000000000 UTC
```

Library:

```python
from nova_time_decoder import unix_to_nova, nova_to_string

nova = unix_to_nova(1279807260, 5_000_000)
print(nova_to_string(nova))   # 2010-Jul-22 14:01:00.005000000000 UTC
```

## Features

- **Zero dependencies** — standard library only; Python 3.9+.
- **Cross-platform** — Linux, macOS, Windows 11.
- **Auto-detecting CLI** — pass a NOvA tick count (decimal or `0x` hex), a UNIX
  `sec.frac`, or a civil datetime string, and it prints all three forms.
- **Full library API** — encode/decode via UNIX times, `struct tm`, broken-down
  fields, and formatted strings, all with an overridable leap-second table.
- **Exact integer arithmetic** — avoids the floating-point precision loss the
  original C++ suffers for modern (large) timestamps, while remaining bit-for-bit
  compatible on values the C++ represented exactly.
- **Manpages** for both the command and the library.
- **Test suite** porting the original CppUnit tests.

## Documentation

- [Getting Started](docs/GETTING_STARTED.md) — install, CLI usage, library
  usage, leap seconds, tests.
- `man/nova-time-convert.1` — command-line reference (`man ./man/nova-time-convert.1`).
- `man/nova_time_decoder.3` — library API reference (`man ./man/nova_time_decoder.3`).

## Project layout

```
nova-time-decoder/
├── src/nova_time_decoder/    # library + CLI (core.py, cli.py)
├── tests/                    # pytest suite (ports the CppUnit tests)
├── man/                      # troff manpages (.1 for the CLI, .3 for the API)
├── docs/                     # Getting Started guide
├── bootstrap.sh             # create/update the venv and install
└── pyproject.toml
```

## Relationship to NovaTimingUtilities

This package reimplements the timestamp encode/decode capability of
`novadaq/pkgs/NovaTimingUtilities`. That package is self-contained (its only
external dependencies are Boost, for date parsing/formatting, and CppUnit, for
tests) and depends on **no other** `novadaq/pkgs` package, so nothing else
needed to be ported. Boost's date handling is replaced here by the Python
standard library (`time`, `calendar`).

## License

MIT.
