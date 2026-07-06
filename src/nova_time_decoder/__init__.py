"""nova_time_decoder -- encode/decode NOvA DAQ timestamps.

A self-contained, pure-Python reimplementation of the NOvA DAQ
``NovaTimingUtilities`` (``novadaq::timeutils``) C++ library.  It converts
between NOvA base time (64 MHz clock ticks since the 2010 NOvA epoch) and UNIX
time / civil calendar time, accounting for post-epoch leap seconds.

Typical use::

    from nova_time_decoder import unix_to_nova, nova_to_string

    nova = unix_to_nova(1279807260, 5_000_000)
    print(nova_to_string(nova))

See :mod:`nova_time_decoder.core` for the full API.
"""

from .core import (
    DEFAULT_LEAP_SECONDS,
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
    unix_to_local_string,
    unix_to_nova,
    unix_to_string,
)

__version__ = "1.2.0"

__all__ = [
    "__version__",
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
