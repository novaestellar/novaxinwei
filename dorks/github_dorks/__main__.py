import os
import sys

# Make the dorks/ directory importable no matter where this is invoked from
# (repo root, dorks/ itself, or as a direct script path). Without this the
# ``from github_dorks.cli import main`` below raises ModuleNotFoundError when
# launched as ``python -m dorks.github_dorks`` or ``python dorks/.../__main__.py``.
_DORKS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _DORKS_DIR not in sys.path:
    sys.path.insert(0, _DORKS_DIR)

from github_dorks.cli import main


if __name__ == '__main__':
    main()