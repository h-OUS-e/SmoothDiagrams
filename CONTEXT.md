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

A reference the user selects to guide generation in one Project: an item picked
from the Library, or a text of its own such as a brief.
_Avoid_: reference, example

### Prior Note

Optional free text on a Prior telling the model what to focus on.
_Avoid_: prompt tag, caption

### Taste Prior

A Prior kept outside any Project that guides taste across Projects. It is taste
notes, a skill document, or an image, and it can be switched on or off.
_Avoid_: permanent prior

### Library

A collection shared across Projects that holds reference images and Nodes the
user has sent to it. It is where Priors are picked from, not a view of the current
Project's Pieces. It is ordered by date, by name, or by how much each item looks
like one the director picks.
_Avoid_: gallery, assets

### Export

Downloading a Step of a Node as a Svelte component, a static SVG, a PNG, or a JPEG.
Each Export is remembered on its Node with the Step, the parameter values, the
animation time, and the size it was made with.
_Avoid_: publish, download

### Interface

A Project's saved setup for directing: the model, the way of working, its Prompt
Controls, its prompt templates, and which Taste Priors it switches off. It is kept
as versions, and a new Project can start from a copy of any version of any Project.
_Avoid_: layout, preset

### Interface Version

One saved state of an Interface. It is frozen once a Node was made with it or
another version was copied from it, and each Node records the version that made it.
_Avoid_: snapshot, revision

### Prompt Control

A control an Interface defines for the director, such as a ratio choice or a
novelty slider. Its value reaches the model as an instruction, not as a value in
the Diagram's source.
_Avoid_: permanent parameter, setting

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

### A Taste Reason lives on the Node that continues, not on the Node that was picked

A Taste Reason says why the director continued from a parent Node, but it is stored
on the child, because one parent can be continued several times for different
reasons. A generation is told the Taste Reasons of every Node on the path from the
root to the Node it continues from, so a reason reaches later generations on that
branch and no others. Candidates the director never picked are kept but not told.

### What a Prior shows the model depends on what it is

An image Prior is attached as an image. A Node Prior is given as text: the requests
that led to it, the Step Reasonings of its Steps, and its final source, because a
model that writes code learns more from the code than from a picture of its render.
An Uploaded Node used as a Prior counts as an image.

### Continuing from an Uploaded Node starts from the source it was an edit of

An Uploaded Node has no source, so a generation that continues from it starts from
the source of the Step the upload was an edit of, and is shown the uploaded image
as the state to bring that source in line with.

### An Interface Version freezes when it is used, not on every change

The first plan was a new immutable version for every change. A slider dragged from
30 to 80 would then leave dozens of versions that never produced anything. Instead
the current version changes in place until a Node is made with it or a Project is
started from it; from then on it never changes, and the next change continues in a
new version. Every setup that produced work is kept, and nothing else.

### The server reads generation settings from the Interface, not from the request

A generation is started with only the piece, the parent, and the prompt. The model,
the way of working, the Prompt Controls, and the Taste Priors come from the
Project's current Interface Version, which is why the frontend stores pending
Interface changes before it starts a generation, and refuses to start if that fails.

### The diagram rules are not part of the Interface

The director can rewrite the direction and the two ways of working per Project.
The rules of the source format stay in a fixed file, because the viewer checks
those rules and a reworded copy would produce Steps that fail to render.

### An Interface lists the Taste Priors it switches off

Taste Priors apply to every Project unless a Project's Interface switches them
off, so a Taste Prior added later is on everywhere without touching old versions.

### Export files are made in the browser, and only their settings are kept

The browser already holds the diagram as the director sees it, so an SVG is that
markup, a PNG or JPEG is that markup drawn on a canvas, and a Svelte component is
the Step's source with the director's values written in as the defaults of its
props. The server stores what the file was made from, not the file, so an Export
can be made again without the app keeping copies of files the director already has.

### Visual similarity runs CLIP through ONNX Runtime, not torch

The Library is sorted with the image half of CLIP ViT-B/32. ONNX Runtime adds about
40 MB of packages where torch would add gigabytes. The owner chose the quantized
model file (89 MB) over the full one (352 MB) on 2026-11-22; the file is one
setting. It is downloaded from Hugging Face at a pinned revision the first time the
Library is sorted by similarity, and never before.

### A Node in the Library is compared by a picture drawn on the server

An embedding needs pixels, and a Node only has the SVG markup of its renders. The
server draws that markup itself with resvg instead of asking the browser for a
picture, so any item can be embedded at any time without the app being open on it.
Each embedding is kept on its Library item with the model and the asset or Step it
came from, and is computed again only when one of those changes. Images are fitted
whole onto a white square, because the usual center crop would cut the sides off a
wide diagram.

### Animation is driven by a time prop

A diagram that moves declares its duration and derives everything from a `time`
prop the viewer supplies. Timers, CSS animations, and SMIL are forbidden in the
prompt, because the play slider could not scrub them and a later export could not
capture them frame by frame.

