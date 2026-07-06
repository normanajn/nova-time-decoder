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


def test_main_now(capsys):
    rc = cli.main(["--now"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "A NOvA base time of" in out


def test_main_no_args_prints_help(capsys):
    rc = cli.main([])
    assert rc == 2
