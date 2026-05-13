# AIS MCP

MCP server for the STU Academic Information System (`is.stuba.sk`).

It exposes AIS data and actions to Claude, Codex, and other MCP-compatible
clients: schedule, grades, course progress, exams, mail, finance, documents,
submissions, thesis topics, and study metadata.

## Requirements

- Python 3.11+
- AIS/STU account

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Configuration

Copy the example environment file and fill in your AIS credentials:

```bash
cp .env.example .env
```

```dotenv
AIS_USERNAME=xlogin
AIS_PASSWORD=yourpassword
# Optional: skip auto-detect on first request
# AIS_DEFAULT_STUDIUM=192844
# AIS_DEFAULT_OBDOBI=706
```

The `.env` file is intentionally ignored by Git.

## Run

```bash
AIS_USERNAME=xlogin AIS_PASSWORD=yourpassword python -m ais_mcp
```

Installed console entry point:

```bash
ais-mcp
```

## Test

```bash
python -m pytest tests/ -v
```

## Versioning

Versions use SemVer-style `X.Y.Z` numbers and Git tags named `vX.Y.Z`.

```bash
python scripts/bump_version.py patch
python scripts/bump_version.py minor
python scripts/bump_version.py major
python scripts/bump_version.py 1.2.3
```

The script updates `pyproject.toml` and `src/ais_mcp/__init__.py`, creates a
commit, creates an annotated tag, and pushes both. Use `--no-push` to prepare
the release locally only.

## Project Structure

```text
src/ais_mcp/
  server.py      FastMCP server and tool registration
  session.py     AIS HTTP session, login, cookie cache
  context.py     active study/period detection
  parsers.py     BeautifulSoup parsing helpers
  tools/         MCP tools grouped by AIS area
tests/           parser tests
```

## Safety Notes

Some tools perform real write actions in AIS, including exam registration,
mail operations, file submissions, and sealed document requests. Read the tool
docstrings before exposing them to an MCP client.
