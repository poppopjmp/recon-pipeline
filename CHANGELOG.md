# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-06-02

First release of the maintained `poppopjmp` fork. This release revives the
project on modern Python and current dependencies; the original tool was built
for Python 3.7 and a 2019-era dependency stack that no longer installs.

### Changed
- **Supported Python is now 3.10+** (previously 3.7, EOL since June 2023).
  CI runs a 3.10–3.13 matrix.
- **Dependencies modernized:** luigi 3.x, cmd2 2.x, SQLAlchemy 1.4. SQLAlchemy
  is pinned to the 1.4 series because `luigi.contrib.sqla` is not yet
  compatible with SQLAlchemy 2.0.
- **Packaging:** added PEP 621 `pyproject.toml`, made it the authoritative
  dependency definition, and added a `recon-pipeline` console entry point. The
  `Pipfile` is kept in sync for pipenv users; the stale `Pipfile.lock` was
  removed.
- **CI:** rewritten on `actions/checkout@v4` / `actions/setup-python@v5`,
  installs from `pyproject.toml`, and runs flake8 + black. The slow,
  network-dependent tool-install tests moved to a separate scheduled workflow.
- **Docker:** rebuilt on `python:3.12-slim` (the previous image used a Python
  alpha on Alpine yet called `apt`, so it could not build).
- **Tooling:** fixed the broken pre-commit config (psf/black, pycqa/flake8 with
  pinned revs) and reformatted the codebase with black 24.

### Fixed
- Replaced the removed `cmd2.ansi.style` with a self-contained styling helper.
- Migrated off removed SQLAlchemy APIs (`relation`, the old `declarative_base`
  import path).
- Updated cmd2 argparse usage (`choices_provider`/`completer`) and the parsed
  statement access (`cmd2_statement`).
- Stored parser handler names as strings so cmd2's per-invocation parser
  deepcopy no longer drags the shell (and its file handles) through
  `copy.deepcopy`, which had broken the `database`, `tools`, and `view`
  commands.

[1.0.0]: https://github.com/poppopjmp/recon-pipeline/releases/tag/v1.0.0
