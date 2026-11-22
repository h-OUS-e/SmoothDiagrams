"""Offer the director candidate reasons for continuing from a node, through a separate agent."""

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from smooth_diagrams.database.models import Node, Step
from smooth_diagrams.generation.prompt_templates import read_prompt
from smooth_diagrams.providers.base import ModelCallError, ModelProvider

candidate_count = 3


class NoParentError(Exception):
	"""A node that continues nothing has no pick to explain."""


def parse_candidates(answer: str) -> list[str]:
	"""Return the candidate reasons in the agent's answer.

	Raises:
		ModelCallError: The answer holds no JSON array of non-empty strings.
	"""
	# Read the array even when the agent wrapped it in a code fence or a sentence.
	start, end = answer.find("["), answer.rfind("]")
	try:
		candidates = json.loads(answer[start : end + 1]) if start != -1 and end > start else None
	except json.JSONDecodeError:
		candidates = None

	is_valid = (
		isinstance(candidates, list)
		and len(candidates) > 0
		and all(isinstance(candidate, str) and candidate.strip() for candidate in candidates)
	)
	if not is_valid:
		raise ModelCallError("The taste reason agent did not answer in the expected form.")
	return [candidate.strip() for candidate in candidates[:candidate_count]]


async def build_request(session: AsyncSession, node: Node, parent: Node) -> str:
	"""Return the prompt that describes the director's pick to the agent."""
	# Describe the picked diagram through the captions of its steps.
	result = await session.execute(
		select(Step)
		.where(Step.node_id == parent.id, Step.is_rejected.is_(False))
		.order_by(Step.step_index)
	)
	steps = list(result.scalars())
	step_captions = "\n".join(
		f"{position}. {step.step_reasoning}" for position, step in enumerate(steps, 1)
	)

	# Say whether the director kept the final step or went back to an earlier one.
	step_ids = [step.id for step in steps]
	if node.parent_step_id in step_ids and node.parent_step_id != step_ids[-1]:
		step_number = step_ids.index(node.parent_step_id) + 1
		continued_from = (
			f"The director continued from step {step_number} of {len(steps)}, "
			"leaving the later steps behind."
		)
	else:
		continued_from = "The director continued from its final state."

	# Mention what else the director asked of the same diagram, which hints at what they valued.
	sibling_result = await session.execute(
		select(Node.prompt)
		.where(Node.parent_node_id == parent.id, Node.id != node.id, Node.prompt != "")
		.order_by(Node.created_at)
	)
	sibling_prompts = list(sibling_result.scalars())
	siblings = ""
	if sibling_prompts:
		lines = "\n".join(f"- {prompt}" for prompt in sibling_prompts)
		siblings = f"Other changes they asked for from the same diagram:\n{lines}"

	return read_prompt("taste_reasons_request").format(
		parent_prompt=parent.prompt or "(It was uploaded by the director.)",
		step_captions=step_captions or "(It has no steps.)",
		continued_from=continued_from,
		siblings=siblings,
		child_prompt=node.prompt,
	)


async def offer_taste_reasons(
	session: AsyncSession, provider: ModelProvider, model: str, node: Node
) -> list[str]:
	"""Ask the agent for candidate reasons, store them on the node, and return them.

	Args:
		session: Database session to read from and store the candidates with.
		provider: Model provider that answers the agent's prompt.
		model: Id of the model the agent runs on.
		node: The node whose parent the director picked.

	Returns:
		Up to three candidate reasons, in the director's voice.

	Raises:
		NoParentError: The node continues no other node.
		ModelCallError: The model call failed or answered in an unusable form.
	"""
	parent = await session.get(Node, node.parent_node_id) if node.parent_node_id else None
	if parent is None:
		raise NoParentError

	answer = await provider.complete(
		system_prompt=read_prompt("taste_reasons_system"),
		prompt=await build_request(session, node, parent),
		model=model,
	)
	candidates = parse_candidates(answer)

	node.taste_reason_candidates = candidates
	await session.commit()
	return candidates
