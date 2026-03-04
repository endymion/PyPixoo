"""Sphinx configuration for PyPixoo."""

from __future__ import annotations

import os
import sys
from datetime import datetime

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

project = "PyPixoo"
author = "PyPixoo contributors"
current_year = datetime.now().year
copyright = f"{current_year}, {author}"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.autosectionlabel",
    "sphinx.ext.intersphinx",
]

autosectionlabel_prefix_document = True

napoleon_google_docstring = False
napoleon_numpy_docstring = True

autodoc_typehints = "description"
autodoc_member_order = "bysource"

autodoc_mock_imports = [
    "playwright",
]

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
}

html_theme = "furo"
html_title = "PyPixoo Documentation"

exclude_patterns = ["_build"]
