"""Console-script entry point for recon-pipeline.

The interactive shell lives in ``pipeline/recon-pipeline.py``.  That filename
contains a hyphen, so it cannot be imported with a normal ``import``
statement; we load it via :func:`importlib.import_module` (the same approach
the test-suite uses) and hand off to its ``main`` with ``name="__main__"`` so
the shell starts.
"""

import importlib


def main():
    """Launch the recon-pipeline interactive shell."""
    module = importlib.import_module("pipeline.recon-pipeline")
    module.main(name="__main__")


if __name__ == "__main__":
    main()
