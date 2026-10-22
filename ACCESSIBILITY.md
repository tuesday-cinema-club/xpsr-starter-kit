# Accessibility

This repository is meant to be usable with a screen reader, with a keyboard only, without color, and on a phone. These are the conventions every file follows. If something falls short, please open an issue.

## Writing

- One top-level heading per file, then headings in order (no skipped levels), so heading navigation gives a true outline.
- Plain language and short sentences. Terms are explained the first time they appear.
- Steps are numbered lists. Diagrams are written as numbered steps rather than ASCII art, which screen readers read as a string of symbols.
- Links say where they go ("the hardware matrix"), never "click here".

## Tables

- Every table has a header row and one idea per column.
- No merged cells and no empty header cells.
- Tables are used for data, not for layout.

## Images

- Every image has alt text that says what it shows and why it matters, including the key text inside a screenshot.
- Terminal screenshots are copies of output that also appears as text in the scripts' own documentation, so nothing is only available as a picture.

## Color and symbols

- Nothing depends on color alone. Script output starts each line with a word: `[pass]`, `[fail]`, `[warn]`, `[working]`, `[next]`. The setup check uses READY, MISSING and OPTIONAL.
- The handout's phone marker is always written as the words "Phone OK", with the emoji as decoration only.
- Project bibles give the palette as hex codes and as plain names ("roast brown", "steamed milk").

## Video

- Every cut is delivered twice: once with captions burned in (open captions, white on a mostly opaque dark box) and once with a selectable subtitle track (closed captions).
- Captions are broken at 42 characters and 2 lines, and none runs across a shot change.
- A person checks every Whisper caption against the audio before release.
- Animated previews in the READMEs have no sound and loop. Each one has alt text describing the whole sequence and sits next to a link to the full cut with sound. If moving images are distracting, GitHub can stop them from playing automatically: Settings, Accessibility, Motion.
- End cards use typed text, never text generated inside an image.

## Taking part without a laptop

A phone is a full seat at the table: the Director and Auditor crews need nothing installed, and the Previs and Edit & Sound crews use phones for camera-move reference and voiceover recording.
