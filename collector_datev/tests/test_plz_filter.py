import pytest

from src.plz_filter import PlzFilter, get_sheet_index, matches_filter, parse_plz_filter


class TestParsePlzFilter:
    def test_parse_single_digit_prefix(self) -> None:
        result = parse_plz_filter("4")
        assert result.prefix == "4"
        assert result.range_start is None
        assert result.range_end is None

    def test_parse_two_digit_prefix(self) -> None:
        result = parse_plz_filter("40")
        assert result.prefix == "40"
        assert result.range_start is None

    def test_parse_three_digit_prefix(self) -> None:
        result = parse_plz_filter("401")
        assert result.prefix == "401"

    def test_parse_full_plz_prefix(self) -> None:
        result = parse_plz_filter("40123")
        assert result.prefix == "40123"

    def test_parse_range(self) -> None:
        result = parse_plz_filter("40000-41000")
        assert result.prefix is None
        assert result.range_start == 40000
        assert result.range_end == 41000

    def test_parse_range_invalid_start_greater_than_end(self) -> None:
        with pytest.raises(ValueError, match="Start muss kleiner als Ende sein"):
            parse_plz_filter("41000-40000")

    def test_parse_invalid_prefix_with_letters(self) -> None:
        with pytest.raises(ValueError, match="nur Ziffern"):
            parse_plz_filter("4a")

    def test_parse_prefix_too_long(self) -> None:
        with pytest.raises(ValueError, match="maximal 5 Ziffern"):
            parse_plz_filter("123456")


class TestMatchesFilter:
    def test_matches_single_digit_prefix(self) -> None:
        plz_filter = PlzFilter(prefix="4")
        assert matches_filter("40000", plz_filter) is True
        assert matches_filter("49999", plz_filter) is True
        assert matches_filter("30000", plz_filter) is False
        assert matches_filter("50000", plz_filter) is False

    def test_matches_two_digit_prefix(self) -> None:
        plz_filter = PlzFilter(prefix="40")
        assert matches_filter("40000", plz_filter) is True
        assert matches_filter("40999", plz_filter) is True
        assert matches_filter("41000", plz_filter) is False
        assert matches_filter("39999", plz_filter) is False

    def test_matches_range(self) -> None:
        plz_filter = PlzFilter(range_start=40000, range_end=41000)
        assert matches_filter("40000", plz_filter) is True
        assert matches_filter("40500", plz_filter) is True
        assert matches_filter("41000", plz_filter) is True
        assert matches_filter("39999", plz_filter) is False
        assert matches_filter("41001", plz_filter) is False

    def test_matches_empty_filter(self) -> None:
        plz_filter = PlzFilter()
        assert matches_filter("40000", plz_filter) is True
        assert matches_filter("00000", plz_filter) is True


class TestGetSheetIndex:
    def test_sheet_index_from_prefix(self) -> None:
        assert get_sheet_index(PlzFilter(prefix="4")) == 4
        assert get_sheet_index(PlzFilter(prefix="40")) == 4
        assert get_sheet_index(PlzFilter(prefix="0")) == 0
        assert get_sheet_index(PlzFilter(prefix="9")) == 9

    def test_sheet_index_from_range(self) -> None:
        assert get_sheet_index(PlzFilter(range_start=40000, range_end=41000)) == 4
        assert get_sheet_index(PlzFilter(range_start=10000, range_end=19999)) == 1
        assert get_sheet_index(PlzFilter(range_start=0, range_end=9999)) == 0

    def test_sheet_index_empty_filter_raises(self) -> None:
        with pytest.raises(ValueError, match="Praefix oder Bereich"):
            get_sheet_index(PlzFilter())
