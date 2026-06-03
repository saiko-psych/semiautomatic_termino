# Configuration file for the Sphinx documentation builder.
# https://www.sphinx-doc.org/en/master/usage/configuration.html
import os
import sys

# Make the project importable for autodoc.
sys.path.insert(0, os.path.abspath(".."))

project = "semiautomatic_termino"
copyright = "2026, saiko-psych"
author = "saiko-psych"
release = "2.0.0"

extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx_copybutton",
    "sphinx_autodoc_typehints",
]

# autosummary generates per-module stub pages at build time.
autosummary_generate = True
autodoc_default_options = {
    "members": True,
    "undoc-members": True,
    "show-inheritance": True,
}
# Start EMPTY. A grep of utils/ found no direct winreg/win32 imports, so all
# modules are expected to import on the Linux RTD builder. Add a module here
# ONLY if the first RTD build log shows it failing to import.
autodoc_mock_imports = []

napoleon_google_docstring = True
napoleon_numpy_docstring = True

myst_enable_extensions = ["colon_fence", "deflist"]

html_theme = "furo"
html_static_path = ["_static"]

# Treat the build as English.
language = "en"

# Keep planning/meta docs and loose, not-yet-integrated reference files out of
# the published site. The superpowers/ tree holds brainstorming specs + plans
# (they contain example toctree blocks that must not be parsed as real ones).
# The two loose .md files are source material folded into the new page tree.
exclude_patterns = [
    "_build",
    "Thumbs.db",
    ".DS_Store",
    "superpowers/**",
    "SERVER_VPN_SETUP.md",
    "UNIGRAZ_OPENCONNECT_ROADMAP.md",
]
