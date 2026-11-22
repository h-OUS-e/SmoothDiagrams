"""Build every prompt the model receives from the templates in the prompts folder."""

from smooth_diagrams.generation.prompt_context import ContextSection, PromptContext
from smooth_diagrams.generation.prompt_templates import read_prompt
from smooth_diagrams.interface_settings import InterfaceSettings
from smooth_diagrams.providers.base import PromptImage


def format_source(source: str) -> str:
	"""Return a source as a fenced block, or a note that there is none yet."""
	if source == "":
		return "(The source is still empty.)"
	return f"```svelte\n{source}\n```"


def build_system_prompt(interface: InterfaceSettings) -> str:
	"""Return the system prompt: the fixed diagram rules plus what the interface adds.

	The interface chooses the way of working, and may add a direction for the project and
	the instructions of its prompt controls.
	"""
	templates = interface.prompt_templates
	parts = [
		read_prompt("diagram_rules"),
		templates.step_by_step if interface.is_step_by_step else templates.single_pass,
	]

	if templates.direction.strip():
		parts.append(read_prompt("interface_direction").format(direction=templates.direction))

	# Tell the model the value of every prompt control that has something to say.
	instructions = [control.render() for control in interface.prompt_controls]
	lines = "\n".join(f"- {instruction}" for instruction in instructions if instruction)
	if lines:
		parts.append(read_prompt("interface_settings").format(instructions=lines))
	return "\n\n".join(parts)


def format_sections(sections: list[ContextSection], images: list[PromptImage]) -> str:
	"""Return context sections as text, numbering each attached image as it is added."""
	blocks: list[str] = []
	for section in sections:
		lines = [f"### {section.heading}"]
		if section.image is not None:
			images.append(section.image)
			lines.append(f"Attached as image {len(images)}.")
		if section.body:
			lines.append(section.body)
		blocks.append("\n\n".join(lines))
	return "\n\n".join(blocks)


def build_first_prompt(
	prompt: str, base_source: str, context: PromptContext
) -> tuple[str, list[PromptImage]]:
	"""Return the prompt that opens a generation and the images it refers to.

	Args:
		prompt: The request of the director.
		base_source: Source the generation continues from, or an empty string.
		context: Taste priors, priors, and taste reasons that apply.

	Returns:
		The prompt text, and the attached images in the order the text numbers them.
	"""
	images: list[PromptImage] = []
	parts: list[str] = []

	# Lead with standing taste, then the references of the project, then the history of the branch.
	if context.taste_sections:
		sections = format_sections(context.taste_sections, images)
		parts.append(read_prompt("context_taste").format(sections=sections))
	if context.prior_sections:
		sections = format_sections(context.prior_sections, images)
		parts.append(read_prompt("context_priors").format(sections=sections))
	if context.taste_reasons:
		reasons = "\n".join(f"- {reason}" for reason in context.taste_reasons)
		parts.append(read_prompt("context_taste_reasons").format(reasons=reasons))
	if context.edited_render is not None:
		images.append(context.edited_render)
		parts.append(read_prompt("context_edited_render").format(image_number=len(images)))

	# End with the request itself, so it is the last thing the model reads.
	if base_source == "":
		request = read_prompt("first_request").format(prompt=prompt)
	else:
		request = read_prompt("continue_request").format(
			prompt=prompt, source=format_source(base_source)
		)
	if parts:
		request = f"## The request\n\n{request}"
	return "\n\n".join([*parts, request]), images


def build_redirect_prompt(direction: str, current_source: str) -> str:
	"""Return the prompt that tells the model the director changed direction."""
	return read_prompt("redirect").format(direction=direction, source=format_source(current_source))


def build_reject_prompt(step_reasoning: str, reason: str | None, current_source: str) -> str:
	"""Return the prompt that tells the model its latest step was rejected."""
	reason_line = f"Their reason: {reason}" if reason else "They gave no reason."
	return read_prompt("reject").format(
		step_reasoning=step_reasoning, reason=reason_line, source=format_source(current_source)
	)


def build_resume_prompt(current_source: str) -> str:
	"""Return the prompt that tells the model to carry on after a pause."""
	return read_prompt("resume").format(source=format_source(current_source))
