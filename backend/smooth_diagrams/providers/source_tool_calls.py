"""The two source tools as every vendor's model sees them, and how a call to one is carried out."""

from dataclasses import dataclass
from typing import Any

from smooth_diagrams.generation.source_edits import SourceEdit
from smooth_diagrams.providers.base import SourceTools, ToolReply

write_source_name = "write_source"
edit_source_name = "edit_source"

# Name the model knows a Step Reasoning by; see the note on wording in CONTEXT.md.
design_note_field = "design_note"

design_note_schema = {
	"type": "string",
	"description": (
		"Caption for the director, at most 25 words: the design choice this step makes "
		"and the alternative it passes over."
	),
}

write_source_schema = {
	"type": "object",
	"properties": {
		design_note_field: design_note_schema,
		"source": {"type": "string", "description": "The complete new source of the diagram."},
	},
	"required": [design_note_field, "source"],
}

edit_source_schema = {
	"type": "object",
	"properties": {
		design_note_field: design_note_schema,
		"edits": {
			"type": "array",
			"minItems": 1,
			"description": "Replacements applied in order, each to the result of the last.",
			"items": {
				"type": "object",
				"properties": {
					"old_text": {
						"type": "string",
						"description": "Exact text to replace. It must occur exactly once.",
					},
					"new_text": {"type": "string", "description": "Text to put in its place."},
				},
				"required": ["old_text", "new_text"],
			},
		},
	},
	"required": [design_note_field, "edits"],
}


@dataclass(frozen=True)
class SourceToolSpec:
	"""What a model is told about one source tool."""

	name: str
	description: str
	input_schema: dict[str, Any]


source_tool_specs = (
	SourceToolSpec(write_source_name, "Replace the whole source as one step.", write_source_schema),
	SourceToolSpec(
		edit_source_name, "Replace exact passages of the source as one step.", edit_source_schema
	),
)


async def call_source_tool(source_tools: SourceTools, tool_name: str, arguments: Any) -> ToolReply:
	"""Carry out a model's call to a source tool and return what the model reads back.

	Args:
		source_tools: The tools of the running generation.
		tool_name: The tool the model named.
		arguments: The arguments the model gave, which may be malformed.

	Returns:
		The reply of the tool, or an error reply when the call cannot be understood.
	"""
	if not isinstance(arguments, dict):
		return ToolReply("The arguments must be an object.", is_error=True)
	step_reasoning = arguments.get(design_note_field)

	if tool_name == write_source_name:
		source = arguments.get("source")
		if not isinstance(step_reasoning, str) or not isinstance(source, str):
			return ToolReply("design_note and source must be strings.", is_error=True)
		return await source_tools.write_source(step_reasoning, source)

	if tool_name == edit_source_name:
		raw_edits = arguments.get("edits")
		if not isinstance(step_reasoning, str) or not isinstance(raw_edits, list):
			return ToolReply("design_note and edits are required.", is_error=True)

		# Read each edit, refusing any that is not a pair of strings.
		edits: list[SourceEdit] = []
		for raw_edit in raw_edits:
			old_text = raw_edit.get("old_text") if isinstance(raw_edit, dict) else None
			new_text = raw_edit.get("new_text") if isinstance(raw_edit, dict) else None
			if not isinstance(old_text, str) or not isinstance(new_text, str):
				return ToolReply("Every edit needs old_text and new_text.", is_error=True)
			edits.append(SourceEdit(old_text=old_text, new_text=new_text))
		return await source_tools.edit_source(step_reasoning, edits)

	return ToolReply(f"There is no tool named {tool_name}.", is_error=True)
