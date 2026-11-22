"""Draw a step's render as pixels, which is what the embedding model looks at."""

import resvg_py

# Width a render is drawn at, in pixels: a little more than the model looks at.
render_width = 448

# Color drawn behind a render, which may leave its paper unpainted.
background = "#ffffff"


def rasterize_svg(svg_markup: str) -> bytes:
	"""Return SVG markup drawn as a PNG. Blocking.

	The markup is only parsed and painted; nothing inside it is run.

	Raises:
		ValueError: The markup is not SVG that can be drawn.
	"""
	return bytes(
		resvg_py.svg_to_bytes(svg_string=svg_markup, width=render_width, background=background)
	)
