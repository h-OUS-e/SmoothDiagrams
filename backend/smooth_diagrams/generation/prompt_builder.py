"""Build every prompt the model receives from the templates in the prompts folder."""

from functools import lru_cache
from pathlib import Path

prompts_directory = Path(__file__).resolve().parent / "prompts"


@lru_cache
def read_prompt(name: str) -> str:
	"""Return the text of one prompt template."""
	return (prompts_directory / f"{name}.md").read_text(encoding="utf-8").strip()


def format_source(source: str) -> str:
	"""Return a source as a fenced block, or a note that there is none yet."""
	if source == "":
		return "(The source is still empty.)"
	return f"```svelte\n{source}\n```"


def build_system_prompt(is_step_by_step: bool) -> str:
	"""Return the system prompt: the diagram rules plus the chosen way of working."""
	working_mode = "step_by_step" if is_step_by_step else "single_pass"
	return f"{read_prompt('diagram_rules')}\n\n{read_prompt(working_mode)}"


def build_first_prompt(prompt: str, base_source: str) -> str:
	"""Return the prompt that opens a generation, with the source it continues from if any."""
	if base_source == "":
		return read_prompt("first_request").format(prompt=prompt)
	return read_prompt("continue_request").format(prompt=prompt, source=format_source(base_source))


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
