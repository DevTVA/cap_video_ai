"""Top-level main entry point.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.resolve()))

from batch_video_cutter.ui.cli import main_cli

if __name__ == "__main__":
    main_cli()
