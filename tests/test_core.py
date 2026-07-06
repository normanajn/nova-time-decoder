"""Tests for nova_time_decoder.core.

These port the CppUnit test suite from the original ``NovaTimingUtilities``
package (TimingUtilitiesTests.cpp) plus a few extra round-trip and precision
checks.
"""

import time

import pytest

from nova_time_decoder import core
from nova_time_decoder.core import (
    GPS_EPOCH,
    NOVA_EPOCH,
    NOVA_GPS_OFFSET,
    NOVA_TIME_FACTOR,
    SECONDS_PER_WEEK,
    GpsTime,
    UnixTime,
    current_nova_time,
    fields_to_nova,
    gps_from_week_tow,
    gps_to_nova,
    gps_to_string,
    gps_to_unix,
    nova_to_fields,
    nova_to_gps,
    nova_to_string,
    nova_to_tm,
    nova_to_unix,
    tm_to_nova,
    unix_to_gps,
    unix_to_nova,
    unix_to_string,
)


def test_epoch_boundaries():
    # NOvA time 0 == the epoch.
    unix = nova_to_unix(0)
    assert unix.sec == 1262304000
    assert unix.nsec == 0

    # One second later.
    unix = nova_to_unix(NOVA_TIME_FACTOR)
    assert unix.sec == 1 + 1262304000
    assert unix.nsec == 0


def test_round_trip_nova_unix():
    sample = int(NOVA_TIME_FACTOR * 123456789.5)
    unix = nova_to_unix(sample)
    assert unix_to_nova(unix.sec, unix.nsec) == sample


def test_reject_before_epoch():
    assert unix_to_nova(NOVA_EPOCH - 1) is None


def test_fields_round_trip():
    # 01-Jan-2010 00:00:00 UTC -> NOvA 0.
    nova = fields_to_nova(0, 0, 0, 1, 0, 110)
    assert nova == 0
    assert nova_to_fields(nova) == (0, 0, 0, 1, 0, 110)

    # A time before the epoch fails.
    assert fields_to_nova(0, 0, 0, 1, 0, 109) is None

    # Feb 4, 2010, 10:11:12 UTC.
    nova = fields_to_nova(12, 11, 10, 4, 1, 110)
    assert nova == 2974272 * 64000000
    assert nova_to_fields(nova) == (12, 11, 10, 4, 1, 110)


def test_tm_struct_round_trip():
    tm = time.struct_time((2010, 1, 1, 0, 0, 0, 0, 1, -1))
    nova = tm_to_nova(tm)
    assert nova == 0
    out = nova_to_tm(nova)
    assert (out.tm_year, out.tm_mon, out.tm_mday, out.tm_hour, out.tm_min,
            out.tm_sec) == (2010, 1, 1, 0, 0, 0)

    tm = time.struct_time((2009, 1, 1, 0, 0, 0, 0, 1, -1))
    assert tm_to_nova(tm) is None


# The exact leap-second vectors from the original CppUnit testLeapSeconds().
@pytest.mark.parametrize(
    "fields,expected",
    [
        # 30-Jun-2012 23:59:59.0 (one second before the 2012 leap second).
        ((59, 59, 23, 30, 5, 112), 5042995136000000),
        # 01-Jul-2012 00:00:00.0 (exactly at the leap second).
        ((0, 0, 0, 1, 6, 112), 5042995136000000 + 32000000 + 32000000 + 64000000),
        # 01-Jul-2012 00:00:01.0 (one second after).
        ((1, 0, 0, 1, 6, 112),
         5042995136000000 + 32000000 + 32000000 + 64000000 + 32000000 + 32000000),
    ],
)
def test_leap_seconds_fields(fields, expected):
    assert fields_to_nova(*fields) == expected
    assert nova_to_fields(expected) == fields


def test_leap_second_fractional_timespec():
    # 30-Jun-2012 23:59:59.5
    expected = 5042995136000000 + 32000000
    nova = unix_to_nova(1341100799, 500000000)
    assert nova == expected
    unix = nova_to_unix(nova)
    assert unix.sec == 1341100799
    assert unix.nsec == 500000000


def test_leap_second_timeval_round_trip():
    # 01-Jul-2012 00:00:00.5 via a timeval (microseconds).
    nova = unix_to_nova(1341100800, 500000 * 1000)
    unix = nova_to_unix(nova)
    assert unix.sec == 1341100800
    assert unix.usec == 500000


def test_nova_to_string_epoch():
    assert nova_to_string(0) == "2010-Jan-01 00:00:00.000000000000 UTC"


def test_nova_to_string_fraction():
    # 1/64_000_000 s == 15625 ps.
    assert nova_to_string(1) == "2010-Jan-01 00:00:00.000000015625 UTC"
    # Half a second.
    assert nova_to_string(NOVA_TIME_FACTOR // 2) == "2010-Jan-01 00:00:00.500000000000 UTC"


def test_unix_to_string():
    assert unix_to_string(NOVA_EPOCH, 5000000) == "2010-Jan-01 00:00:00.005000000 UTC"


def test_current_nova_time_monotonic():
    before = unix_to_nova(*_now_parts())
    now = current_nova_time()
    after = unix_to_nova(*_now_parts())
    assert before <= now <= after


def _now_parts():
    t = time.time()
    sec = int(t)
    return sec, int((t - sec) * 1_000_000_000)


def test_gps_epoch_offset():
    # NOvA time 0 (2010-01-01) is NOVA_GPS_OFFSET GPS seconds after the GPS epoch.
    gps = nova_to_gps(0)
    assert gps.seconds == NOVA_GPS_OFFSET
    assert gps.nsec == 0
    # And the offset is the elapsed UNIX seconds + 15 leap seconds.
    assert NOVA_GPS_OFFSET == (NOVA_EPOCH - GPS_EPOCH) + 15


def test_nova_gps_round_trip():
    sample = int(NOVA_TIME_FACTOR * 123456789.5)
    gps = nova_to_gps(sample)
    assert gps_to_nova(gps.seconds, gps.nsec) == sample


def test_gps_is_fixed_offset_from_nova_seconds():
    # GPS whole seconds track NOvA whole seconds with a constant offset,
    # with no leap-second adjustment between the two continuous scales.
    nova = NOVA_TIME_FACTOR * 78796801  # 2012-07-01 00:00:00 UTC
    assert nova_to_gps(nova).seconds == NOVA_GPS_OFFSET + 78796801


def test_gps_matches_standard_utc_formula_across_a_leap_second():
    # At 2012-07-01 00:00:00 UTC, GPS-UTC == 16, so
    # gps = unix - GPS_EPOCH + 16.
    unix_sec = 1341100800
    gps = unix_to_gps(unix_sec, 0)
    assert gps.seconds == unix_sec - GPS_EPOCH + 16
    # And one second before the 2012 leap, GPS-UTC == 15.
    gps_before = unix_to_gps(1341100799, 0)
    assert gps_before.seconds == 1341100799 - GPS_EPOCH + 15


def test_unix_gps_round_trip_preserves_nanoseconds():
    gps = unix_to_gps(1751000000, 123456789)
    assert gps is not None
    unix = gps_to_unix(gps.seconds, gps.nsec)
    assert unix == UnixTime(1751000000, 123456789)


def test_gps_week_and_tow():
    gps = nova_to_gps(0)
    assert gps.week == NOVA_GPS_OFFSET // SECONDS_PER_WEEK
    assert gps.tow == NOVA_GPS_OFFSET % SECONDS_PER_WEEK
    # Rebuild from week/tow.
    rebuilt = gps_from_week_tow(gps.week, gps.tow, gps.nsec)
    assert rebuilt.seconds == gps.seconds
    assert rebuilt.nsec == gps.nsec


def test_gps_before_nova_epoch_is_none():
    assert gps_to_nova(NOVA_GPS_OFFSET - 1) is None
    assert gps_to_unix(NOVA_GPS_OFFSET - 1) is None
    assert unix_to_gps(NOVA_EPOCH - 1) is None


def test_gps_to_string_format():
    s = gps_to_string(GpsTime(NOVA_GPS_OFFSET, 500000000))
    assert "week 1564" in s
    assert "TOW 432015.500000000" in s
    assert "%d.500000000 s" % NOVA_GPS_OFFSET in s


def test_large_modern_timestamp_is_exact():
    # A modern NOvA time exceeds 2**53, where the original C++ float math lost
    # precision; the integer port must round-trip it exactly.
    nova = unix_to_nova(1751000000, 123456789)  # mid-2025
    assert nova is not None
    unix = nova_to_unix(nova)
    # Seconds reconstruct exactly; nsec is quantised to the 15.625 ns tick.
    assert unix.sec == 1751000000
    assert abs(unix.nsec - 123456789) < 16
