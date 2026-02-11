"""
配置验证工具
用于验证配置文件的正确性和完整性
"""
from __future__ import annotations

from urllib.parse import urlparse
from typing import List, Tuple


def validate_url(url: str) -> Tuple[bool, str]:
    """
    验证 URL 是否有效
    
    Returns:
        (is_valid, error_message)
    """
    if not url or not isinstance(url, str):
        return False, "URL 不能为空"
    
    url = url.strip()
    if not url:
        return False, "URL 不能为空"
    
    try:
        parsed = urlparse(url)
        if not parsed.scheme:
            return False, f"URL 缺少协议（scheme）: {url}"
        if parsed.scheme not in ("http", "https"):
            return False, f"URL 协议必须是 http 或 https: {url}"
        if not parsed.netloc:
            return False, f"URL 缺少域名: {url}"
        return True, ""
    except Exception as e:
        return False, f"URL 格式无效: {e}"


def validate_base_url(base_url: str) -> Tuple[bool, str]:
    """验证 base_url"""
    is_valid, msg = validate_url(base_url)
    if not is_valid:
        return False, f"base_url 无效: {msg}"
    
    # base_url 应该以 / 结尾或没有路径
    parsed = urlparse(base_url)
    if parsed.path and parsed.path != "/" and not parsed.path.endswith("/"):
        # 这不是错误，只是建议
        pass
    
    return True, ""


def validate_domain(domain: str) -> Tuple[bool, str]:
    """
    验证域名格式
    
    Returns:
        (is_valid, error_message)
    """
    if not domain or not isinstance(domain, str):
        return False, "域名不能为空"
    
    domain = domain.strip().lower()
    
    # 基本格式检查
    if "." not in domain:
        return False, f"域名格式无效: {domain}"
    
    # 不能包含协议
    if domain.startswith(("http://", "https://")):
        return False, f"域名不应包含协议: {domain}"
    
    # 不能包含路径
    if "/" in domain:
        return False, f"域名不应包含路径: {domain}"
    
    return True, ""


def validate_language_code(lang: str) -> Tuple[bool, str]:
    """
    验证语言代码格式（ISO 639-1）
    
    Returns:
        (is_valid, error_message)
    """
    if not lang or not isinstance(lang, str):
        return False, "语言代码不能为空"
    
    lang = lang.strip().lower()
    
    # 基本格式：2-3 个字母
    if not lang.isalpha():
        return False, f"语言代码只能包含字母: {lang}"
    
    if len(lang) < 2 or len(lang) > 3:
        return False, f"语言代码长度应为 2-3 个字母: {lang}"
    
    return True, ""


def validate_config_basic(config_dict: dict) -> List[str]:
    """
    验证配置的基本结构
    
    Returns:
        错误消息列表（空列表表示无错误）
    """
    errors: List[str] = []
    
    if not isinstance(config_dict, dict):
        errors.append("配置文件必须是 YAML 字典格式")
        return errors
    
    # 检查 site 部分
    if "site" not in config_dict:
        errors.append("配置缺少 'site' 部分")
        return errors
    
    site = config_dict.get("site", {})
    if not isinstance(site, dict):
        errors.append("'site' 必须是字典格式")
        return errors
    
    # 验证 base_url
    base_url = site.get("base_url")
    if not base_url:
        errors.append("'site.base_url' 是必需的")
    else:
        is_valid, msg = validate_base_url(base_url)
        if not is_valid:
            errors.append(msg)
    
    # 验证 default_language（可选，但如果有则验证格式）
    default_lang = site.get("default_language")
    if default_lang:
        is_valid, msg = validate_language_code(default_lang)
        if not is_valid:
            errors.append(f"'site.default_language' {msg}")
    
    # 验证 allowed_domains（可选）
    allowed_domains = site.get("allowed_domains", [])
    if allowed_domains:
        if not isinstance(allowed_domains, list):
            errors.append("'site.allowed_domains' 必须是列表")
        else:
            for i, domain in enumerate(allowed_domains):
                is_valid, msg = validate_domain(domain)
                if not is_valid:
                    errors.append(f"'site.allowed_domains[{i}]' {msg}")
    
    # 检查 sources 部分
    if "sources" not in config_dict:
        errors.append("配置缺少 'sources' 部分")
        return errors
    
    sources = config_dict.get("sources", [])
    if not isinstance(sources, list):
        errors.append("'sources' 必须是列表")
        return errors
    
    if len(sources) == 0:
        errors.append("'sources' 至少需要包含一个数据源")
        return errors
    
    # 验证每个 source
    for i, src in enumerate(sources):
        if not isinstance(src, dict):
            errors.append(f"'sources[{i}]' 必须是字典格式")
            continue
        
        src_type = src.get("type")
        if not src_type:
            errors.append(f"'sources[{i}].type' 是必需的")
            continue
        
        if src_type not in ("sitemap", "crawl", "static"):
            errors.append(f"'sources[{i}].type' 必须是 'sitemap'、'crawl' 或 'static': {src_type}")
        
        # 验证 URL
        if src_type in ("sitemap", "crawl"):
            url = src.get("url")
            if not url:
                errors.append(f"'sources[{i}].url' 是必需的（当 type={src_type} 时）")
            else:
                is_valid, msg = validate_url(url)
                if not is_valid:
                    errors.append(f"'sources[{i}].url' {msg}")
        
        # static 类型需要 urls 列表
        if src_type == "static":
            urls = src.get("urls", [])
            if not urls or not isinstance(urls, list):
                errors.append(f"'sources[{i}].urls' 是必需的且必须是列表（当 type=static 时）")
            else:
                for j, url in enumerate(urls):
                    is_valid, msg = validate_url(url)
                    if not is_valid:
                        errors.append(f"'sources[{i}].urls[{j}]' {msg}")
    
    return errors
