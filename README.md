# jupyterlab_sympy_assistant

SymPy helper sidebar and equation library for JupyterLab notebooks.

This extension is composed of a Python package named `jupyterlab_sympy_assistant`
for the server extension and a NPM package named `jupyterlab-sympy-assistant`
for the frontend extension.

## What It Adds

- A **Notebook toolbar icon** (function glyph) to open a left sidebar panel.
- A **sidebar equation library** with rendered math preview (KaTeX) and stored SymPy text.
- An **Add/Edit modal** for equation metadata (`name`, `sympy`, `latex`, `description`, `tags`).
- An **Insert from LaTeX** flow using the Physics Derivation Pad AST parser and SymPy output.
- **Insert action** to place SymPy notation into the active notebook cell.
- A lightweight **server extension** that persists equations to a JSON file.

## Requirements

- JupyterLab >= 4.0.0
- A sibling checkout of
  [physics-derivation-pad](https://github.com/reubengann/physics-derivation-pad)
  when building from source. The frontend currently resolves
  `@physics-derivation-pad/core` from `../physics-derivation-pad`.

The Physics Derivation Pad dependency is compiled into the built JupyterLab
extension. Users installing a prebuilt wheel do not need its repository, but
source and editable installs do.

## Installation

```bash
pip install jupyterlab_sympy_assistant
```

### Equation Library Storage

Equation records are saved in a user-local JSON file:

- `<jupyter_data_dir>/jupyterlab-sympy-assistant/equation-library.json`

The file includes a `schema_version` and an `equations` array to support future migration
to another storage backend (such as SQLite) without changing the frontend API.

### Development install

Note: You will need NodeJS to build the extension package.

The `jlpm` command is JupyterLab's pinned version of
[yarn](https://yarnpkg.com/) that is installed with JupyterLab.

Before installing this extension, place both repositories under the same parent
directory and build the Physics Derivation Pad core package:

```bash
cd ../physics-derivation-pad
npm install
npm run build:core
cd ../jupyterlab-sympy-assistant
```

> **Builder compatibility note:** This repository was generated from the
> JupyterLab extension template v4.5.2 and currently uses the corresponding
> `@jupyterlab/builder` and `jupyter labextension` workflow. JupyterLab 4.6 is
> transitioning extensions to the standalone `jupyter-builder` Python package
> and `@jupyter/builder` npm package; see
> [jupyter-builder issue #81](https://github.com/jupyterlab/jupyter-builder/issues/81).
> Do not replace only the npm builder dependency in this repository. On Windows,
> `jupyter-builder watch` can currently generate an invalid `_build.load` value
> of `"static"`, causing JupyterLab to request the static directory and receive a
> 404. Continue to use `jlpm build` and `jlpm watch` until the repository is
> updated from the Copier template and the Python requirements, npm dependency,
> and build scripts can be migrated together.

```bash
# Clone the repo to your local environment
# Change directory to the jupyterlab_sympy_assistant directory

# Set up a virtual environment and install package in development mode
python -m venv .venv
source .venv/bin/activate
pip install --editable ".[dev,test]"

# Link your development version of the extension with JupyterLab
jupyter labextension develop . --overwrite
# Server extension must be manually installed in develop mode
jupyter server extension enable jupyterlab_sympy_assistant

# Rebuild extension Typescript source after making changes
# IMPORTANT: Unlike the steps above which are performed only once, do this step
# every time you make a change.
jlpm build
```

If `jlpm` is not directly on your shell `PATH`, you can invoke it through Python:

```bash
python -m jupyterlab.jlpmapp run build
```

You can watch the source directory and run JupyterLab at the same time in different terminals to watch for changes in the extension's source and automatically rebuild the extension.

```bash
# Watch the source directory in one terminal, automatically rebuilding when needed
jlpm watch
# Run JupyterLab in another terminal
jupyter lab
```

With the watch command running, every saved change will immediately be built locally and available in your running JupyterLab. Refresh JupyterLab to load the change in your browser (you may need to wait several seconds for the extension to be rebuilt).

By default, the `jlpm build` command generates the source maps for this extension to make it easier to debug using the browser dev tools. To also generate source maps for the JupyterLab core extensions, you can run the following command:

```bash
jupyter lab build --minimize=False
```

### Development uninstall

```bash
# Server extension must be manually disabled in develop mode
jupyter server extension disable jupyterlab_sympy_assistant
pip uninstall jupyterlab_sympy_assistant
```

In development mode, you will also need to remove the symlink created by `jupyter labextension develop`
command. To find its location, you can run `jupyter labextension list` to figure out where the `labextensions`
folder is located. Then you can remove the symlink named `jupyterlab-sympy-assistant` within that folder.

### Testing the extension

#### Server tests

This extension is using [Pytest](https://docs.pytest.org/) for Python code testing.

Install test dependencies (needed only once):

```sh
pip install -e ".[test]"
# Each time you install the Python package, you need to restore the front-end extension link
jupyter labextension develop . --overwrite
```

To execute them, run:

```sh
pytest -vv -r ap --cov jupyterlab_sympy_assistant
```


#### Frontend tests

This extension is using [Jest](https://jestjs.io/) for JavaScript code testing.

To execute them, execute:

```sh
jlpm
jlpm test
```

#### Integration tests

This extension uses [Playwright](https://playwright.dev/docs/intro) for the integration tests (aka user level tests).
More precisely, the JupyterLab helper [Galata](https://github.com/jupyterlab/jupyterlab/tree/master/galata) is used to handle testing the extension in JupyterLab.

More information are provided within the [ui-tests](./ui-tests/README.md) README.

### Packaging the extension

See [RELEASE](RELEASE.md)
