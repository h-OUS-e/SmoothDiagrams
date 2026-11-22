# SmoothDiagrams
Creating SVG diagrams with ease by exploiting smooth interactions with visual priors, visual edits, prompting, and context.

## Running it

The app is two processes: a local server that stores the work and calls the models, and the frontend.

Start the local server from `backend/`. It needs the Claude Code login of this machine for the Claude models, and the Codex login (`codex login`) for the GPT models; either one alone is enough to draw with its models. It creates its SQLite database in `backend/data/` on first start. `uv run` uses the project's own environment in `backend/.venv`, whichever conda environment is active.

```bash
uv run uvicorn smooth_diagrams.main:app --port 8000
```

Start the frontend from `frontend/`, then open http://localhost:5173.

```bash
yarn dev
```

Sorting the Library by similarity downloads an 89 MB image model from Hugging Face the first time it is used. Nothing is downloaded before that.

## Checking it

```bash
# backend/
uv run --extra dev pytest
uv run --extra dev ruff check .

# frontend/
yarn run check
yarn lint
yarn test:e2e
```

Vocabulary and the decisions behind the design are in [CONTEXT.md](CONTEXT.md).
