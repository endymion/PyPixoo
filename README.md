# PyPixoo

> The Pixoo library you can trust — BDD-first, well-tested.

A Python library for the Divoom Pixoo 64 display, driven by Gherkin specs.

## Requirements

- Python 3.10+
- A Divoom Pixoo 64 on your network
- `PIXOO_IP` environment variable set to the device IP (e.g. `192.168.0.37`)

## Installation

```bash
cd PyPixoo
pip install -e ".[dev]"
```

## Run specs

```bash
behave
```

Specs require a real Pixoo device. Set `PIXOO_IP` before running:

```bash
export PIXOO_IP=192.168.0.37
behave
```

## Usage

```python
from pypixoo import Pixoo

pixoo = Pixoo("192.168.0.37")
pixoo.connect()
pixoo.fill(255, 0, 68)
pixoo.push()
```
