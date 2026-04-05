"""DeskLapse — Desktop Timelapse Application.

Entry point for the DeskLapse application. Initializes the
CustomTkinter GUI and starts the main event loop.

Usage:
    python -m src.main
    # or
    python src/main.py
"""

import sys
from pathlib import Path

# Ensure the project root is on the Python path so that
# 'src' package imports resolve correctly regardless of
# where the script is launched from.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ui.app_window import DeskLapseApp


def main() -> None:
    """Launch the DeskLapse application.

    Creates the main application window and enters the
    CustomTkinter event loop. The window runs until the
    user closes it.
    """
    app = DeskLapseApp()
    app.mainloop()


if __name__ == "__main__":
    main()
