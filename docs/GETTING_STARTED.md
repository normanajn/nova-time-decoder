# Getting Started with nova-time-decoder

`nova-time-decoder` encodes and decodes **NOvA DAQ timestamps**: it converts
between NOvA base time (64 MHz clock ticks since the 2010 NOvA epoch), UNIX
time, and civil calendar dates. It ships as both a command-line tool
(`nova-time-convert`) and a pure-Python library (`nova_time_decoder`), with
**no third-party dependencies** — only the Python standard library.

It is a self-contained reimplementation of the NOvA DAQ `NovaTimingUtilities`
package (`novadaq::timeutils` / `NovaTimeConvert`).

---

## 1. Requirements

- Python **3.9 or newer** (works on Linux, macOS, and Windows 11).
- Nothing else. There are no runtime dependencies; `pytest` is only needed to
  run the test suite.

Check your Python:

```bash
python3 --version
```

---

## 2. Install

### Quick bootstrap (Linux / macOS / Git Bash on Windows)

```bash
./bootstrap.sh
source venv/bin/activate      # POSIX
# source venv/Scripts/activate   # Git Bash on Windows
```

`bootstrap.sh` creates a `venv/` virtual environment, upgrades `pip`, and
installs the package in editable mode with the test extras. It is safe to
re-run to update an existing environment. Override the interpreter with
`PYTHON=python3.9 ./bootstrap.sh`.

### Manual install (any platform)

```bash
python3 -m venv venv
# Linux/macOS:
source venv/bin/activate
# Windows cmd.exe:
venv\Scripts\activate.bat
# Windows PowerShell:
venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
python -m pip install -e ".[test]"
```

### Use without installing

Because the library is pure standard library, you can also just point
`PYTHONPATH` at `src/`:

```bash
PYTHONPATH=src python -c "from nova_time_decoder import current_nova_time; print(current_nova_time())"
```

---

## 3. Command-line usage

The `nova-time-convert` command takes a single time value, auto-detects which
representation it is, and prints all three.

```console
$ nova-time-convert 1120208640000000

A NOvA base time of 1120208640000000 corresponds to...
  a UNIX time of 1279807260 sec, 0 nsec
  a calendar date of 2010-Jul-22 14:01:00.000000000000 UTC
```

How the input is detected:

| Input looks like            | Interpreted as     | Example                                  |
|-----------------------------|--------------------|------------------------------------------|
| contains `:`                | datetime string    | `"2010-Jul-22 14:22:30.5 UTC"`           |
| contains `.` (but no `:`)   | UNIX `sec.frac`    | `1279807260.005`                         |
| bare integer / `0x...`      | NOvA base time     | `1120208640000000`, `0x43d950a5b0000`    |

You can force the mode with `--nova`, `--unix`, or `--datetime`. Datetime
strings are treated as **local time** unless they end in `UTC` or you pass
`--utc`.

More examples:

```bash
nova-time-convert 0x43d950a5b0000                       # NOvA time in hex
nova-time-convert 1279807260.005                        # UNIX time
nova-time-convert "2010-Jul-22 14:22:30.000000015625 UTC"   # civil time (UTC)
nova-time-convert "2010-Jul-22 09:01"                   # civil time (local)
nova-time-convert --now                                 # current time
```

See `man nova-time-convert` (or `man/nova-time-convert.1`) for the full
reference, including the `--leap-seconds` / `NOVA_LEAP_SECONDS` override.

---

## 4. Library usage

```python
from nova_time_decoder import (
    unix_to_nova, nova_to_unix, nova_to_string, current_nova_time,
    fields_to_nova, nova_to_fields,
)

# Encode a UNIX time (seconds, nanoseconds) as a NOvA tick count.
nova = unix_to_nova(1279807260, 5_000_000)
print(nova)                       # 1120208640320000

# Decode it back.
unix = nova_to_unix(nova)
print(unix.sec, unix.nsec)        # 1279807260 5000000

# Human-readable string (picosecond precision).
print(nova_to_string(nova))       # 2010-Jul-22 14:01:00.005000000000 UTC

# Broken-down UTC calendar fields (struct tm conventions: mon 0-11, year-1900).
nova = fields_to_nova(12, 11, 10, 4, 1, 110)   # Feb 4, 2010 10:11:12 UTC
print(nova_to_fields(nova))       # (12, 11, 10, 4, 1, 110)

# Current time as NOvA ticks.
print(current_nova_time())
```

`unix_to_nova` (and the other encoders) return `None` for instants before the
NOvA epoch (01-Jan-2010 00:00:00 UTC).

See `man nova_time_decoder` (or `man/nova_time_decoder.3`) for the full API.

---

## 5. Leap seconds

NOvA time has no leap seconds; UNIX time does. The library adds/removes the
leap seconds inserted **after** the NOvA epoch. The default table covers the
2012, 2015, and 2016 leap seconds (there have been none since). Override it if
a future leap second is added:

```bash
# CLI
nova-time-convert --leap-seconds 1341100799,1435708799,1483228799 <time>
export NOVA_LEAP_SECONDS=1341100799,1435708799,1483228799
```

```python
# Library: every conversion function takes a leap_seconds= keyword.
unix_to_nova(sec, nsec, leap_seconds=(1341100799, 1435708799, 1483228799))
```

---

## 6. Running the tests

```bash
python -m pytest
```

The suite ports the original CppUnit tests from `NovaTimingUtilities` plus
extra round-trip and precision checks.

---

## 7. Reading the manpages without installing

```bash
man ./man/nova-time-convert.1
man ./man/nova_time_decoder.3
```
