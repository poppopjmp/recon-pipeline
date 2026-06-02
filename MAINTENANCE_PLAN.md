# recon-pipeline — Maintenance Revival Plan

**Status of this document:** executed — see the Progress section below.
**Repository:** `poppopjmp/recon-pipeline` (a fork of `epi052/recon-pipeline`).
**Prepared:** 2026-06.

---

## Progress (executed)

The revival described below has been carried out on the
`claude/project-maintenance-plan-uX4gp` branch:

- **P0 Triage** — ✅ Target stack chosen (Python ≥3.10; luigi 3.x, cmd2 2.x,
  SQLAlchemy 1.4) and breakage reproduced.
- **P1 Modern-Python install** — ✅ Code migrated; installs cleanly via
  `pip install -e .[dev]` on Python 3.10–3.13. **Full mocked suite: 233 passed,
  1 skipped.**
- **P2 CI & tooling** — ✅ Workflow rewritten (checkout@v4/setup-python@v5,
  3.10–3.13 matrix, installs from pyproject, flake8 + black gates); live
  tool-install tests split into a scheduled workflow; pre-commit fixed; black 24
  applied.
- **P3 Docker** — ✅ Rebuilt on `python:3.12-slim`; install-from-pyproject step
  verified (Docker daemon unavailable here for a full image build).
- **P4 Rebrand & docs** — ✅ README badges/URLs, CONTRIBUTING, PR template, and
  docs updated; broken design-doc images fixed; `.readthedocs.yml` added.
- **P5 Tool installers** — ✅ `go get`→`go install …@latest` for the Go-based
  tools (Go 1.17+ removed `go get` for binaries). ⚠️ Residual follow-ups
  (require a live Go toolchain + network to verify, hence the scheduled
  tool-installs workflow):
  - **amass**: deliberately left on v3 — `AmassScan.run()` and
    `ParseAmassOutput` are written against amass v3's CLI flags and JSON
    schema. A move to v4 must update the installer, the run() flags, and the
    parser together and be verified end-to-end against a real v4 binary.
  - **subjack/tko-subs**: their data files (fingerprints.json /
    providers-data.csv) were read from `$GOPATH/src`, which `go install` no
    longer populates; those runtime paths need revisiting.
- **P6 Release & automation** — ✅ PEP 621 packaging + console entry point,
  CHANGELOG, SECURITY.md, and Dependabot added. Tagging `v1.0.0` and enabling
  branch protection remain for the maintainer.

---

## 1. Executive summary

`recon-pipeline` is an automated reconnaissance pipeline built on
[Luigi](https://github.com/spotify/luigi) (task orchestration),
[cmd2](https://github.com/python-cmd2/cmd2) (interactive shell), and
SQLAlchemy (result storage). It wraps external recon tools (amass, masscan,
nmap, gobuster, aquatone, webanalyze, subjack, tko-subs, waybackurls,
searchsploit) into a resumable, scheduler-driven workflow.

The codebase itself is reasonably well structured (~14k LOC in `pipeline/`,
~2k LOC of tests, docs in `docs/`). The problem is **bit-rot in everything
around the code**: the dependency stack no longer installs on a supported
Python, the container image cannot build, CI uses long-deprecated actions and
a non-reproducible install path, the developer tooling (pre-commit) is broken,
and the fork was never rebranded away from upstream. The only recent activity
is automated Snyk security bumps — some of which made things *worse* (e.g. the
Dockerfile).

This plan sequences the work to get the project **installable, testable, and
releasable again on modern Python**, then to keep it that way.

---

## 2. Findings (current state)

### 2.1 Blocking / correctness issues

| # | Area | Problem | Evidence |
|---|------|---------|----------|
| B1 | Dependencies | `Pipfile` pins `luigi==2.8.12` (2019), `cmd2==1.0.1`, `sqlalchemy==1.3.15`, `pytest==5.4.1`, `black==19.10b0`, `flake8==3.7.9`. This stack **fails to install on Python 3.11** (sqlalchemy 1.3.15 fails to build a wheel). `pipenv install` is broken on any current interpreter. | `Pipfile`; verified locally |
| B2 | Python version | Project targets **Python 3.7** (Pipfile, README badge, every CI job). Python 3.7 has been **end-of-life since June 2023**. | `Pipfile`, `.github/workflows/pythonapp.yml`, `README.md` |
| B3 | Dependency drift | `Pipfile` says `luigi==2.8.12`; `docs/requirements.txt` says `luigi==3.6.0`. Luigi 2→3 is a **breaking** major version. Two conflicting sources of truth; unclear which the code actually targets. | `Pipfile` vs `docs/requirements.txt` |
| B4 | Docker | `Dockerfile` uses `FROM python:3.14.0a2-alpine3.19` (a Python **alpha** on Alpine) but then runs `apt update && apt install …`. Alpine has no `apt` (it uses `apk`). **The image cannot build.** Introduced by merged Snyk auto-PRs. | `Dockerfile` |
| B5 | CI | Uses `actions/checkout@v1` and `actions/setup-python@v1` (both from 2019, deprecated). Installs deps ad-hoc and **unpinned** (`pipenv install pytest cmd2 luigi …`) instead of from a lockfile → non-reproducible builds. One job installs real tools over the network (`test-unmocked-tool-installs`) → slow and flaky. | `.github/workflows/pythonapp.yml` |
| B6 | pre-commit | Hooks reference `repo: https://github.com/ambv/black` with `rev: stable` (the `stable` tag was removed years ago; black moved to `psf/black`) and `gitlab.com/pycqa/flake8` (moved to GitHub). `pre-commit run` is broken out of the box. | `.pre-commit-config.yaml` |

### 2.2 Maintainability / project-health issues

| # | Area | Problem |
|---|------|---------|
| M1 | Branding | The fork was never rebranded. `README.md`, `CONTRIBUTING.md`, the PR template, `docs/`, and even some source/tests still say `git clone https://github.com/epi052/…`, link to upstream's readthedocs, and point bug reports to upstream's issue tracker. |
| M2 | Packaging | No installable packaging — no `setup.py`/`setup.cfg`/PEP 621 `[project]` metadata (`pyproject.toml` only carries `black` config). The tool is run as a loose script and is not `pip install`-able. |
| M3 | Releases | No GitHub releases exist, yet the README shows a "latest release" badge. No changelog. |
| M4 | Automation gaps | No Dependabot config, no `.readthedocs.yml`. The only dependency automation is Snyk, which has merged questionable changes (see B4) without review. |
| M5 | README badges/links | Build badge uses the deprecated `github/workflow/status` shield API and a workflow name that no longer matches; coverage is a hard-coded `97%`; Python badge says 3.7. |
| M6 | Docs | `docs/overview/design.rst` references `architecture_diagram.png` and `data_flow_diagram.png`, neither of which exists in `docs/img/`. Sphinx pins (`sphinx==3.0.0`) are very old. |
| M7 | External tool installers | The per-tool YAML installers rot as upstreams move. E.g. `amass.yaml` installs `github.com/OWASP/Amass/v3/...@master` — Amass is now **v4** under `owasp-amass/amass`; the v3 path likely no longer resolves. `go.yaml` downloads Go tarballs from a host that has already required a fix once (`Update go download host`). |
| M8 | Test strategy | Tests are pinned to Python 3.7 + old Luigi; the unmocked tool-install job depends on live network + third-party hosts. No coverage reporting wired into CI despite the README badge. |

---

## 3. Goals & non-goals

**Goals**
- The project installs cleanly on **currently-supported Python** (3.10–3.13) with a single, reproducible command.
- One authoritative dependency definition; locked and CI-enforced.
- Green CI on modern GitHub Actions, reproducible from the lockfile.
- A buildable container image.
- Correct fork branding and working contributor onboarding.
- A tagged release + changelog so users have a known-good baseline.
- Automation (Dependabot) so dependency drift is caught early — with human review.

**Non-goals (for the revival phase)**
- New scanning features or new tool integrations.
- Rewriting the architecture (Luigi/cmd2/SQLAlchemy stay).
- Supporting non-Linux hosts (the tooling is Linux-centric by design).

---

## 4. Phased plan

Each phase is independently shippable. Recommended order top-to-bottom;
P0 and P1 are the critical path to "usable again."

### Phase 0 — Triage & baseline (½–1 day)

Goal: know exactly what works today before changing anything.

1. **Pick the target stack.** Decide Luigi 3.x (recommended — Luigi 2.x is
   Python-2-era and unmaintained) and a supported Python floor (recommend
   **3.10**). Record the decision in this doc / an ADR.
2. **Reproduce the breakage.** Confirm `pipenv install` failure and capture the
   error (done: sqlalchemy 1.3.15 won't build on 3.11).
3. **Inventory actual imports & API usage** to scope the Luigi 2→3 and
   SQLAlchemy 1.3→2.0 / cmd2 1.0→2.x migrations (search for deprecated call
   sites: `luigi.Parameter` signatures, `Task.requires`, SQLAlchemy
   `Query`/`session` patterns, cmd2 `do_*`/`argparse` decorators).
4. **Snyk hygiene:** close/raze the open Snyk PRs (#6, #7) that touch only
   `docs/requirements.txt`; they'll be superseded by the dependency rework.
   Audit previously-merged Snyk PRs for damage (the Dockerfile is one).

**Deliverable:** a short migration scope note + decision on Python floor and
Luigi/SQLAlchemy/cmd2 target versions.

---

### Phase 1 — Make it install & run on modern Python (2–5 days, critical path)

Goal: `pip install -e .` (or `pipenv install`) succeeds on Python 3.10+ and the
shell starts.

1. **Consolidate dependency management.** Choose **one** of:
   - PEP 621 `pyproject.toml` with `[project.dependencies]` + a lock
     (`uv`/`pip-tools`), **or**
   - keep `pipenv` but regenerate `Pipfile`/`Pipfile.lock` from scratch.

   Recommendation: migrate to `pyproject.toml` (PEP 621) — it also solves
   packaging (M2) and lets us drop the Pipfile/`docs/requirements.txt` split
   (B3). Use `uv` or `pip-tools` for a committed lockfile.
2. **Bump core deps to current, compatible versions:**
   - `luigi` → 3.x
   - `cmd2` → 2.x (note: cmd2 2.x changed several APIs vs 1.0)
   - `SQLAlchemy` → 2.0 (or pin 1.4 as an intermediate step if 2.0 is too large)
   - `python-libnmap`, `PyYAML` → current
3. **Fix code for the upgraded APIs.** Expect changes in:
   - Luigi task/parameter API and the central scheduler invocation.
   - SQLAlchemy session/query API (`Query.get` → `Session.get`, `declarative_base`
     import path, etc.) across `pipeline/models/`.
   - cmd2 command/argparse decorators and output helpers in
     `pipeline/recon-pipeline.py`.
4. **Set the supported Python floor** in packaging metadata
   (`requires-python = ">=3.10"`).
5. **Smoke test:** launch the shell, run `tools`, `database`, and `view`
   subcommands; confirm `--local-scheduler` scan dry-runs.

**Deliverable:** clean install on 3.10–3.13; shell boots; unit tests collected.

---

### Phase 2 — Restore CI & developer tooling (1–2 days)

Goal: green, reproducible CI on a matrix of supported Pythons.

1. **Rewrite `.github/workflows/pythonapp.yml`:**
   - `actions/checkout@v4`, `actions/setup-python@v5`.
   - Python matrix: `["3.10", "3.11", "3.12", "3.13"]`.
   - Install **from the lockfile** (not ad-hoc `pipenv install pkg pkg`).
   - Add pip/uv caching.
   - Run lint (`flake8`/`ruff`), format check (`black`/`ruff format`), and the
     mocked test suites (`test_shell`, `test_recon`, `test_web`, `test_models`,
     `test_tools_install`).
   - Move `test-unmocked-tool-installs` (live network) to a **separate,
     manually/scheduled-triggered** workflow so PR CI isn't flaky.
   - Upload coverage and replace the hard-coded README badge.
2. **Fix `.pre-commit-config.yaml`:** point black at `psf/black` with a real
   pinned `rev`, flake8 at its GitHub mirror (or migrate the whole lot to
   **ruff** for lint+format in one hook), and refresh `pre-commit-hooks` rev.
   Consider replacing flake8+black with `ruff` to cut config surface.
3. **Add a `Makefile`/`tox`/`nox`** (or document `uv run …`) so contributors run
   the same commands locally as CI.

**Deliverable:** PR CI green on the Python matrix, reproducible from lock,
pre-commit working.

---

### Phase 3 — Fix the container image (½–1 day)

Goal: `docker build` succeeds and the container runs `luigid` + the shell.

1. Rewrite the `Dockerfile` to a **consistent, stable base** — either
   `python:3.12-slim` (Debian, use `apt`) or `python:3.12-alpine` (use `apk`).
   Drop the Python 3.14 **alpha**.
2. Install OS deps with the package manager that matches the base
   (`apt-get`/`apk`).
3. Install the project from the committed lockfile (`--deploy` semantics).
4. Re-verify the workarounds (`systemctl` stub, `luigid` relocation, the
   `config.py` `tun0→eth0` sed) still apply on the new base.
5. Add a CI job (or reuse the scheduled workflow) that builds the image.

**Deliverable:** a buildable, documented image; README Docker steps verified.

---

### Phase 4 — Rebrand the fork & fix docs (1–2 days)

Goal: docs, README, and contributor flow reflect `poppopjmp/recon-pipeline`.

1. **README:** replace `epi052` clone URLs with this repo; fix/replace badges
   (build, coverage, Python version); update readthedocs links (or remove if
   not republishing); correct the "Found a bug?" section to this issue tracker.
2. **CONTRIBUTING.md, PR template, issue templates:** update repo URLs and any
   upstream-specific instructions.
3. **Docs:** either add the missing `architecture_diagram.png` /
   `data_flow_diagram.png` referenced by `design.rst`, or remove the
   references; bump Sphinx pins; add a `.readthedocs.yml` if docs are to be
   hosted.
4. Keep clear **attribution to upstream `epi052`** (license + credits) — this is
   a fork, not a takeover.

**Deliverable:** consistent branding; docs build without missing-asset warnings.

---

### Phase 5 — Refresh external tool installers (1–3 days, ongoing)

Goal: `tools install all` works against today's upstreams.

1. Audit every YAML in `pipeline/tools/` against the current upstream:
   - `amass.yaml`: migrate `OWASP/Amass/v3@master` → `owasp-amass/amass/v4`
     (or pin a known-good release).
   - `go.yaml`: pin/verify the Go download host and version logic.
   - Re-verify `gobuster`, `aquatone`, `webanalyze`, `subjack`, `tko-subs`,
     `waybackurls`, `searchsploit`, `seclists`, `recursive-gobuster`.
2. Pin tool versions where feasible instead of `@master` for reproducibility.
3. Run the (now isolated) unmocked-install workflow to validate end-to-end.

**Deliverable:** installer YAMLs that resolve against current upstreams.

---

### Phase 6 — Release & ongoing maintenance (½ day + recurring)

Goal: a known-good baseline and a process to stay current.

1. **Packaging:** finalize PEP 621 metadata, add a console-script entry point
   (`recon-pipeline = …`) so it's `pip install`-able and on `PATH`.
2. **Changelog:** add `CHANGELOG.md`; tag the first revival release (e.g.
   `v1.0.0` for the fork, documenting the modern-Python baseline).
3. **Dependabot:** add `.github/dependabot.yml` for `pip` + `github-actions`
   ecosystems (weekly), so drift is surfaced as reviewable PRs — and reduce
   reliance on unreviewed Snyk auto-merges.
4. **Branch protection / review:** require CI green + review before merge so a
   bot can't reintroduce a broken Dockerfile.
5. **SECURITY.md / support policy:** state supported Python versions and how to
   report issues.

**Deliverable:** tagged release, changelog, dependency automation, guardrails.

---

## 5. Suggested sequencing & effort

| Phase | Outcome | Rough effort | Priority |
|-------|---------|--------------|----------|
| P0 Triage | Migration scope & decisions | ½–1 day | Must |
| P1 Modern Python install | Installs & runs on 3.10+ | 2–5 days | Must (critical path) |
| P2 CI & tooling | Green, reproducible CI | 1–2 days | Must |
| P3 Docker | Buildable image | ½–1 day | Should |
| P4 Rebrand & docs | Correct fork identity | 1–2 days | Should |
| P5 Tool installers | `tools install` works | 1–3 days | Should (ongoing) |
| P6 Release & automation | Baseline + guardrails | ½ day + recurring | Must (after P1–P2) |

Total for a usable, releasable baseline (P0–P2 + P6): **~1–1.5 weeks**.
Full revival including Docker, docs, and installers: **~2–3 weeks**.

---

## 6. Risks & mitigations

- **Luigi 2→3 / SQLAlchemy 1.3→2.0 / cmd2 1→2 breaking changes.** Largest
  uncertainty. Mitigate by upgrading one dependency at a time, leaning on the
  existing test suite, and pinning intermediate versions (e.g. SQLAlchemy 1.4)
  if a direct jump is too large.
- **External tool drift is unbounded.** Upstream recon tools move and break
  installers independently of this repo. Mitigate by pinning versions and
  isolating the live-install tests from PR CI.
- **Bot-introduced regressions.** Snyk has already merged a broken Dockerfile.
  Mitigate with branch protection + required review (P6).
- **Test fragility on the live-install path.** Keep it out of the PR gate; run
  on a schedule.

---

## 7. Quick wins (can land immediately, low risk)

- Close the stale Snyk PRs (#6, #7) and revert the broken Alpine+apt Dockerfile.
- Bump CI actions to `checkout@v4` / `setup-python@v5`.
- Fix `.pre-commit-config.yaml` repo URLs/revs (or switch to ruff).
- Replace `epi052` clone URLs in the README with this fork.
- Add `.github/dependabot.yml`.

These are cheap, reversible, and unblock contributor onboarding while the
larger P1 migration proceeds.
