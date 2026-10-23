"""Código interno correlativo `EQ-` + 6 dígitos (T-09 / RN-02)."""

import inspect

import pytest

from app.domain.codes import (
    CODE_DIGITS,
    CODE_PREFIX,
    MAX_SEQUENCE,
    format_internal_code,
    parse_internal_code,
)


@pytest.mark.parametrize(
    ("sequence", "expected"),
    [(1, "EQ-000001"), (42, "EQ-000042"), (999999, "EQ-999999")],
)
def test_format_pads_to_six_digits(sequence, expected):
    assert format_internal_code(sequence) == expected


def test_format_has_fixed_width():
    codes = [format_internal_code(value) for value in (1, 10, 100, 1000, 10000, 100000)]

    assert {len(code) for code in codes} == {len(CODE_PREFIX) + CODE_DIGITS}
    assert all(code.startswith(CODE_PREFIX) for code in codes)


def test_max_sequence_matches_the_six_digit_format():
    assert CODE_DIGITS == 6
    assert MAX_SEQUENCE == 999999
    assert format_internal_code(MAX_SEQUENCE) == "EQ-999999"


@pytest.mark.parametrize("sequence", [0, -1, -999])
def test_non_positive_sequences_are_rejected(sequence):
    with pytest.raises(ValueError):
        format_internal_code(sequence)


def test_overflow_is_rejected():
    with pytest.raises(ValueError):
        format_internal_code(1000000)


@pytest.mark.parametrize("value", ["1", 1.5, None, True])
def test_non_integer_sequences_are_rejected_by_type(value):
    with pytest.raises(TypeError):
        format_internal_code(value)


def test_non_string_codes_are_rejected_by_type():
    with pytest.raises(TypeError):
        parse_internal_code(42)


@pytest.mark.parametrize("sequence", [1, 42, 999999])
def test_parse_round_trips_the_formatted_code(sequence):
    assert parse_internal_code(format_internal_code(sequence)) == sequence


@pytest.mark.parametrize("code", ["eq-000042", " EQ-000042 "])
def test_parse_is_case_and_space_tolerant(code):
    assert parse_internal_code(code) == 42


@pytest.mark.parametrize(
    "code",
    ["EQ-0", "EQ-000000", "EQ-0000420", "XX-000042", "EQ-ABC123", "", "EQ-"],
)
def test_parse_rejects_invalid_codes(code):
    with pytest.raises(ValueError):
        parse_internal_code(code)


def test_format_signature_only_depends_on_the_sequence():
    # El formato no depende del id de la entidad ni del estado del repositorio.
    assert list(inspect.signature(format_internal_code).parameters) == ["sequence"]
