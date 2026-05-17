# Changelog

All notable changes to this project will be documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
This project follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] - YYYY-MM-DD

### Added
- Core models: Block, Relationship, Flow, StateMachine, System
- Metadata schema registry with required/allowed key validation
- Python query helpers: 20 functions across 5 query categories
- Kuzu graph integration (optional) with Cypher query runner
- Textual TUI with 6 query tabs and free-form Cypher input
- Registry extension API: register_schema(), get_schema()
- Serialization: System.to_dict(), from_dict(), to_json(), from_json()
- Typed exception hierarchy under SysmodelError
- Full test suite with >=90% coverage
- MkDocs documentation site
- GitHub Actions CI pipeline with lint, test, docs, and publish stages
