"""Read a string field out of JSON that is still being streamed."""

import json
import re


def read_partial_string_field(partial_json: str, field_name: str) -> str | None:
	"""Return as much of a top-level string field as has arrived so far.

	Args:
		partial_json: The beginning of a JSON object, possibly cut off anywhere.
		field_name: Name of the string field to read.

	Returns:
		The decoded text received so far, or None when the field has not started.
	"""
	# Find where the field's string value begins.
	field_start = re.search(rf'"{re.escape(field_name)}"\s*:\s*"', partial_json)
	if field_start is None:
		return None

	# Collect characters up to the closing quote, keeping escape sequences whole.
	characters: list[str] = []
	position = field_start.end()
	while position < len(partial_json):
		character = partial_json[position]
		if character == '"':
			break
		if character == "\\":
			escape_length = 6 if partial_json[position + 1 : position + 2] == "u" else 2
			if position + escape_length > len(partial_json):
				break
			characters.append(partial_json[position : position + escape_length])
			position += escape_length
			continue
		characters.append(character)
		position += 1

	try:
		return json.loads(f'"{"".join(characters)}"')
	except json.JSONDecodeError:
		return None
