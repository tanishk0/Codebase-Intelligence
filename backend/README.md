# Codebase Copilot - Backend

High-performance codebase ingestion, parsing, and semantic AST chunking engine for Codebase Copilot.

## Architecture

- **`config.py`**: Pydantic-based configuration with file size caps, count limits, and extension ignore lists.
- **`ingestion/git_clone.py`**: Safe GitHub URL validation and shallow (`depth=1`) cloning to temporary workspaces.
- **`ingestion/loader.py`**: Fast recursive directory scanner filtering non-code, binaries, and oversized files.
- **`ingestion/chunker.py`**: Tree-sitter powered AST chunker supporting Python, JavaScript, TypeScript, and TSX with intelligent class/method/preamble extraction and sliding fallback for documentation and configs.
- **`tests/`**: Unit test suite covering URL validation, file discovery, AST chunking, and end-to-end repository ingestion.

## Setup & Running Tests

```bash
# Setup dependencies with uv
uv sync

# Run test suite
python -m unittest discover -s tests
```
