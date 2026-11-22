# Context

Vocabulary for this project. These are the words used in code identifiers,
comments, commits, and UI copy. The `Avoid` lines matter as much as the
definitions; they are what stops the codebase drifting into generic naming.

## Language

### Component

A UI building block of the app, such as a button, a container, or an icon.
Components can be reusable even when initially used in only one place. General
components live in `frontend/src/lib/components/`; components tied to a particular
route or feature can live beside that code.
_Avoid_: widget, UI module

### Project

The top-level container for one body of work. A project holds Pieces, Priors, and
one Interface.

### Piece

One tree of Nodes inside a Project, grown from a single root Node. A series is
several Pieces in one Project.
_Avoid_: tree, artwork

### Node

One point in a Piece's tree. A node has one parent node, unless it is the root,
and holds a linear sequence of Steps. A post-edit is always a new Node, never a
replacement of an existing one.
_Avoid_: version, revision

### Uploaded Node

A Node that holds an image the user brought in from outside the app instead of
source. It has no Steps and no exposed parameters.
_Avoid_: imported node, attachment

### Diagram

What a single Node renders.
_Avoid_: image, picture

### Prior

A reference the user selects to guide generation, such as a past creation.
_Avoid_: reference, example

### Prior Note

Optional free text on a Prior telling the model what to focus on.
_Avoid_: prompt tag, caption

### Taste Prior

A Prior kept outside any Project that guides taste across Projects. It can be
switched on or off.
_Avoid_: permanent prior

### Library

A collection shared across Projects that holds reference images and Nodes the
user has sent to it. It is where Priors are picked from, not a view of the current
Project's Pieces.
_Avoid_: gallery, assets

### Export

Downloading a Node as a Svelte component, a static SVG, a PNG, or a JPEG. Each
Export is remembered on its Node.
_Avoid_: publish, download

### Interface

A Project's saved setup for directing: its permanent controls, its prompt
templates, and which taste Priors are on by default. Every change saves a new
immutable version, and a new Project can start from a copy of any version.
_Avoid_: layout, preset

### Step

One meaningful addition to a Node's source, such as a visual component, a relation,
or an exposed parameter. A step always renders successfully and carries a Step
Reasoning. Steps are linear inside a Node and never branch.
_Avoid_: layer, stage, iteration

### Step Reasoning

The model's one-line explanation on a Step: why it was chosen, and why another
direction was not.
_Avoid_: reason, rationale

### Exposed Parameter

A value of a Diagram that its source offers to the director as a control. It has
a kind (number, color, text, boolean, select) and a group (general, styling,
animation, copy).
_Avoid_: prop, setting, knob

### Taste Reason

The user's explanation for continuing from a Node, picked from candidates offered
by a separate agent or written freely. A picked Taste Reason guides every later
generation on that branch.
_Avoid_: reasoning, feedback

### Fork

Creating a child Node that starts from a chosen Step of another Node. The original
Node keeps all of its Steps.
_Avoid_: clone, duplicate

## Decisions

Choices that are not obvious from the code, and why they were made.

### Model calls use plan logins through the vendors' agent programs

The local server calls Claude through the Claude Agent SDK and GPT through Codex
app-server, signed in with personal plan logins instead of metered API keys. This
fits a personal, single-user app. Anthropic's policy bars offering Claude plan
login to other users, so adding accounts would mean moving to API keys.
Checked against vendor docs on 2026-11-21.

### Step source is compiled in the browser

Each Step's Svelte source is compiled in a web worker and run in a sandboxed
iframe. The Svelte compiler is JavaScript and the server is Python, and a compile
measured about 4 ms for a 150-line diagram, so the browser is the natural place.
The sandbox exists because the source is model-written code that must not reach
the app, Supabase, or the network.

### The local server is Python

Chosen by the owner's preference; it also lets the local embedding model for
visual similarity run in the same process. The cost is that Node and Step types
are not shared with the TypeScript frontend.

### Storage is local SQLite for now, built to move to Supabase

The owner chose a local SQLite file over a hosted Supabase project for the first
version. The schema uses only column types that Postgres also has, every change
goes through an Alembic migration, and the database is chosen by one URL setting,
so moving to Supabase means changing that URL and running the migrations. The
frontend never talks to the database; it only talks to the local server.

### The model calls a Step Reasoning a "design note"

The prompt and the tool schema ask the model for a `design_note`, never for its
"reasoning". Wording that asks the model to explain how it thinks is refused by the
model's safeguards, which read it as an attempt to extract hidden reasoning. The
app keeps the term Step Reasoning everywhere else.

### Every proposed Step is rendered before it is saved

The server holds a Step the model proposes until the frontend reports that it
compiled and rendered, and sends the failure back to the model otherwise. This is
why a generation needs the app open in a browser, and why the page keeps a second,
hidden viewer: checking a Step must not disturb the diagram on screen.

### Animation is driven by a time prop

A diagram that moves declares its duration and derives everything from a `time`
prop the viewer supplies. Timers, CSS animations, and SMIL are forbidden in the
prompt, because the play slider could not scrub them and a later export could not
capture them frame by frame.

