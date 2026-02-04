# Devman

## Overview:
An opinionated development assistant, built on a context driven template based workflow enabled by a combination of copier and watchdog. In general:
- User creates file
- If file matches template match parameters: (name, location, type, etc.)
    - Create associated copier template repo in appropriate location
    - Replace file with generated + symlinked file from copier template repo
- Refine context of template repo until file is generated correctly via:
    - Input context (docs, notes, overviews, examples)
    - Prodding context (git hook scripts/workflow loops)
    - Validation context (tests, filters, pick-best-of-N style prompts)
- Interact with file via the template repo:
    - If file is edited, the copier template repo should receive a task to edit the file along with the watchdog generated file diff. 
        - It should then go through jujutsu branch workflow loop to make the change and validate with tests, etc. 
        - Send summary back with results along with merge request from copier template repo.


## Goals:
- Make it easy to experiment.
- Aim to provide "bonus" functionality:
    - Additional background context hiding in the .devman/ directory is never a bad thing, storage is cheap. 
    - Being suprised by something good is a good thing, being suprised by something bad is a bad thing. 
- LLMs are good at summarization and combination. Lean into this with simple workflows that build context, not complex requests that provide answers. 
    - Simple requests can be run on local models. Local models should be thought of as free. Free is good.
- Build a knowledge graph:
    - Having "the way" of doing things is beneficial. 
    - Trying lots of things and having an LLM take notes and comb through logs of those trials is a good way to figure out "the way" over time.
    - Have dumb LLMs ask questions, workflows to search for resources, and smart LLMs to consolidate those resources into research and development guides. 
