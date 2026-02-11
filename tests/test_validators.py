"""
配置验证器测试
"""
import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from llms_sitemap_generator.validators import (
    validate_url,
    validate_base_url,
    validate_domain,
    validate_language_code,
    validate_config_basic,
)


def test_validate_url():
    """测试 URL 验证"""
    # 有效 URL
    assert validate_url("https://example.com")[0] is True
    assert validate_url("http://example.com/path")[0] is True
    
    # 无效 URL
    assert validate_url("")[0] is False
    assert validate_url("not-a-url")[0] is False
    assert validate_url("ftp://example.com")[0] is False  # 不支持 ftp
    assert validate_url("example.com")[0] is False  # 缺少协议
    
    print("[OK] URL validation test passed")


def test_validate_domain():
    """测试域名验证"""
    # 有效域名
    assert validate_domain("example.com")[0] is True
    assert validate_domain("sub.example.com")[0] is True
    
    # 无效域名
    assert validate_domain("")[0] is False
    assert validate_domain("http://example.com")[0] is False
    assert validate_domain("example.com/path")[0] is False
    
    print("[OK] Domain validation test passed")


def test_validate_language_code():
    """测试语言代码验证"""
    # 有效语言代码
    assert validate_language_code("en")[0] is True
    assert validate_language_code("zh")[0] is True
    assert validate_language_code("pt")[0] is True
    
    # 无效语言代码
    assert validate_language_code("")[0] is False
    assert validate_language_code("1")[0] is False
    assert validate_language_code("english")[0] is False  # 太长
    
    print("[OK] Language code validation test passed")


def test_validate_config_basic():
    """测试配置验证"""
    # 有效配置
    valid_config = {
        "site": {
            "base_url": "https://example.com",
            "default_language": "en",
            "allowed_domains": ["example.com"],
        },
        "sources": [
            {"type": "sitemap", "url": "https://example.com/sitemap.xml"},
        ],
    }
    errors = validate_config_basic(valid_config)
    assert len(errors) == 0, f"有效配置不应有错误: {errors}"
    
    # 无效配置：缺少 site
    invalid_config = {"sources": []}
    errors = validate_config_basic(invalid_config)
    assert len(errors) > 0, "无效配置应该有错误"
    
    # 无效配置：无效 base_url
    invalid_config2 = {
        "site": {"base_url": "not-a-url"},
        "sources": [{"type": "sitemap", "url": "https://example.com/sitemap.xml"}],
    }
    errors = validate_config_basic(invalid_config2)
    assert len(errors) > 0, "无效 base_url 应该有错误"
    
    print("[OK] Config validation test passed")


def main():
    """运行所有测试"""
    print("=" * 50)
    print("配置验证器测试")
    print("=" * 50)
    
    try:
        test_validate_url()
        test_validate_domain()
        test_validate_language_code()
        test_validate_config_basic()
        
        print("\n" + "=" * 50)
        print("[OK] All tests passed")
        print("=" * 50)
        return 0
    except AssertionError as e:
        print(f"\n[FAIL] Test failed: {e}")
        return 1
    except Exception as e:
        print(f"\n[ERROR] Test error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
