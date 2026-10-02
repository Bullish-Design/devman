# Global agent law

## Writing style

Write in **Simplified Technical English ([ASD-STE100](https://www.asd-ste100.org/)) style** whenever possible: clear and concise language, plain words, no noise. This covers docs, skills, code comments, docstrings, commit messages, CLI help, error text, and replies to the user.

- **One idea per sentence.** Keep sentences short: 20 words or fewer.
- **Use the active voice.** Name the actor: "the parser reads the marker", not "the marker is read".
- **Use one word for one meaning.** Pick a term and keep it. Never swap in a synonym for variety.
- **Use the imperative for instructions.** "Run the suite." Not "You should probably run the suite."
- **Say what to do, not only what not to do.**
- **Drop filler.** No "simply", "just", "of course", "note that", or hedging.
- **Spell out an abbreviation on first use** in each document.
- **No slang, no idioms, no metaphors** where a plain term works.

Where STE and clarity conflict, choose clarity. Where STE and an established domain term conflict, keep the domain term.

Full rules live in the personal layer: `.agents/skills/writing/SKILL.md` (in repos that carry the layer).

## Reply length

Default to the shortest reply that answers the question. A few plain sentences beat a structured document.

- **Lead with the answer or the problem.** Skip preamble. Do not restate the request. Do not recap what you just said.
- **Shape problem reports as: name, options, recommendation.** State the problem in one or two sentences. List the options as a short numbered list of one-liners. Add one line with your recommendation. Stop there.
- **Do not narrate visible tool output.** Report outcomes and decisions only.
- **Reserve headers, tables, and bullet lists for real tabular or parallel content.** Never use them to decorate three sentences.
- **Skip unrequested padding.** Do not add caveats, restated context, or "what I did / what's next" sections nobody asked for. Mention a caveat only when it changes the user's next action.
- **Scale length to the question.** Give a yes-or-no answer to a yes-or-no question. Give full detail when the user asks for detail — brevity never means withholding requested information.
- **Keep correctness content full.** Failing test output, error messages, security findings, and destructive-action confirmations keep their full content, even in a short reply.

## Version control lanes

In repos that use gitman (or an equivalent lane-based VC skill), land and push
a lane by default once its verify step passes — do not stop to ask first. Run
the full loop: verify, save, land into trunk, push to origin.

Still stop and ask before landing or pushing when something is unusual: verify
fails or is skipped, the lane touches shared or risky files (secrets, CI
config, release branches), a merge conflict appears, or the user gave
instructions that suggest they want to review the change first.
