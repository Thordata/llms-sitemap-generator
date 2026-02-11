"""
Build Windows executable (.exe) for GUI tool using PyInstaller

Usage:
    python build_exe.py

Requirements:
    pip install pyinstaller PyQt5 requests PyYAML

Output:
    dist/llms-sitemap-generator-gui.exe
"""

import PyInstaller.__main__
import sys
import os
from pathlib import Path


def build_exe():
    """Build GUI tool as .exe"""
    project_root = Path(__file__).parent
    # Use gui_entry.py which uses absolute imports to avoid relative import issues
    script_path = project_root / "src" / "llms_sitemap_generator" / "gui_entry.py"

    if not script_path.exists():
        print(f"[ERROR] GUI entry script not found: {script_path}")
        return 1

    # Build args for PyInstaller
    args = [
        str(script_path),  # Use gui_entry.py as entry point (uses absolute imports)
        "--name=llms-sitemap-generator-gui",
        "--onefile",  # Build as single file
        "--windowed",  # No console window (GUI app)
        "--icon=NONE",  # Can specify icon file path
        # Set the path so imports work correctly
        f"--paths={project_root / 'src'}",
        # Hidden imports for core dependencies
        "--hidden-import=llms_sitemap_generator",
        "--hidden-import=llms_sitemap_generator.cli",
        "--hidden-import=llms_sitemap_generator.config",
        "--hidden-import=llms_sitemap_generator.crawler",
        "--hidden-import=llms_sitemap_generator.filters",
        "--hidden-import=llms_sitemap_generator.generator",
        "--hidden-import=llms_sitemap_generator.gui_main",
        "--hidden-import=llms_sitemap_generator.html_summary",
        "--hidden-import=llms_sitemap_generator.logger",
        "--hidden-import=llms_sitemap_generator.site_analyzer",
        "--hidden-import=llms_sitemap_generator.sitemap",
        "--hidden-import=llms_sitemap_generator.subdomain_discovery",
        "--hidden-import=llms_sitemap_generator.url_utils",
        "--hidden-import=llms_sitemap_generator.validators",
        "--hidden-import=yaml",
        "--hidden-import=yaml.cyaml",
        "--hidden-import=requests",
        "--hidden-import=requests.packages.urllib3",
        "--hidden-import=charset_normalizer",
        "--hidden-import=idna",
        "--collect-all=PyQt5",  # Collect all PyQt5 dependencies
        "--collect-submodules=PyQt5",  # Collect all PyQt5 submodules
    ]

    print("=" * 60)
    print("LLMS Sitemap Generator - EXE Build")
    print("=" * 60)
    print(f"\nProject root: {project_root}")
    print(f"Entry script: {script_path}")
    print(f"Output: dist/llms-sitemap-generator-gui.exe")
    print()

    print("Building executable...")
    sys.argv = ["pyinstaller"] + args
    PyInstaller.__main__.run(args)

    exe_path = project_root / "dist" / "llms-sitemap-generator-gui.exe"
    if exe_path.exists():
        size_mb = exe_path.stat().st_size / (1024 * 1024)
        print()
        print("=" * 60)
        print(f"[SUCCESS] Build completed!")
        print(f"Executable: {exe_path}")
        print(f"Size: {size_mb:.2f} MB")
        print("=" * 60)
    else:
        print(f"[ERROR] Build failed - executable not found at {exe_path}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(build_exe())
