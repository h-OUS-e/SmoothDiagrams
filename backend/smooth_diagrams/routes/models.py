"""Route for the models a director can choose."""

from fastapi import APIRouter, Request

from smooth_diagrams.model_catalog import ModelCatalog, model_options

router = APIRouter()


@router.get("/models")
async def get_model_catalog(request: Request) -> ModelCatalog:
	"""Return every selectable model and the default one."""
	return ModelCatalog(
		default_model=request.app.state.settings.default_model, models=model_options
	)
