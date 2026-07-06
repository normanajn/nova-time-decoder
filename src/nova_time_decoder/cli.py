"""Command-line utility to encode/decode NOvA timestamps.

This is a pure-Python replacement for the ``NovaTimeConvert`` C++ tool from the
NOvA DAQ ``NovaTimingUtilities`` package.  Given a single time value it detects
which representation it is and prints the equivalent NOvA base time, UNIX time
and civil calendar date.

Three input representations are recognised (auto-detected, or forced with a
flag):

* **datetime string** -- contains a ``:`` , e.g. ``"2010-Jul-22 14:22:30.5"``.
  The fractional second is interpreted down to one picosecond.  If the string
  ends in ``UTC`` (or ``--utc`` is given) it is treated as UTC, otherwise as
  local time.
* **UNIX time** -- ``sec.frac`` with a dot but no colon, e.g.
  ``1279807260.005``.  The fractional second is interpreted down to one
  nanosecond.
* **NOvA base time** -- a bare integer, decimal or ``0x`` hex, e.g.
  ``1120208640000000`` or ``0x43d950a5b0000``.

Command-line options override environment variables which override built-in
defaults (currently only the leap-second table is configurable this way, via
``--leap-seconds`` / ``NOVA_LEAP_SECONDS``).
"""

from __future__ import annotations

import argparse
import calendar
import os
import sys
import time
from typing import Optional, Sequence, Tuple

from . import __version__
from .core import (
    DEFAULT_LEAP_SECONDS,
    NOVA_EPOCH,
    nova_to_string,
    nova_to_unix,
    unix_to_nova,
    unix_to_string,
)

# strptime formats tried, in order, for a datetime string.  Both month names
# (Jul) and month numbers (07) are accepted, with or without seconds.
_DATETIME_FORMATS = (
    "%Y-%b-%d %H:%M:%S",
    "%Y-%b-%d %H:%M",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
)


def parse_leap_seconds(text: Optional[str]) -> Sequence[int]:
    """Parse a comma-separated leap-second table, or return the default."""
    if not text:
        return DEFAULT_LEAP_SECONDS
    try:
        return tuple(int(part) for part in text.split(",") if part.strip())
    except ValueError as exc:
        raise ValueError("invalid --leap-seconds value: %r" % text) from exc


def parse_datetime_string(text: str) -> Tuple[str, int, bool]:
    """Split a datetime string into its civil part, picoseconds and UTC flag.

    Returns ``(civil_part, picoseconds, has_utc_suffix)`` where ``civil_part``
    is the ``YYYY-...-DD HH:MM[:SS]`` text with any fraction and ``UTC`` suffix
    removed.
    """
    has_utc = False
    working = text.strip()
    upper = working.upper()
    pos = upper.find("UTC")
    if pos != -1:
        working = working[:pos]
        has_utc = True
    working = working.strip()

    picoseconds = 0
    dot = working.find(".")
    if dot != -1:
        frac = working[dot + 1:]
        working = working[:dot]
        frac = (frac + "000000000000")[:12]
        picoseconds = int(frac)
    return working, picoseconds, has_utc


def datetime_string_to_unix(
    text: str, force_utc: Optional[bool] = None
) -> Tuple[int, int]:
    """Convert a datetime string to ``(unix_seconds, picoseconds)``.

    ``force_utc`` overrides the ``UTC`` suffix detection: ``True`` forces UTC,
    ``False`` forces local time, ``None`` (default) honours the suffix and
    otherwise treats the time as local (matching the original tool).
    """
    civil, picoseconds, has_utc = parse_datetime_string(text)

    tm = None
    for fmt in _DATETIME_FORMATS:
        try:
            tm = time.strptime(civil, fmt)
            break
        except ValueError:
            continue
    if tm is None:
        raise ValueError("unrecognised datetime string: %r" % text)

    use_utc = has_utc if force_utc is None else force_utc
    if use_utc:
        unix_sec = calendar.timegm(tm)
    else:
        unix_sec = int(time.mktime(tm))
    return unix_sec, picoseconds


def _emit(lines, out) -> None:
    for line in lines:
        out.write(line + "\n")


def decode_nova(nova_time: int, leap_seconds: Sequence[int], out) -> None:
    unix = nova_to_unix(nova_time, leap_seconds)
    _emit(
        [
            "",
            "A NOvA base time of %d corresponds to..." % nova_time,
            "  a UNIX time of %d sec, %d nsec" % (unix.sec, unix.nsec),
            "  a calendar date of %s" % nova_to_string(nova_time, leap_seconds),
            "",
        ],
        out,
    )


def decode_unix(
    sec: int, nsec: int, leap_seconds: Sequence[int], out
) -> None:
    nova = unix_to_nova(sec, nsec, leap_seconds)
    lines = ["", "A UNIX time of %d sec, %d nsec corresponds to..." % (sec, nsec)]
    if nova is not None:
        lines.append("  a NOvA base time of %d" % nova)
    else:
        lines.append("  an invalid NOvA base time")
    lines.append("  a calendar date of %s" % unix_to_string(sec, nsec))
    lines.append("")
    _emit(lines, out)


def decode_datetime(
    text: str,
    force_utc: Optional[bool],
    leap_seconds: Sequence[int],
    out,
) -> None:
    unix_sec, picoseconds = datetime_string_to_unix(text, force_utc)
    nsec = picoseconds // 1000
    lines = ["", "A time string of %s corresponds to..." % text]
    nova = unix_to_nova(unix_sec, nsec, leap_seconds) if unix_sec >= NOVA_EPOCH else None
    if nova is not None:
        lines.append("  a NOvA base time of %d" % nova)
        calendar_date = nova_to_string(nova, leap_seconds)
    else:
        lines.append("  an invalid NOvA base time")
        calendar_date = unix_to_string(unix_sec, nsec)
    lines.append("  a UNIX time of %d sec, %d nsec" % (unix_sec, nsec))
    lines.append("  a calendar date of %s" % calendar_date)
    lines.append("")
    _emit(lines, out)


def detect_mode(value: str) -> str:
    """Auto-detect the representation of ``value``: nova, unix or datetime."""
    if ":" in value:
        return "datetime"
    if "." in value:
        return "unix"
    return "nova"


def _parse_unix(value: str) -> Tuple[int, int]:
    dot = value.find(".")
    sec = int(value[:dot])
    frac = (value[dot + 1:] + "000000000")[:9]
    return sec, int(frac)


def _parse_nova(value: str) -> int:
    if "x" in value.lower():
        return int(value, 16)
    return int(value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nova-time-convert",
        description="Convert between NOvA base time, UNIX time and civil dates.",
        epilog=(
            "examples:\n"
            '  nova-time-convert "2010-Jul-22 14:22:30.000000015625"\n'
            '  nova-time-convert "2010-Jul-22 00:00 UTC"\n'
            "  nova-time-convert 1120208640000000\n"
            "  nova-time-convert 0x43d950a5b0000\n"
            "  nova-time-convert 1279807260.005\n"
            "  nova-time-convert --now"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "time",
        nargs="?",
        help="the time value to convert (datetime string, UNIX sec.frac, "
        "or NOvA tick count); omit with --now",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--nova", action="store_const", const="nova", dest="mode",
        help="force interpretation of the input as a NOvA base time",
    )
    mode.add_argument(
        "--unix", action="store_const", const="unix", dest="mode",
        help="force interpretation of the input as a UNIX sec.frac time",
    )
    mode.add_argument(
        "--datetime", action="store_const", const="datetime", dest="mode",
        help="force interpretation of the input as a civil datetime string",
    )
    tz = parser.add_mutually_exclusive_group()
    tz.add_argument(
        "--utc", action="store_true",
        help="interpret a datetime string as UTC (overrides suffix detection)",
    )
    tz.add_argument(
        "--local", action="store_true",
        help="interpret a datetime string as local time",
    )
    parser.add_argument(
        "--now", action="store_true",
        help="use the current time as the input (as a NOvA base time)",
    )
    parser.add_argument(
        "--leap-seconds", metavar="T1,T2,...",
        default=os.environ.get("NOVA_LEAP_SECONDS"),
        help="comma-separated UNIX time_t leap-second thresholds "
        "(overrides the NOVA_LEAP_SECONDS environment variable)",
    )
    parser.add_argument(
        "--version", action="version",
        version="nova-time-convert (nova_time_decoder) %s" % __version__,
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        leap_seconds = parse_leap_seconds(args.leap_seconds)
    except ValueError as exc:
        parser.error(str(exc))

    force_utc: Optional[bool] = None
    if args.utc:
        force_utc = True
    elif args.local:
        force_utc = False

    if args.now:
        from .core import current_nova_time
        decode_nova(current_nova_time(leap_seconds), leap_seconds, sys.stdout)
        return 0

    if args.time is None:
        parser.print_help(sys.stderr)
        return 2

    mode = args.mode or detect_mode(args.time)

    try:
        if mode == "nova":
            decode_nova(_parse_nova(args.time), leap_seconds, sys.stdout)
        elif mode == "unix":
            decode_unix(*_parse_unix(args.time), leap_seconds=leap_seconds, out=sys.stdout)
        else:
            decode_datetime(args.time, force_utc, leap_seconds, sys.stdout)
    except ValueError as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
