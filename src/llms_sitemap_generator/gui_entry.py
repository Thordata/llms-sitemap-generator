"""
GUI Entry Point for PyInstaller
This script uses absolute imports to avoid relative import issues in .exe builds

When running as .exe, PyInstaller sets sys.frozen=True and sys._MEIPASS to the temp directory.
We need to handle both normal execution and PyInstaller execution.
"""

import sys
import os
from pathlib import Path

# Handle PyInstaller bundled execution
if getattr(sys, 'frozen', False):
    # Running as compiled .exe
    # PyInstaller creates a temp folder and stores path in _MEIPASS
    base_path = Path(sys._MEIPASS)
    # Add the bundled package path
    if str(base_path) not in sys.path:
        sys.path.insert(0, str(base_path))
else:
    # Running as normal Python script
    # Add src directory to path so we can use absolute imports
    project_root = Path(__file__).parent.parent.parent
    src_path = project_root / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))

# Now we can import using absolute imports
try:
    from llms_sitemap_generator.gui_main import main
except ImportError as e:
    # Fallback: try relative import if absolute fails
    try:
        from .gui_main import main
    except ImportError:
        print(f"[ERROR] Failed to import gui_main: {e}")
        print(f"Python path: {sys.path}")
        raise

if __name__ == "__main__":
    sys.exit(main())
