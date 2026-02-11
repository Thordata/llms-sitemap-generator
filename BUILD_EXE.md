# Building Windows Executable (.exe)

This guide explains how to build a standalone Windows executable (.exe) for the GUI tool.

## Prerequisites

1. **Python 3.8+** installed on Windows
2. **PyInstaller** installed:
   ```bash
   pip install pyinstaller
   ```
3. **All dependencies** installed:
   ```bash
   pip install -r requirements-gui.txt
   pip install -e .
   ```

## Quick Build

### Option 1: Using the build script (Recommended)

```bash
python build_exe.py
```

This will:
- Build a single-file executable
- Create `dist/llms-sitemap-generator-gui.exe`
- Include all dependencies
- Use `gui_entry.py` which handles relative import issues in PyInstaller

### Option 2: Manual build

**Important**: Use `gui_entry.py` instead of `gui_main.py` to avoid relative import issues:

```bash
pyinstaller --name=llms-sitemap-generator-gui ^
    --onefile ^
    --windowed ^
    --paths=src ^
    --hidden-import=llms_sitemap_generator ^
    --hidden-import=llms_sitemap_generator.gui_main ^
    --hidden-import=yaml ^
    --hidden-import=requests ^
    --collect-all=PyQt5 ^
    src/llms_sitemap_generator/gui_entry.py
```

**Note**: The build script (`build_exe.py`) automatically uses `gui_entry.py` which handles PyInstaller's import system correctly.

## Build Options

### Single-file executable (default)
- `--onefile`: Creates a single .exe file
- **Pros**: Easy to distribute
- **Cons**: Slower startup time

### Directory distribution
Remove `--onefile` to create a directory with multiple files:
```bash
pyinstaller --name=llms-sitemap-generator-gui ^
    --windowed ^
    --add-data="src/llms_sitemap_generator;llms_sitemap_generator" ^
    --hidden-import=llms_sitemap_generator ^
    --hidden-import=yaml ^
    --hidden-import=requests ^
    --collect-all=PyQt5 ^
    src/llms_sitemap_generator/gui_main.py
```
- **Pros**: Faster startup
- **Cons**: Multiple files to distribute

### Add custom icon
Create or download an `.ico` file, then:
```bash
pyinstaller --icon=icon.ico --onefile --windowed ...
```

## Output Location

After building, the executable will be in:
- **Single-file**: `dist/llms-sitemap-generator-gui.exe`
- **Directory**: `dist/llms-sitemap-generator-gui/` (with `llms-sitemap-generator-gui.exe` inside)

## Testing the Executable

1. Navigate to the `dist` folder
2. Double-click `llms-sitemap-generator-gui.exe`
3. Test all GUI features

## Troubleshooting

### Error: "Failed to execute script" or "attempted relative import with no known parent package"
- **Solution**: Make sure you're using `gui_entry.py` as the entry point (the build script does this automatically)
- The `gui_entry.py` file handles both normal execution and PyInstaller bundled execution
- Check that all dependencies are installed
- Try building with `--debug=all` to see detailed errors

### Error: "ImportError: attempted relative import with no known parent package"
- This error occurs when using `__main__.py` or `gui_main.py` directly with PyInstaller
- **Solution**: Always use `gui_entry.py` as the entry point (handled automatically by `build_exe.py`)

### Large file size
- This is normal for PyInstaller builds (includes Python runtime)
- Single-file executables are typically 50-100MB
- Consider using directory distribution for smaller size

### Missing modules
Add to `--hidden-import`:
```bash
--hidden-import=module_name
```

### PyQt5 issues
Ensure `--collect-all=PyQt5` is included in the build command.

## Distribution

The executable is standalone and can be distributed without:
- Python installation
- Dependencies installation
- Source code

Simply share the `.exe` file (or the entire `dist/` directory for directory builds).

## Advanced Options

### Reduce file size
```bash
--exclude-module=matplotlib
--exclude-module=numpy
```

### Add version info
Create a `version.txt` file and use:
```bash
--version-file=version.txt
```

### UPX compression (optional)
If UPX is installed:
```bash
--upx-dir=path/to/upx
```

## Notes

- First build may take several minutes
- Antivirus software may flag PyInstaller executables (false positive)
- Test on a clean Windows machine before distribution
