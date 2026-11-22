"""Apply a model's exact-text edits to a diagram source."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SourceEdit:
	"""One replacement of an exact passage of the source."""

	old_text: str
	new_text: str


class SourceEditError(Exception):
	"""An edit cannot be applied; the message is written for the model to act on."""


def apply_source_edits(source: str, edits: list[SourceEdit]) -> str:
	"""Return the source with every edit applied in order.

	Args:
		source: The current diagram source.
		edits: Replacements to apply, each to the result of the one before it.

	Returns:
		The edited source.

	Raises:
		SourceEditError: An edit's old text is empty, missing, or found more than once.
	"""
	edited_source = source

	for position, edit in enumerate(edits, start=1):
		if edit.old_text == "":
			raise SourceEditError(f"Edit {position}: old_text is empty.")

		# Require exactly one match, so an edit can never land in the wrong place.
		match_count = edited_source.count(edit.old_text)
		if match_count == 0:
			raise SourceEditError(
				f"Edit {position}: old_text was not found in the current source. "
				"It must match the source exactly, including whitespace."
			)
		if match_count > 1:
			raise SourceEditError(
				f"Edit {position}: old_text matches {match_count} places. "
				"Include more surrounding text so it matches exactly one."
			)

		edited_source = edited_source.replace(edit.old_text, edit.new_text, 1)

	return edited_source
