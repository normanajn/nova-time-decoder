# Getting Started with nova-time-decoder

`nova-time-decoder` encodes and decodes **NOvA DAQ timestamps**: it converts
between NOvA base time (64 MHz clock ticks since the 2010 NOvA epoch), UNIX
time, **GPS time**, and civil calendar dates. It ships as both a command-line
tool (`nova-time-convert`) and a pure-Python library (`nova_time_decoder`), with
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
  a GPS time of week 1593, TOW 396075.000000000 (963842475.000000000 s)
  a calendar date of 2010-Jul-22 14:01:00.000000000000 UTC
```

Every conversion reports the **GPS time** too (see [GPS time](#5-gps-time)).

How the input is detected:

| Input looks like            | Interpreted as     | Example                                  |
|-----------------------------|--------------------|------------------------------------------|
| contains `:`                | datetime string    | `"2010-Jul-22 14:22:30.5 UTC"`           |
| contains `.` (but no `:`)   | UNIX `sec.frac`    | `1279807260.005`                         |
| bare integer / `0x...`      | NOvA base time     | `1120208640000000`, `0x43d950a5b0000`    |
| (never auto-detected)       | GPS time — needs `--gps` | `--gps 1025136016`, `--gps 1695:259216` |

You can force the mode with `--nova`, `--unix`, `--datetime`, or `--gps`.
Datetime strings are treated as **local time** unless they end in `UTC` or you
pass `--utc`. GPS input is never auto-detected because GPS seconds look just
like UNIX seconds, so it must be requested explicitly with `--gps`.

More examples:

```bash
nova-time-convert 0x43d950a5b0000                       # NOvA time in hex
nova-time-convert 1279807260.005                        # UNIX time
nova-time-convert "2010-Jul-22 14:22:30.000000015625 UTC"   # civil time (UTC)
nova-time-convert "2010-Jul-22 09:01"                   # civil time (local)
nova-time-convert --gps 1025136016                      # GPS seconds
nova-time-convert --gps 1695:259216                     # GPS week:time-of-week
nova-time-convert --now                                 # current time
```

### Printing a single value (for scripting)

By default the tool prints a short report of every representation. To get just
one value — with no surrounding text, on a single line — use one of the
mutually exclusive `--output-*` flags:

| Flag              | Prints                                            |
|-------------------|---------------------------------------------------|
| `--output-nova`   | the NOvA base time (tick count)                   |
| `--output-gps`    | the GPS time in seconds since the GPS epoch       |
| `--output-utc`    | the UTC calendar date string                      |
| `--output-local`  | the local-time calendar date string (with TZ)     |

```console
$ nova-time-convert --output-nova 1279807260.005
1120208640320000

$ nova-time-convert --output-gps 1120208640000000
963842475

$ nova-time-convert --now --output-utc
2026-Jul-06 20:25:04.109338984375 UTC

$ nova-time-convert --gps --output-utc 1025136016
2012-Jul-01 00:00:00.000000000000 UTC
```

If the requested representation does not exist for the instant (e.g. a NOvA or
GPS value for a time before the NOvA epoch), the tool prints an error to stderr
and exits with status 1.

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

## 5. GPS time

GPS time is the continuous (leap-second-free) count of seconds since the GPS
epoch, **06-Jan-1980 00:00:00 UTC**. Because both NOvA time and GPS time are
continuous atomic timescales, the NOvA ↔ GPS conversion is an exact fixed
integer-second offset — **no leap-second table is involved**. Only the
GPS ↔ UNIX/civil conversion uses leap seconds.

```python
from nova_time_decoder import (
    nova_to_gps, gps_to_nova, unix_to_gps, gps_to_unix,
    gps_from_week_tow, gps_to_string,
)

# NOvA <-> GPS (exact, no leap seconds).
gps = nova_to_gps(5042995264000000)   # 2012-07-01 00:00:00 UTC
print(gps.seconds, gps.week, gps.tow) # 1025136016 1695 16
print(gps_to_nova(gps.seconds, gps.nsec))   # 5042995264000000

# UNIX <-> GPS (leap seconds applied).
print(unix_to_gps(1341100800).seconds)      # 1025136016
print(gps_to_unix(1025136016).sec)          # 1341100800

# Build from week / time-of-week, and format.
g = gps_from_week_tow(1695, 16)
print(gps_to_string(g))   # week 1695, TOW 16.000000000 (1025136016.000000000 s)
```

A `GpsTime` is a `NamedTuple(seconds, nsec)` with `.week` (full week number)
and `.tow` (whole-second time-of-week) properties. The GPS functions return
`None` for instants before the NOvA epoch, matching the NOvA conversions.

---

## 6. Leap seconds

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

## 7. Running the tests

```bash
python -m pytest
```

The suite ports the original CppUnit tests from `NovaTimingUtilities` plus
extra round-trip and precision checks.

---

## 8. Reading the manpages without installing

```bash
man ./man/nova-time-convert.1
man ./man/nova_time_decoder.3
```
