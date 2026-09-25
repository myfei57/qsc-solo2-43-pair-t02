"""Module entry point for ``python -m linecontrol``."""

import sys

from .cli import main


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
