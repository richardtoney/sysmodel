# Contributing

Thank you for your interest in contributing to sysmodel!

## Development Setup

```bash
git clone https://github.com/richardtoney/sysmodel.git
cd sysmodel
pip install -e ".[graph,dev]"
pre-commit install
```

## Running Tests

```bash
pytest
```

## Code Style

This project uses `ruff` for linting and formatting, and `mypy` for type checking.

```bash
ruff check sysmodel/ tests/
mypy sysmodel/
```

## Submitting Changes

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Ensure all tests pass and coverage stays above 90%
5. Submit a pull request
