"""Tests for the nova-time-convert command-line interface."""

import pytest

from nova_time_decoder import cli


def test_detect_mode():
    assert cli.detect_mode("2010-Jul-22 09:01") == "datetime"
    assert cli.detect_mode("1279807260.005") == "unix"
    assert cli.detect_mode("1120208640000000") == "nova"
    assert cli.detect_mode("0x43d950a5b0000") == "nova"


def test_parse_nova_decimal_and_hex():
    assert cli._parse_nova("1120208640000000") == 1120208640000000
    assert cli._parse_nova("0x43d950a5b0000") == 0x43d950a5b0000


def test_parse_unix():
    assert cli._parse_unix("1279807260.005") == (1279807260, 5000000)
    assert cli._parse_unix("1279807260.0") == (1279807260, 0)


def test_parse_datetime_string_utc_and_fraction():
    civil, psec, utc = cli.parse_datetime_string("2010-Jul-22 14:22:30.000000015625 UTC")
    assert civil == "2010-Jul-22 14:22:30"
    assert psec == 15625
    assert utc is True


def test_datetime_string_to_unix_utc():
    sec, psec = cli.datetime_string_to_unix("2010-Jan-01 00:00:00 UTC")
    assert sec == 1262304000
    assert psec == 0


def test_parse_leap_seconds():
    assert cli.parse_leap_seconds(None) == cli.DEFAULT_LEAP_SECONDS
    assert cli.parse_leap_seconds("1,2,3") == (1, 2, 3)
    with pytest.raises(ValueError):
        cli.parse_leap_seconds("bogus")


def test_main_nova(capsys):
    rc = cli.main(["1120208640000000"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "A NOvA base time of 1120208640000000 corresponds to" in out
    assert "a UNIX time of" in out
    assert "a calendar date of" in out


def test_main_hex_matches_decimal(capsys):
    cli.main(["0x43d950a5b0000"])
    hex_out = capsys.readouterr().out
    cli.main([str(0x43d950a5b0000)])
    dec_out = capsys.readouterr().out
    # Both describe the same NOvA base time / calendar date.
    assert "a calendar date of" in hex_out
    assert hex_out.splitlines()[-2] == dec_out.splitlines()[-2]


def test_main_unix(capsys):
    cli.main(["1279807260.005"])
    out = capsys.readouterr().out
    assert "A UNIX time of 1279807260 sec, 5000000 nsec corresponds to" in out
    assert "a NOvA base time of" in out


def test_main_datetime_utc(capsys):
    cli.main(["2010-Jan-01 00:00:00 UTC"])
    out = capsys.readouterr().out
    assert "a NOvA base time of 0" in out
    assert "2010-Jan-01 00:00:00.000000000000 UTC" in out


def test_main_before_epoch_is_invalid(capsys):
    cli.main(["2000-Jan-01 00:00:00 UTC"])
    out = capsys.readouterr().out
    assert "an invalid NOvA base time" in out


def test_parse_gps_seconds_and_week_tow():
    g1 = cli._parse_gps("1025136016")
    assert (g1.seconds, g1.nsec) == (1025136016, 0)
    g2 = cli._parse_gps("1025136016.5")
    assert (g2.seconds, g2.nsec) == (1025136016, 500000000)
    g3 = cli._parse_gps("1695:259216")
    assert g3.seconds == 1695 * 604800 + 259216


def test_main_gps_seconds(capsys):
    rc = cli.main(["--gps", "1025136016"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "A GPS time of week" in out
    assert "a NOvA base time of" in out
    assert "2012-Jul-01 00:00:00" in out


def test_main_gps_week_tow_matches_seconds(capsys):
    cli.main(["--gps", "1025136016"])
    by_sec = capsys.readouterr().out
    week, tow = divmod(1025136016, 604800)
    cli.main(["--gps", "%d:%d" % (week, tow)])
    by_wt = capsys.readouterr().out
    # Same instant -> same NOvA base time line.
    nova_line = [l for l in by_sec.splitlines() if "NOvA base time" in l][0]
    assert nova_line in by_wt


def test_every_mode_reports_gps(capsys):
    cli.main(["1120208640000000"])
    assert "a GPS time of" in capsys.readouterr().out
    cli.main(["1279807260.005"])
    assert "a GPS time of" in capsys.readouterr().out
    cli.main(["2012-Jul-01 00:00:00 UTC"])
    assert "a GPS time of" in capsys.readouterr().out


def test_main_now(capsys):
    rc = cli.main(["--now"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "A NOvA base time of" in out


def test_main_no_args_prints_help(capsys):
    rc = cli.main([])
    assert rc == 2


# --- single-value output flags ---------------------------------------------

def test_output_nova_is_just_the_value(capsys):
    rc = cli.main(["--output-nova", "1279807260.005"])
    assert rc == 0
    out = capsys.readouterr().out
    # Exactly one line, the bare integer, no descriptive text.
    assert out == "1120208640320000\n"


def test_output_gps_seconds(capsys):
    rc = cli.main(["--output-gps", "1120208640000000"])
    assert rc == 0
    assert capsys.readouterr().out == "963842475\n"


def test_output_gps_with_fraction(capsys):
    cli.main(["--output-gps", "1279807260.005"])
    assert capsys.readouterr().out == "963842475.005000000\n"


def test_output_utc(capsys):
    cli.main(["--output-utc", "1120208640000000"])
    assert capsys.readouterr().out == "2010-Jul-22 14:01:00.000000000000 UTC\n"


def test_output_utc_from_gps_input(capsys):
    cli.main(["--gps", "--output-utc", "1025136016"])
    assert capsys.readouterr().out == "2012-Jul-01 00:00:00.000000000000 UTC\n"


def test_output_local_is_single_wellformed_line(capsys):
    cli.main(["--output-local", "1120208640000000"])
    out = capsys.readouterr().out
    assert out.count("\n") == 1
    # 14:01 UTC lands on Jul-22 or Jul-23 depending on the local zone.
    assert out.startswith("2010-Jul-2")
    assert ".000000000 " in out  # nanosecond field + trailing tz token


def test_output_now(capsys):
    rc = cli.main(["--now", "--output-nova"])
    assert rc == 0
    out = capsys.readouterr().out.strip()
    assert out.isdigit()


def test_output_before_epoch_has_no_nova(capsys):
    rc = cli.main(["--output-nova", "2000-Jan-01 00:00:00 UTC"])
    assert rc == 1
    err = capsys.readouterr().err
    assert "before the NOvA epoch" in err


def test_output_before_epoch_utc_still_works(capsys):
    rc = cli.main(["--output-utc", "2000-Jan-01 00:00:00 UTC"])
    assert rc == 0
    assert capsys.readouterr().out == "2000-Jan-01 00:00:00.000000000 UTC\n"


def test_output_flags_mutually_exclusive():
    with pytest.raises(SystemExit):
        cli.main(["--output-nova", "--output-gps", "1120208640000000"])


def test_output_without_input_errors():
    with pytest.raises(SystemExit):
        cli.main(["--output-nova"])
