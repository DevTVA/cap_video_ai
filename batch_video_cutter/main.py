"""Main entry point for Batch Video Cutter.
"""

import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.resolve()))

from ui.cli import main_cli

if __name__ == "__main__":
    main_cli()
