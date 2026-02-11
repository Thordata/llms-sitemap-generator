# 打包 Windows 可执行文件 (.exe)

本指南说明如何为 GUI 工具构建独立的 Windows 可执行文件 (.exe)。

## 前置要求

1. **Python 3.8+** 已安装在 Windows 上
2. **PyInstaller** 已安装：
   ```bash
   pip install pyinstaller
   ```
3. **所有依赖** 已安装：
   ```bash
   pip install -r requirements-gui.txt
   pip install -e .
   ```

## 快速打包

### 方法 1: 使用构建脚本（推荐）

```bash
python build_exe.py
```

这将：
- 构建单个可执行文件
- 创建 `dist/llms-sitemap-generator-gui.exe`
- 包含所有依赖
- 使用 `gui_entry.py` 处理 PyInstaller 的相对导入问题

### 方法 2: 手动打包

**重要**：使用 `gui_entry.py` 而不是 `gui_main.py` 以避免相对导入问题：

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

**注意**：构建脚本（`build_exe.py`）会自动使用 `gui_entry.py`，它正确处理了 PyInstaller 的导入系统。

## 打包选项

### 单文件可执行文件（默认）
- `--onefile`: 创建单个 .exe 文件
- **优点**: 易于分发
- **缺点**: 启动时间较慢

### 目录分发
移除 `--onefile` 以创建包含多个文件的目录：
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
- **优点**: 启动更快
- **缺点**: 需要分发多个文件

### 添加自定义图标
创建或下载 `.ico` 文件，然后：
```bash
pyinstaller --icon=icon.ico --onefile --windowed ...
```

## 输出位置

打包后，可执行文件位于：
- **单文件**: `dist/llms-sitemap-generator-gui.exe`
- **目录**: `dist/llms-sitemap-generator-gui/`（内含 `llms-sitemap-generator-gui.exe`）

## 测试可执行文件

1. 进入 `dist` 文件夹
2. 双击 `llms-sitemap-generator-gui.exe`
3. 测试所有 GUI 功能

## 故障排除

### 错误: "Failed to execute script" 或 "attempted relative import with no known parent package"
- **解决方案**：确保使用 `gui_entry.py` 作为入口点（构建脚本会自动处理）
- `gui_entry.py` 文件同时处理正常执行和 PyInstaller 打包执行
- 检查所有依赖是否已安装
- 尝试使用 `--debug=all` 构建以查看详细错误

### 错误: "ImportError: attempted relative import with no known parent package"
- 当直接使用 `__main__.py` 或 `gui_main.py` 与 PyInstaller 打包时会出现此错误
- **解决方案**：始终使用 `gui_entry.py` 作为入口点（`build_exe.py` 会自动处理）

### 文件大小过大
- 这对 PyInstaller 构建是正常的（包含 Python 运行时）
- 单文件可执行文件通常为 50-100MB
- 考虑使用目录分发以减小大小

### 缺少模块
添加到 `--hidden-import`：
```bash
--hidden-import=module_name
```

### PyQt5 问题
确保构建命令中包含 `--collect-all=PyQt5`。

## 分发

可执行文件是独立的，可以在没有以下内容的情况下分发：
- Python 安装
- 依赖安装
- 源代码

只需分享 `.exe` 文件（或目录构建的整个 `dist/` 目录）。

## 高级选项

### 减小文件大小
```bash
--exclude-module=matplotlib
--exclude-module=numpy
```

### 添加版本信息
创建 `version.txt` 文件并使用：
```bash
--version-file=version.txt
```

### UPX 压缩（可选）
如果已安装 UPX：
```bash
--upx-dir=path/to/upx
```

## 注意事项

- 首次构建可能需要几分钟
- 防病毒软件可能会标记 PyInstaller 可执行文件（误报）
- 分发前在干净的 Windows 机器上测试
