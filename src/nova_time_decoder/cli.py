"""Command-line utility to encode/decode NOvA timestamps.

This is a pure-Python replacement for the ``NovaTimeConvert`` C++ tool from the
NOvA DAQ ``NovaTimingUtilities`` package.  Given a single time value it detects
which representation it is and prints the equivalent NOvA base time, UNIX time,
GPS time and civil calendar date.

Input representations (auto-detected, or forced with a flag):

* **datetime string** -- contains a ``:`` , e.g. ``"2010-Jul-22 14:22:30.5"``.
  The fractional second is interpreted down to one picosecond.  If the string
  ends in ``UTC`` (or ``--utc`` is given) it is treated as UTC, otherwise as
  local time.
* **UNIX time** -- ``sec.frac`` with a dot but no colon, e.g.
  ``1279807260.005``.  The fractional second is interpreted down to one
  nanosecond.
* **NOvA base time** -- a bare integer, decimal or ``0x`` hex, e.g.
  ``1120208640000000`` or ``0x43d950a5b0000``.
* **GPS time** -- only when ``--gps`` is given (GPS seconds are numerically
  indistinguishable from UNIX seconds, so they cannot be auto-detected):
  ``seconds[.frac]`` or ``week:tow[.frac]``, e.g. ``1025136016`` or
  ``1695:259216``.

By default all representations are printed as a short report.  The
``--output-nova``, ``--output-gps``, ``--output-utc`` and ``--output-local``
flags instead print *only* that single value (with no surrounding text), which
is convenient for scripting; they are mutually exclusive.

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
from typing import NamedTuple, Optional, Sequence, Tuple

from . import __version__
from .core import (
    DEFAULT_LEAP_SECONDS,
    NOVA_EPOCH,
    GpsTime,
    UnixTime,
    current_nova_time,
    gps_from_week_tow,
    gps_to_nova,
    gps_to_string,
    gps_to_unix,
    nova_to_gps,
    nova_to_string,
    nova_to_unix,
    unix_to_gps,
    unix_to_local_string,
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


def _gps_line(gps: Optional[GpsTime]) -> str:
    if gps is None:
        return "  an invalid GPS time"
    return "  a GPS time of %s" % gps_to_string(gps)


def decode_nova(nova_time: int, leap_seconds: Sequence[int], out) -> None:
    unix = nova_to_unix(nova_time, leap_seconds)
    gps = nova_to_gps(nova_time)
    _emit(
        [
            "",
            "A NOvA base time of %d corresponds to..." % nova_time,
            "  a UNIX time of %d sec, %d nsec" % (unix.sec, unix.nsec),
            _gps_line(gps),
            "  a calendar date of %s" % nova_to_string(nova_time, leap_seconds),
            "",
        ],
        out,
    )


def decode_unix(
    sec: int, nsec: int, leap_seconds: Sequence[int], out
) -> None:
    nova = unix_to_nova(sec, nsec, leap_seconds)
    gps = unix_to_gps(sec, nsec, leap_seconds)
    lines = ["", "A UNIX time of %d sec, %d nsec corresponds to..." % (sec, nsec)]
    if nova is not None:
        lines.append("  a NOvA base time of %d" % nova)
    else:
        lines.append("  an invalid NOvA base time")
    lines.append(_gps_line(gps))
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
    gps = unix_to_gps(unix_sec, nsec, leap_seconds) if unix_sec >= NOVA_EPOCH else None
    if nova is not None:
        lines.append("  a NOvA base time of %d" % nova)
        calendar_date = nova_to_string(nova, leap_seconds)
    else:
        lines.append("  an invalid NOvA base time")
        calendar_date = unix_to_string(unix_sec, nsec)
    lines.append(_gps_line(gps))
    lines.append("  a UNIX time of %d sec, %d nsec" % (unix_sec, nsec))
    lines.append("  a calendar date of %s" % calendar_date)
    lines.append("")
    _emit(lines, out)


def decode_gps(
    gps: GpsTime, leap_seconds: Sequence[int], out
) -> None:
    nova = gps_to_nova(gps.seconds, gps.nsec)
    unix = gps_to_unix(gps.seconds, gps.nsec, leap_seconds)
    lines = ["", "A GPS time of %s corresponds to..." % gps_to_string(gps)]
    if nova is not None:
        lines.append("  a NOvA base time of %d" % nova)
    else:
        lines.append("  an invalid NOvA base time")
    if unix is not None:
        lines.append("  a UNIX time of %d sec, %d nsec" % (unix.sec, unix.nsec))
        lines.append("  a calendar date of %s" % unix_to_string(unix.sec, unix.nsec))
    else:
        lines.append("  an invalid UNIX time")
    lines.append("")
    _emit(lines, out)


class Resolved(NamedTuple):
    """An instant resolved into every representation (each may be ``None``)."""

    nova: Optional[int]
    unix: Optional[UnixTime]
    gps: Optional[GpsTime]


def _resolve_from_nova(nova: int, leap_seconds: Sequence[int]) -> Resolved:
    return Resolved(nova, nova_to_unix(nova, leap_seconds), nova_to_gps(nova))


def _resolve_from_unix(sec: int, nsec: int, leap_seconds: Sequence[int]) -> Resolved:
    return Resolved(
        unix_to_nova(sec, nsec, leap_seconds),
        UnixTime(sec, nsec),
        unix_to_gps(sec, nsec, leap_seconds),
    )


def _resolve_from_gps(gps: GpsTime, leap_seconds: Sequence[int]) -> Resolved:
    return Resolved(
        gps_to_nova(gps.seconds, gps.nsec),
        gps_to_unix(gps.seconds, gps.nsec, leap_seconds),
        gps,
    )


def _out_error(message: str) -> int:
    sys.stderr.write("nova-time-convert: %s\n" % message)
    return 1


def emit_output_value(
    which: str, resolved: Resolved, leap_seconds: Sequence[int], out
) -> int:
    """Print only the requested representation of ``resolved``.

    Returns 0 on success, or 1 if the instant has no such representation
    (e.g. a NOvA or GPS value for a time before the NOvA epoch).
    """
    if which == "nova":
        if resolved.nova is None:
            return _out_error("no NOvA base time: the instant is before the NOvA epoch")
        out.write("%d\n" % resolved.nova)
    elif which == "gps":
        gps = resolved.gps
        if gps is None:
            return _out_error("no GPS time: the instant is before the NOvA epoch")
        if gps.nsec:
            out.write("%d.%09d\n" % (gps.seconds, gps.nsec))
        else:
            out.write("%d\n" % gps.seconds)
    elif which == "utc":
        if resolved.nova is not None:
            out.write(nova_to_string(resolved.nova, leap_seconds) + "\n")
        elif resolved.unix is not None:
            out.write(unix_to_string(resolved.unix.sec, resolved.unix.nsec) + "\n")
        else:
            return _out_error("no UTC calendar date for this instant")
    elif which == "local":
        if resolved.unix is None:
            return _out_error("no local calendar date for this instant")
        out.write(unix_to_local_string(resolved.unix.sec, resolved.unix.nsec) + "\n")
    return 0


def detect_mode(value: str) -> str:
    """Auto-detect the representation of ``value``: nova, unix or datetime."""
    if ":" in value:
        return "datetime"
    if "." in value:
        return "unix"
    return "nova"


def _sec_and_ns(value: str) -> Tuple[int, int]:
    """Split a ``sec.frac`` (or bare ``sec``) string into (seconds, nanoseconds)."""
    dot = value.find(".")
    if dot == -1:
        return int(value), 0
    sec = int(value[:dot])
    frac = (value[dot + 1:] + "000000000")[:9]
    return sec, int(frac)


def _parse_unix(value: str) -> Tuple[int, int]:
    return _sec_and_ns(value)


def _parse_nova(value: str) -> int:
    if "x" in value.lower():
        return int(value, 16)
    return int(value)


def _parse_gps(value: str) -> GpsTime:
    """Parse a GPS input: ``seconds[.frac]`` or ``week:tow[.frac]``."""
    if ":" in value:
        week_str, tow_str = value.split(":", 1)
        tow_sec, nsec = _sec_and_ns(tow_str)
        return gps_from_week_tow(int(week_str), tow_sec, nsec)
    sec, nsec = _sec_and_ns(value)
    return GpsTime(sec, nsec)


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
            "  nova-time-convert --gps 1025136016\n"
            "  nova-time-convert --gps 1695:259216\n"
            "  nova-time-convert --now\n"
            "  nova-time-convert --output-gps 1120208640000000\n"
            "  nova-time-convert --now --output-utc\n"
            "\n"
            "Without an --output-* flag, every conversion reports all\n"
            "representations, including the GPS time (continuous, no leap\n"
            "seconds) as full GPS seconds and GPS week / time-of-week.\n"
            "With an --output-* flag, only that single value is printed."
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
    mode.add_argument(
        "--gps", action="store_const", const="gps", dest="mode",
        help="interpret the input as a GPS time: 'seconds[.frac]' or "
        "'week:tow[.frac]' (must be given explicitly)",
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
    output = parser.add_mutually_exclusive_group()
    output.add_argument(
        "--output-nova", action="store_const", const="nova", dest="output",
        help="print only the NOvA base time (tick count)",
    )
    output.add_argument(
        "--output-gps", action="store_const", const="gps", dest="output",
        help="print only the GPS time (seconds since the GPS epoch)",
    )
    output.add_argument(
        "--output-utc", action="store_const", const="utc", dest="output",
        help="print only the UTC calendar date string",
    )
    output.add_argument(
        "--output-local", action="store_const", const="local", dest="output",
        help="print only the local-time calendar date string",
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

    # Resolve the input into a canonical instant plus a matching full-report
    # renderer.  ``full`` is only used when no --output-* flag was given.
    try:
        if args.now:
            nova = current_nova_time(leap_seconds)
            resolved = _resolve_from_nova(nova, leap_seconds)
            full = lambda: decode_nova(nova, leap_seconds, sys.stdout)
        elif args.time is None:
            if args.output:
                parser.error("no input time given")
            parser.print_help(sys.stderr)
            return 2
        else:
            mode = args.mode or detect_mode(args.time)
            if mode == "nova":
                nova = _parse_nova(args.time)
                resolved = _resolve_from_nova(nova, leap_seconds)
                full = lambda: decode_nova(nova, leap_seconds, sys.stdout)
            elif mode == "unix":
                sec, nsec = _parse_unix(args.time)
                resolved = _resolve_from_unix(sec, nsec, leap_seconds)
                full = lambda: decode_unix(sec, nsec, leap_seconds, sys.stdout)
            elif mode == "gps":
                gps = _parse_gps(args.time)
                resolved = _resolve_from_gps(gps, leap_seconds)
                full = lambda: decode_gps(gps, leap_seconds, sys.stdout)
            else:
                unix_sec, picoseconds = datetime_string_to_unix(args.time, force_utc)
                resolved = _resolve_from_unix(unix_sec, picoseconds // 1000, leap_seconds)
                full = lambda: decode_datetime(
                    args.time, force_utc, leap_seconds, sys.stdout
                )
    except ValueError as exc:
        parser.error(str(exc))

    if args.output:
        return emit_output_value(args.output, resolved, leap_seconds, sys.stdout)
    full()
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
