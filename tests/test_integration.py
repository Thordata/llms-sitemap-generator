"""
集成测试 - 测试完整的生成流程
"""
import sys
from pathlib import Path
import tempfile
import shutil

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from llms_sitemap_generator.config import load_config, AppConfig, SiteConfig, SourceConfig, FiltersConfig, OutputConfig
from llms_sitemap_generator.validators import validate_config_basic


def test_config_loading():
    """测试配置加载"""
    config_path = project_root / "llmstxt.config.yml"
    if not config_path.exists():
        print("[SKIP] Config file not found, skipping test")
        return
    
    config = load_config(config_path)
    assert config.site.base_url is not None
    assert len(config.sources) > 0
    print("[OK] Config loading test passed")


def test_config_validation():
    """测试配置验证"""
    # 有效配置
    valid_config = {
        "site": {
            "base_url": "https://example.com",
            "default_language": "en",
        },
        "sources": [
            {"type": "sitemap", "url": "https://example.com/sitemap.xml"},
        ],
    }
    
    errors = validate_config_basic(valid_config)
    assert len(errors) == 0, f"Valid config should have no errors: {errors}"
    
    # 无效配置
    invalid_config = {
        "site": {
            "base_url": "not-a-url",
        },
        "sources": [],
    }
    
    errors = validate_config_basic(invalid_config)
    assert len(errors) > 0, "Invalid config should have errors"
    
    print("[OK] Config validation test passed")


def test_dry_run():
    """测试 dry-run 模式（不实际生成文件）"""
    config_path = project_root / "llmstxt.config.yml"
    if not config_path.exists():
        print("[SKIP] Config file not found, skipping test")
        return
    
    from llms_sitemap_generator.generator import generate_llms_txt
    
    config = load_config(config_path)
    # 使用临时路径，避免覆盖实际文件
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "test_llms.txt"
        generate_llms_txt(
            config,
            output_path,
            dry_run=True,
            max_pages=5,  # 只测试前 5 页
            fetch_content=False,  # 不实际抓取内容
        )
    print("[OK] Dry-run test passed")


def main():
    """运行所有集成测试"""
    print("=" * 50)
    print("Integration Tests")
    print("=" * 50)
    
    print("\n1. Testing config loading...")
    try:
        test_config_loading()
    except Exception as e:
        print(f"[FAIL] {e}")
        return 1
    
    print("\n2. Testing config validation...")
    try:
        test_config_validation()
    except Exception as e:
        print(f"[FAIL] {e}")
        return 1
    
    print("\n3. Testing dry-run mode...")
    try:
        test_dry_run()
    except Exception as e:
        print(f"[FAIL] {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    print("\n" + "=" * 50)
    print("All tests passed!")
    print("=" * 50)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
