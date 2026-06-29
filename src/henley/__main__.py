"""Enable ``python -m henley`` as an alias for the ``henley`` CLI.

Lets the tool run without the installed entry-point script — handy on a fresh
checkout where ``pip install -e .`` hasn't put ``henley`` on PATH (or the venv
isn't activated): ``PYTHONPATH=src python -m henley <cmd>``.
"""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
