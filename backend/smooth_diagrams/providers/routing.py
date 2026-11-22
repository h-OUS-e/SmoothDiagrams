"""One provider that hands every call to the vendor whose model was asked for."""

from collections.abc import Mapping
from contextlib import AbstractAsyncContextManager

from smooth_diagrams.model_catalog import ModelVendor, find_model
from smooth_diagrams.providers.base import ModelCallError, ModelProvider, ModelSession, SourceTools


class RoutingProvider:
	"""Picks the provider of a model's vendor, so callers only ever name a model."""

	def __init__(self, providers: Mapping[ModelVendor, ModelProvider]) -> None:
		self._providers = providers

	def _find_provider(self, model: str) -> ModelProvider:
		"""Return the provider that runs a model.

		Raises:
			ModelCallError: The model is not one of the selectable models.
		"""
		option = find_model(model)
		provider = self._providers.get(option.vendor) if option else None
		if provider is None:
			raise ModelCallError(
				f"There is no model named {model}. Choose another under Prompting."
			)
		return provider

	def open_session(
		self, *, system_prompt: str, model: str, source_tools: SourceTools
	) -> AbstractAsyncContextManager[ModelSession]:
		"""Open a conversation that lasts for one generation."""
		return self._find_provider(model).open_session(
			system_prompt=system_prompt, model=model, source_tools=source_tools
		)

	async def complete(self, *, system_prompt: str, prompt: str, model: str) -> str:
		"""Return the answer to one prompt, with no tools and no memory."""
		return await self._find_provider(model).complete(
			system_prompt=system_prompt, prompt=prompt, model=model
		)
