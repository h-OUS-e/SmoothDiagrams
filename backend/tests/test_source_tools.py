"""Tests for applying edits and reading streamed tool input."""

import pytest

from smooth_diagrams.generation.partial_json import read_partial_string_field
from smooth_diagrams.generation.source_edits import SourceEdit, SourceEditError, apply_source_edits


def test_edits_apply_in_order() -> None:
	source = "<circle r=10 />"
	edits = [SourceEdit("r=10", "r=20"), SourceEdit("r=20", "r=30")]
	assert apply_source_edits(source, edits) == "<circle r=30 />"


def test_edit_must_match_exactly_once() -> None:
	with pytest.raises(SourceEditError, match="matches 2 places"):
		apply_source_edits("<circle /><circle />", [SourceEdit("<circle />", "<rect />")])


def test_edit_must_be_found() -> None:
	with pytest.raises(SourceEditError, match="was not found"):
		apply_source_edits("<circle />", [SourceEdit("<rect />", "<path />")])


def test_empty_old_text_is_refused() -> None:
	with pytest.raises(SourceEditError, match="old_text is empty"):
		apply_source_edits("<circle />", [SourceEdit("", "<path />")])


def test_partial_field_grows_as_json_streams() -> None:
	assert read_partial_string_field('{"design_', "design_note") is None
	assert read_partial_string_field('{"design_note": "Thin ri', "design_note") == "Thin ri"
	assert (
		read_partial_string_field('{"design_note": "Thin rings", "so', "design_note")
		== "Thin rings"
	)


def test_partial_field_keeps_escapes_whole() -> None:
	# A cut inside an escape sequence leaves the escape out until it is complete.
	assert read_partial_string_field('{"design_note": "a \\', "design_note") == "a "
	assert read_partial_string_field('{"design_note": "a \\"b', "design_note") == 'a "b'
	assert read_partial_string_field('{"design_note": "caf\\u00e', "design_note") == "caf"
	assert read_partial_string_field('{"design_note": "caf\\u00e9', "design_note") == "café"
