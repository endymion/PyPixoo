# PyPixoo — Agent Guide


## Project management with Kanbus

Use Kanbus for task management.
Why: Kanbus task management is MANDATORY here; every task must live in Kanbus.
When: Create/update the Kanbus task before coding; close it only after the change lands.
How: See CONTRIBUTING_AGENT.md for the Kanbus workflow, hierarchy, status rules, priorities, command examples, and the sins to avoid. Never inspect project/ or issue JSON directly (including with cat or jq); use Kanbus commands only.
Performance: Prefer kbs (Rust) when available; kanbus (Python) is equivalent but slower.
Warning: Editing project/ directly is a sin against The Way. Do not read or write anything in project/; work only through Kanbus.

This document helps AI agents (and humans) work effectively on PyPixoo.

## Project Overview

PyPixoo is a BDD-first Python library for the Divoom Pixoo 64 display. It is a reimplementation inspired by the [pixoo](https://github.com/SomethingWithComputers/pixoo) project, with Gherkin specs driving implementation and real-device integration tests.

## Key Principles

1. **BDD-first:** Write Gherkin specs before implementation. Run `behave`, see failures, implement until green.
2. **Real device required:** Specs run against an actual Pixoo 64 on the network. No mock in v1.
3. **Minimal API:** Connect, draw primitives (fill, text, shapes), push to screen.

## Project Structure

```
PyPixoo/
  features/              # Gherkin specs
    display.feature
    steps/
      display_steps.py   # Behave step implementations
    environment.py       # Behave hooks
  src/pypixoo/           # Library
    __init__.py
    pixoo.py             # Pixoo client (connect, fill, push)
  pyproject.toml
  PR_FAQ.md              # RFC-style project rationale
  README.md
```

## Workflow

1. Add or edit scenarios in `features/*.feature`
2. Run `behave` — expect undefined or failing steps
3. Implement steps in `features/steps/` and library code in `src/pypixoo/`
4. Reference the original pixoo project for HTTP API semantics (e.g. `Draw/SendHttpGif`, `Channel/GetAllConf`)

## Commands

- **Run specs:** `behave`
- **Install:** `pip install -e ".[dev]"`
- **Device IP:** Specs use hardcoded IP in feature file (e.g. `192.168.0.37`). Edit the feature if the device IP differs.

## API Reference (Current)

```python
from pypixoo import Pixoo

pixoo = Pixoo("192.168.0.37")
pixoo.connect()          # Returns bool, loads GIF counter
pixoo.fill(r, g, b)      # Fill buffer with RGB
pixoo.push()             # Send buffer to device
```
