# devman

devman is a small CLI for working with projects that contain a `.devman` directory. It locates the nearest `.devman` directory (optionally rooted at a configured projects directory) and runs `devenv` commands there.

## Installation

1. Ensure you have Python 3.11+ and `devenv` installed.
2. Clone this repository.
3. Install the project dependencies (for example, with `pip install -e .`).

## Configuration

Use `devman config --projects-root` to store a default projects root in `~/.config/devman/config.env`. This value is used by `devman run` to stop searching for `.devman` once it reaches that directory.

```bash
# Set the projects root directory
$ devman config --projects-root ~/projects

# Show the current configuration
$ devman config --show
```

## Usage

`devman run` finds the nearest `.devman` directory from your current working directory (or from the configured projects root) and executes `devenv` with any additional arguments.

```bash
# Run a devenv command from within the nearest .devman project
$ devman run up

# Show the installed version
$ devman version
```

## Available Commands

- `devman run [ARGS...]`: Run `devenv` with the provided arguments in the nearest `.devman` directory.
- `devman config --projects-root PATH`: Set the default projects root directory.
- `devman config --show`: Show the current configuration.
- `devman version`: Print the current devman version.
- `devman hello NAME`: Print a greeting.
