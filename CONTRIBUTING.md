# Contributing

## Report bugs

Report bugs using this repository's GitHub Issues. Search existing issues first to avoid duplicates, then open an issue using the **Bug report** template.

Include a minimal reproducible example, the behavior you expected, what actually happened, and any relevant error messages or tracebacks. Provide your operating system, Python version, `q8s.runtime` version, and versions of any relevant integrations.

## Propose features and new ideas

Discuss new features in a GitHub issue before starting implementation. Search existing issues first, then open an issue using the **Feature or idea** template. Describe the problem or use case, your proposed solution, and any alternatives you have considered so maintainers and contributors can discuss the scope and approach.

## Development setup

Run the following commands from the root of your local `q8s-runtime` checkout. You will need Git and Python 3.10 or newer; optional integrations may require a newer Python version.

## Create a virtual environment

On macOS or Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

On Windows with PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Activate this environment whenever you open a new terminal to work on the project.

## Install in editable mode

Install the package and development tools into the active environment:

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[development]"
```

Editable mode makes changes under `src/` available without reinstalling the package. The `development` extra includes `pre-commit`, `pytest`, and `pytest-cov`.

For integration development and the test suite, install the additional dependencies:

```bash
python -m pip install -e ".[development,test,qiskit,qrisp,ucc,matplotlib]"
```

The extras are defined in [pyproject.toml](pyproject.toml). You can select only the integrations needed for your work when running a subset of the tests.

## Configure pre-commit

Install the repository's Git hooks:

```bash
pre-commit install
```

Check all existing files once after setup:

```bash
pre-commit run --all-files
```

The first run downloads and prepares the hook environments, so it requires network access and can take longer. Hooks are configured in [.pre-commit-config.yaml](.pre-commit-config.yaml) and include formatting, import sorting, linting, file checks, and Python license headers.

The hooks run automatically on staged files when you commit. If a hook modifies files, review and stage those changes, then retry the commit. Run `pre-commit run --all-files` before submitting changes.

## Run tests

With the test and integration dependencies installed:

```bash
python -m pytest
```

To run a specific test file:

```bash
python -m pytest tests/test_qiskit_utils.py
```

When you finish working, leave the virtual environment with `deactivate`.
