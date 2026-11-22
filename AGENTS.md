# GENERAL RULES
- You were trained on an older data. Always assume that there may be an update you need to lookup
- Reuse components where possible
- Prefer established library terms over invented or complicated names unless they conflict with existing repo terminology.
- Put UI or effects with potential for reuse in separate components, even when initially used in only one place.
- If a component is getting complicated, offer to break it down.
- If multiple components start sharing same strucutre, offer to extract general structure as a parent component.
- Keep instructions minimal in AGENTS.md and vocabulary in CONTEXT.md
- Add docs only for decisions or findings that would be costly to reconstruct.
- Remove any testing files after you are done testing to avoid cluterring the repo.
- Read CONTEXT.md. Push against me if a naming doesn't make sense or a code structure might cause trouble down the line.
- Never take shortcuts to write code. This is professional portfolio and repo that needs to be maintained.

# STYLING RULES

## Banned Styling
- Never use em dashes 
- Never use emojis in comments

## Comments Styling Rules

- Every complex function gets a one-line comment starting with a verb: "Return chat history with expired messages removed." No "A method to..." filler. 
- Long or hard-to-understand functions upgrade to a Google style docstring with args and returns; its summary line still starts with a verb.
- Inside a function, separate logical steps with a blank line and open each step with a one-line comment saying what it does in plain words.
- Add a one-line, verb-first comment before substantial template blocks, such as loops rendering images with captions, to describe what the block displays.
- Comments say what first; add why in the same line only when the code could mislead.
- Keep ordinary comments one line, never multi-sentence; section dividers may use multiline block comments with short labels.
- Comments use only code words, never coined shorthand or invented words. Check CONTEXT.md for words used in the codebase.
- Never copy the surrounding code's comment style; these rules win over local style.
- A comment that breaks these rules is a defect: fix it in any file you edit, the same way a space-indented file gets converted to tabs.
- Check compliance while writing code. 
- Use `//` in JavaScript, TypeScript, and Svelte scripts; use `<!-- ... -->` in Svelte markup. Allow `/* ... */` for file headers and section dividers. Allow `/** */` to describe a functio ncontract docstring in js/ts scripts.


## Code styling
- use snake case for variables, functions, methods of a class, dircetors
- use Pascal casing for svelte component names and class objects
- don't use camel case names for variables or constants or functions
- ask me when unsure about how to style something.
- Keep an empty line between major code sections, don't make it look cramped. Add a one-line comment or block divider for a section.
- Be consistent about used vocabular when writing variables. CONTEXT.md has a list of vocab list, but doesn't include everything. For instance, if writing EventEnded and whant to describe the end of some other attribute like Dragging, don't write DraggingFinished. Instead, write DraggingEnded. But also use the right vocab thoughtfully (e.g. released is different from ended, ContactReleased will have a different meaning from ContactEnded, so it may be appropriate to use ContactReleased instead of ended in this case). 

# Repo
- Frontend is inside frontend/ dir
- Local server is inside backend/ dir


# Grilling sessions

- Each question is one line: name the decision and the options, nothing else.
- The above rule can be broken if the question NEEDS context to properly explain it. Even then, strive for concise yet clear.
- Try to fit recommendation ns one line, no reasoning unless I ask or unless the concept is complex.
- Do not restate context I already know or decisions already settled.
- Findings that reshape questions get one line each, before the questions.
- Do NOT use shorthand or invent words. Be explicit.
- Do NOT introduce shortcuts unless I ask for them.

# Git 
- Don't git commit, I should be committing
- Give me a git add and commit -m commands. add should include files you changed. commit message should be a short message. ensure they are in separate boxes i can quickly copy and paste.

# What makes pages fast
These are general rules for you to remind me. Don't implement them without clearly notifying me (i don't want to downsize images accidentally)
- Export appropriately sized images; serve smaller variants on smaller screens.
- Load the first visible cover immediately; lazy-load later images.
- Give images explicit dimensions or an aspect ratio.
- Show video posters and defer video downloads.
- Cache published assets using versioned URLs.

# What images belong where
Keep code and small site assets in Git. Put published project media in R2. This rule is for both of us, so remind me of it.
- GitHub repository: Code, project text, metadata, logos, icons, small shared SVGs, fonts, robots.txt
- Public R2 bucket: Project covers, thumbnails, stickers, photographs, screenshots, videos, PDFs, downloads; future Blog and Misc media
- Private storage outside Git: Original photographs, PSD files, editing files, raw footage, unpublished material