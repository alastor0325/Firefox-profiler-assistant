# Firefox Profiler Assistant

An AI-powered command-line tool to analyze performance profiles from the Firefox Profiler. This tool can download a profile directly from a `share.firefox.dev` URL or load a local file, parse the complex JSON structure, and prepare it for advanced analysis.

## Features

- **Direct Download**: Fetches profiles directly from `share.firefox.dev` URLs.
- **Local File Analysis**: Analyzes `profile.json` files from your local disk.
- **High-Performance Parsing**: Uses `orjson` and `pandas` to efficiently handle and structure multi-megabyte profile files.
- **Structured Data Access**: Converts the profile's relational format into accessible Pandas DataFrames.

## Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-username/firefox-profiler-assistant.git
    cd firefox-profiler-assistant
    ```

2.  **Install dependencies:**
    It is recommended to use a virtual environment.
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    pip install .
    ```

## Usage

The tool provides a single entry point for analyzing profiles from either a URL or a local file path.

```bash
profiler-analysis <PROFILE_SOURCE>
```

`<PROFILE_SOURCE>` can be either:
- A `share.firefox.dev` URL (e.g., `https://share.firefox.dev/3HkKTjj`)
- A path to a local `profile.json` file (e.g., `./profile.json`)

### Example: Analyzing from a URL

```bash
profiler-analysis https://share.firefox.dev/3HkKTjj
```

The tool will first download the profile into a temporary file and then proceed with the analysis.

### Example: Analyzing a Local File

```bash
profiler-analysis /path/to/your/profile.json
```

## Development

To set up the development environment, including test dependencies, run:

```bash
pip install -e ".[test]"
```
> **Note**: If you encounter an error about "editable mode" and `pyproject.toml`, your version of `pip` may be outdated. Please upgrade it first by running `python -m pip install --upgrade pip` and then try the installation command again.


### Running Tests

The project uses `pytest` for testing. To run the full test suite:

```bash
pytest
```

## CI/CD

This project uses GitHub Actions to automatically run tests on every push and pull request to the `main` branch. This ensures code quality and prevents regressions. The workflow is defined in `.github/workflows/python-app.yml`.