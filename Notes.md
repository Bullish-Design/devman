# Dev Environment:
A local first development environment standardization, with the goal of automating background work via specialized agents

Core pieces:
- Pydantree
    - Treesitter -> JSON -> Pydantic #-> JSON #-> Jinja -> Code 
- Templateer
    - The generator part for the Pydantree library
    - Pydantic + Jinja2 => Code
    - Custom File format type for IDE highlighting/parsing
    - Able to be wrapped up in a github repo and installed as a plugin for Parsedantic. 
- Parsedantic
    - Pydantree + Templateer
    - Round trip treesitter + graph based Parser/Generator Library
- Confidantic
    - Configuration library
    - Pydantic Based
    - Manages the /.config directory, reads/writes to/from pyproject.toml
- Testy
    - Testing Library
    - Parsedantic based
    - Tests each class with randomly generated objects
        - Use to dial in validation and error handling
    - Generates unit + integration test suites for each file, class, and function. 
    - Generates reports for all test runs. 
    - Generates github issue for all failing test runs, with appropriate context.
- Devman templating library 
    - Generates/manages the rest
- Nixos 
    - Repeatable, consistent environments, with fast containerization for local development
- Neovim (Local config, piped via devman from disk/github)
    - IDE/Interface
    - Will handle automating and UI for most functionality
    - Will start with UI and CodeCompanion, and look to make Python API for LSP using it. 
- Kitty
    - Handles visuals + automating testing of UI
    - Handles session management and "visual containerization" for workspaces/splits/etc.
- Tmux
    - Might add later for a persistent server instance


DevMan - The Voltron of developer tools:
- FileMan
    - File handling/Path Wrapper
- GitMan
    - Git/Github interaction and workflow scripting
- DocMan
    - Documentation, Guides, Changelog, etc
- ConMan/Confidantic
    - Configuration and settings
- Karen
    - Github Issues Handling
        - General error handling, too?
    - Partners with DocMan to gather context and fill out a template, then summarize before escalating to the developer/manager agent.

