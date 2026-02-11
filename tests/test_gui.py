"""
GUI 工具测试脚本
用于验证 GUI 工具的基本功能

注意：CI / lint 环境可能没有安装 PyQt5，因此这些测试会在缺少依赖时自动跳过。
"""

import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

import pytest


def test_imports():
    """测试导入"""
    try:
        from llms_sitemap_generator.gui_main import MainWindow  # noqa: F401

        print("✅ GUI 模块导入成功")
        return True
    except ImportError as e:
        print(f"❌ GUI 模块导入失败: {e}")
        print("提示: 请安装 PyQt5: pip install PyQt5")
        pytest.skip("PyQt5 not installed; skipping GUI import test")


def test_config_building():
    """测试配置构建"""
    try:
        from llms_sitemap_generator.gui_main import MainWindow
        from PyQt5.QtWidgets import QApplication

        app = (
            QApplication(sys.argv)
            if not QApplication.instance()
            else QApplication.instance()
        )
        window = MainWindow()

        # 设置测试值
        window.base_url_input.setText("https://www.example.com")
        window.lang_combo.setCurrentText("en")
        window.include_blog_toggle.setChecked(True)
        # 不设置 sitemap，验证仍然会添加 homepage crawl 作为 fallback

        # 测试构建配置
        try:
            config = window.build_config_from_ui()
            print("✅ 配置构建成功")
            print(f"   - Base URL: {config.site.base_url}")
            print(f"   - Default Language: {config.site.default_language}")
            print(f"   - Sources: {len(config.sources)}")
            # 关键断言：即使没有 sitemap，也应该有 crawl source 指向首页
            has_home_crawl = any(
                s.type == "crawl"
                and s.url.rstrip("/") == config.site.base_url.rstrip("/")
                for s in config.sources
            )
            print(f"   - Has homepage crawl fallback: {has_home_crawl}")
            assert has_home_crawl, (
                "Expected a homepage crawl source as fallback when sitemap is missing"
            )
            return True
        except Exception as e:
            print(f"❌ 配置构建失败: {e}")
            return False
    except ImportError as e:
        print(f"❌ 测试失败（依赖缺失）: {e}")
        pytest.skip("PyQt5 not installed; skipping GUI config building test")
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False


def main():
    """运行所有测试"""
    print("=" * 50)
    print("GUI 工具测试")
    print("=" * 50)

    results = []

    print("\n1. 测试导入...")
    results.append(test_imports())

    print("\n2. 测试配置构建...")
    results.append(test_config_building())

    print("\n" + "=" * 50)
    print(f"测试结果: {sum(results)}/{len(results)} 通过")
    print("=" * 50)

    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
