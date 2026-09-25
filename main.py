"""Process entry point for the line control service."""

import sys

from linecontrol.cli import main


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
