"""Core NOvA timestamp encoding/decoding routines.

This module is a self-contained, pure-Python reimplementation of the
``novadaq::timeutils`` C++ library from the NOvA DAQ ``NovaTimingUtilities``
package.  It has **no third-party dependencies** -- only the Python standard
library is used.

Two constants define the NOvA time base:

``NOVA_EPOCH``
    The UNIX ``time_t`` for the start of the NOvA epoch,
    01-Jan-2010 00:00:00 UTC (``1262304000``).  A NOvA time of ``0``
    corresponds to this instant.

``NOVA_TIME_FACTOR``
    The number of NOvA clock ticks per second (``64000000`` == 64 MHz).
    A NOvA timestamp is an unsigned 64-bit count of these ticks since the
    NOvA epoch.

NOvA time does **not** contain leap seconds, while UNIX time does.  Leap
seconds inserted *after* the NOvA epoch therefore have to be added when
going from UNIX time to NOvA time (and removed going the other way).  The
table of leap seconds is expressed as the UNIX ``time_t`` value of the last
second *before* each inserted leap second and can be overridden per-call or
via configuration (see :data:`DEFAULT_LEAP_SECONDS`).

Implementation note
-------------------
The original C++ used floating-point division in a few places
(``nova / NOVA_TIME_FACTOR`` and ``1E12 * frac / NOVA_TIME_FACTOR``).  For
modern (large) NOvA timestamps those doubles exceed 2**53 and lose
precision.  This port performs the equivalent operations with exact integer
arithmetic, so it is bit-for-bit compatible with the C++ code on every value
the C++ code represented exactly, and strictly more accurate elsewhere.
"""

from __future__ import annotations

import calendar
import time
from typing import NamedTuple, Optional, Sequence

__all__ = [
    "NOVA_EPOCH",
    "NOVA_TIME_FACTOR",
    "DEFAULT_LEAP_SECONDS",
    "GPS_EPOCH",
    "NOVA_GPS_OFFSET",
    "SECONDS_PER_WEEK",
    "UnixTime",
    "GpsTime",
    "unix_to_nova",
    "nova_to_unix",
    "tm_to_nova",
    "nova_to_tm",
    "fields_to_nova",
    "nova_to_fields",
    "current_nova_time",
    "nova_to_string",
    "unix_to_string",
    "unix_to_local_string",
    "nova_to_gps",
    "gps_to_nova",
    "unix_to_gps",
    "gps_to_unix",
    "gps_from_week_tow",
    "gps_to_string",
]

# *time_t* of the start of the NOvA epoch, 01-Jan-2010 00:00:00 UTC.
NOVA_EPOCH = 1262304000

# Conversion factor: NOvA clock ticks per second (64 MHz).
NOVA_TIME_FACTOR = 64000000

# UNIX ``time_t`` values of the last second *before* each leap second that was
# inserted after the NOvA epoch.  These match the hard-coded table in the
# original C++ implementation:
#   * 1341100799 -> 30-Jun-2012 23:59:59 UTC
#   * 1435708799 -> 30-Jun-2015 23:59:59 UTC
#   * 1483228799 -> 31-Dec-2016 23:59:59 UTC
# No leap seconds have been inserted since 2016, so this table is current.
DEFAULT_LEAP_SECONDS = (1341100799, 1435708799, 1483228799)

# UNIX ``time_t`` of the GPS epoch, 06-Jan-1980 00:00:00 UTC.
GPS_EPOCH = 315964800

# GPS time (like NOvA time) is a *continuous* atomic timescale: it counts real
# SI seconds with no leap-second discontinuities.  The NOvA <-> GPS relationship
# is therefore a fixed integer-second offset that needs no leap-second table.
#
# NOVA_GPS_OFFSET is the GPS time, in whole seconds since the GPS epoch, of the
# NOvA epoch (i.e. the GPS time corresponding to a NOvA base time of 0).  It is
#   (NOVA_EPOCH - GPS_EPOCH) + 15
# where 15 is the number of leap seconds inserted between the GPS epoch (1980)
# and the NOvA epoch (2010).  Both the offset and the "15" are historical
# constants, independent of the configurable post-epoch leap-second table.
NOVA_GPS_OFFSET = 946339215

# Seconds in a GPS week, used to derive week number and time-of-week.
SECONDS_PER_WEEK = 604800

_MONTH_ABBR = (
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
)


class UnixTime(NamedTuple):
    """A UNIX time expressed as whole seconds plus a nanosecond remainder.

    ``sec`` is the UNIX ``time_t`` (seconds since 01-Jan-1970 UTC) and
    ``nsec`` is the sub-second part in nanoseconds (0..999999999).  This mirrors
    a POSIX ``struct timespec`` and can represent a ``struct timeval`` too
    (microseconds == ``nsec // 1000``).
    """

    sec: int
    nsec: int = 0

    @property
    def usec(self) -> int:
        """The sub-second part expressed in microseconds (truncated)."""
        return self.nsec // 1000


class GpsTime(NamedTuple):
    """A GPS time on the continuous (no-leap-second) GPS timescale.

    ``seconds`` is the whole number of GPS seconds since the GPS epoch
    (06-Jan-1980 00:00:00 UTC) and ``nsec`` is the sub-second remainder in
    nanoseconds (0..999999999).  The :attr:`week` and :attr:`tow` properties
    provide the equivalent GPS week number and (whole-second) time-of-week.
    """

    seconds: int
    nsec: int = 0

    @property
    def week(self) -> int:
        """The full GPS week number (not reduced modulo 1024)."""
        return self.seconds // SECONDS_PER_WEEK

    @property
    def tow(self) -> int:
        """The whole-second time-of-week (0..604799); sub-second in ``nsec``."""
        return self.seconds % SECONDS_PER_WEEK


def _leap_forward(seconds: int, leap_seconds: Sequence[int]) -> int:
    """Add leap seconds when converting UNIX -> NOvA time.

    Replicates the original C++ behaviour exactly: the thresholds are applied
    sequentially in chronological order, each ``> threshold`` test seeing the
    running (already-incremented) value.  Because real leap-second thresholds
    are years apart this is equivalent to a simple count, but we keep the
    sequential form to remain bit-identical at pathological inputs.
    """
    for threshold in leap_seconds:
        if seconds > threshold:
            seconds += 1
    return seconds


def _leap_backward(seconds: int, leap_seconds: Sequence[int]) -> int:
    """Remove leap seconds when converting NOvA -> UNIX time."""
    for threshold in leap_seconds:
        if seconds > threshold:
            seconds -= 1
    return seconds


def unix_to_nova(
    sec: int,
    nsec: int = 0,
    leap_seconds: Sequence[int] = DEFAULT_LEAP_SECONDS,
) -> Optional[int]:
    """Convert a UNIX time (seconds + nanoseconds) to a NOvA timestamp.

    Returns the NOvA tick count, or ``None`` if the input predates the NOvA
    epoch (mirroring the C++ ``bool`` failure return).
    """
    if sec < NOVA_EPOCH:
        return None
    adjusted = _leap_forward(sec, leap_seconds)
    return (
        (adjusted - NOVA_EPOCH) * NOVA_TIME_FACTOR
        + (nsec * NOVA_TIME_FACTOR) // 1_000_000_000
    )


def nova_to_unix(
    nova_time: int,
    leap_seconds: Sequence[int] = DEFAULT_LEAP_SECONDS,
) -> UnixTime:
    """Convert a NOvA timestamp to a :class:`UnixTime` (seconds + nanoseconds)."""
    time_sec = nova_time // NOVA_TIME_FACTOR
    frac_ticks = nova_time - time_sec * NOVA_TIME_FACTOR
    # 1 tick == 1/64_000_000 s == 15.625 ns; nsec = frac_ticks * 1000 / 64.
    nsec = frac_ticks * 1000 // 64
    tv_sec = _leap_backward(NOVA_EPOCH + time_sec, leap_seconds)
    return UnixTime(tv_sec, nsec)


def tm_to_nova(
    tm: time.struct_time,
    leap_seconds: Sequence[int] = DEFAULT_LEAP_SECONDS,
) -> Optional[int]:
    """Convert a UTC :class:`time.struct_time` to a NOvA timestamp."""
    sec = calendar.timegm(tm)
    if sec < 0:
        return None
    return unix_to_nova(sec, 0, leap_seconds)


def nova_to_tm(
    nova_time: int,
    leap_seconds: Sequence[int] = DEFAULT_LEAP_SECONDS,
) -> time.struct_time:
    """Convert a NOvA timestamp to a UTC :class:`time.struct_time`."""
    unix = nova_to_unix(nova_time, leap_seconds)
    return time.gmtime(unix.sec)


def fields_to_nova(
    sec: int,
    minute: int,
    hour: int,
    mday: int,
    mon: int,
    year: int,
    leap_seconds: Sequence[int] = DEFAULT_LEAP_SECONDS,
) -> Optional[int]:
    """Convert broken-down UTC calendar fields to a NOvA timestamp.

    Field semantics match the C ``struct tm``:

    * ``sec``   -- seconds after the minute (0-60, 60 for a leap second)
    * ``minute``-- minutes after the hour (0-59)
    * ``hour``  -- hours since midnight (0-23)
    * ``mday``  -- day of the month (1-31)
    * ``mon``   -- months since January (0-11)
    * ``year``  -- years since 1900

    Returns ``None`` if the instant predates the NOvA epoch.
    """
    # (year, mon, mday, hour, min, sec, wday, yday, isdst); wday/yday ignored.
    tm = time.struct_time(
        (year + 1900, mon + 1, mday, hour, minute, sec, 0, 1, -1)
    )
    return tm_to_nova(tm, leap_seconds)


def nova_to_fields(
    nova_time: int,
    leap_seconds: Sequence[int] = DEFAULT_LEAP_SECONDS,
):
    """Convert a NOvA timestamp to broken-down UTC fields.

    Returns a 6-tuple ``(sec, minute, hour, mday, mon, year)`` using the same
    ``struct tm`` field conventions as :func:`fields_to_nova`.
    """
    tm = nova_to_tm(nova_time, leap_seconds)
    return (
        tm.tm_sec,
        tm.tm_min,
        tm.tm_hour,
        tm.tm_mday,
        tm.tm_mon - 1,
        tm.tm_year - 1900,
    )


def current_nova_time(
    leap_seconds: Sequence[int] = DEFAULT_LEAP_SECONDS,
) -> int:
    """Return the current wall-clock time as a NOvA timestamp."""
    now = time.time()
    sec = int(now)
    nsec = int((now - sec) * 1_000_000_000)
    nova = unix_to_nova(sec, nsec, leap_seconds)
    # "now" is always well after the NOvA epoch, so this cannot be None.
    assert nova is not None
    return nova


def _format_civil(sec: int) -> str:
    """Format a UNIX ``time_t`` as ``YYYY-Mon-DD HH:MM:SS`` (UTC).

    Matches Boost's ``to_simple_string`` output used by the original C++.
    """
    tm = time.gmtime(sec)
    return "%04d-%s-%02d %02d:%02d:%02d" % (
        tm.tm_year,
        _MONTH_ABBR[tm.tm_mon - 1],
        tm.tm_mday,
        tm.tm_hour,
        tm.tm_min,
        tm.tm_sec,
    )


def nova_to_string(
    nova_time: int,
    leap_seconds: Sequence[int] = DEFAULT_LEAP_SECONDS,
) -> str:
    """Format a NOvA timestamp as ``YYYY-Mon-DD HH:MM:SS.pppppppppppp UTC``.

    The fractional part is expressed in picoseconds (12 digits).
    """
    unix = nova_to_unix(nova_time, leap_seconds)
    frac_ticks = nova_time - (nova_time // NOVA_TIME_FACTOR) * NOVA_TIME_FACTOR
    # 1E12 / 64_000_000 == 15625 exactly, so this is exact integer math.
    picoseconds = frac_ticks * 1_000_000_000_000 // NOVA_TIME_FACTOR
    return "%s.%012d UTC" % (_format_civil(unix.sec), picoseconds)


def unix_to_string(sec: int, nsec: int = 0) -> str:
    """Format a UNIX time as ``YYYY-Mon-DD HH:MM:SS.nnnnnnnnn UTC``.

    The fractional part is expressed in nanoseconds (9 digits).  No leap-second
    adjustment is applied -- the value is treated as a raw UNIX time.
    """
    return "%s.%09d UTC" % (_format_civil(sec), nsec)


def unix_to_local_string(sec: int, nsec: int = 0) -> str:
    """Format a UNIX time in the local timezone.

    Renders as ``YYYY-Mon-DD HH:MM:SS.nnnnnnnnn TZ`` where ``TZ`` is the local
    timezone abbreviation.  The fractional part is expressed in nanoseconds
    (9 digits).
    """
    tm = time.localtime(sec)
    civil = "%04d-%s-%02d %02d:%02d:%02d" % (
        tm.tm_year,
        _MONTH_ABBR[tm.tm_mon - 1],
        tm.tm_mday,
        tm.tm_hour,
        tm.tm_min,
        tm.tm_sec,
    )
    tzname = time.strftime("%Z", tm)
    return "%s.%09d %s" % (civil, nsec, tzname)


# ---------------------------------------------------------------------------
# GPS timebase
#
# GPS time and NOvA time are both continuous atomic timescales, so converting
# between them is a pure fixed-offset operation with no leap seconds involved.
# Converting GPS <-> UNIX/civil time does involve leap seconds, and is done by
# routing through NOvA time so the configurable post-epoch leap-second table is
# applied consistently.  As with the NOvA conversions, these are defined for
# instants at or after the NOvA epoch (01-Jan-2010); earlier GPS times cannot be
# represented as a NOvA base time and yield ``None``.
# ---------------------------------------------------------------------------


def nova_to_gps(nova_time: int) -> GpsTime:
    """Convert a NOvA base time to a :class:`GpsTime` (exact, no leap seconds)."""
    nova_sec = nova_time // NOVA_TIME_FACTOR
    frac_ticks = nova_time - nova_sec * NOVA_TIME_FACTOR
    nsec = frac_ticks * 1000 // 64
    return GpsTime(NOVA_GPS_OFFSET + nova_sec, nsec)


def gps_to_nova(seconds: int, nsec: int = 0) -> Optional[int]:
    """Convert a GPS time (seconds + nanoseconds) to a NOvA base time.

    Returns ``None`` if the instant predates the NOvA epoch (i.e. the GPS time
    is earlier than :data:`NOVA_GPS_OFFSET`).
    """
    if seconds < NOVA_GPS_OFFSET:
        return None
    nova_sec = seconds - NOVA_GPS_OFFSET
    return nova_sec * NOVA_TIME_FACTOR + (nsec * NOVA_TIME_FACTOR) // 1_000_000_000


def unix_to_gps(
    sec: int,
    nsec: int = 0,
    leap_seconds: Sequence[int] = DEFAULT_LEAP_SECONDS,
) -> Optional[GpsTime]:
    """Convert a UNIX time to a :class:`GpsTime`.

    Leap seconds are applied via the same table used for the NOvA conversions.
    Returns ``None`` for instants before the NOvA epoch.
    """
    if sec < NOVA_EPOCH:
        return None
    adjusted = _leap_forward(sec, leap_seconds)
    return GpsTime(NOVA_GPS_OFFSET + (adjusted - NOVA_EPOCH), nsec)


def gps_to_unix(
    seconds: int,
    nsec: int = 0,
    leap_seconds: Sequence[int] = DEFAULT_LEAP_SECONDS,
) -> Optional[UnixTime]:
    """Convert a GPS time to a :class:`UnixTime`.

    Returns ``None`` for instants before the NOvA epoch.
    """
    if seconds < NOVA_GPS_OFFSET:
        return None
    nova_sec = seconds - NOVA_GPS_OFFSET
    tv_sec = _leap_backward(NOVA_EPOCH + nova_sec, leap_seconds)
    return UnixTime(tv_sec, nsec)


def gps_from_week_tow(week: int, tow: int, nsec: int = 0) -> GpsTime:
    """Build a :class:`GpsTime` from a GPS week number and time-of-week.

    ``week`` is the full (non-modulo-1024) GPS week and ``tow`` is the
    time-of-week in seconds (0..604799).
    """
    return GpsTime(week * SECONDS_PER_WEEK + tow, nsec)


def gps_to_string(gps: GpsTime) -> str:
    """Format a :class:`GpsTime` as ``week W, TOW ssssss.nnnnnnnnn (GGGG.nnn s)``.

    The rendering shows both the GPS week / time-of-week and the total GPS
    seconds since the GPS epoch, with nanosecond precision.
    """
    return "week %d, TOW %d.%09d (%d.%09d s)" % (
        gps.week,
        gps.tow,
        gps.nsec,
        gps.seconds,
        gps.nsec,
    )
