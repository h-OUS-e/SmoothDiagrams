"""Read the prompt templates kept as files in the prompts folder."""

from functools import lru_cache
from pathlib import Path

prompts_directory = Path(__file__).resolve().parent / "prompts"


@lru_cache
def read_prompt(name: str) -> str:
	"""Return the text of one prompt template."""
	return (prompts_directory / f"{name}.md").read_text(encoding="utf-8").strip()
