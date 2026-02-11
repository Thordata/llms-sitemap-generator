"""
LLMS Sitemap Generator - GUI Tool
基于 PyQt5 的可视化配置工具
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Optional

try:
    from PyQt5.QtWidgets import (
        QApplication,
        QMainWindow,
        QWidget,
        QVBoxLayout,
        QHBoxLayout,
        QPushButton,
        QLabel,
        QTextEdit,
        QTreeWidget,
        QTreeWidgetItem,
        QSplitter,
        QTabWidget,
        QLineEdit,
        QCheckBox,
        QSpinBox,
        QGroupBox,
        QMessageBox,
        QProgressBar,
        QFileDialog,
        QComboBox,
        QScrollArea,
        QSizePolicy,
    )
    from PyQt5.QtCore import Qt, QThread, pyqtSignal
    from PyQt5.QtGui import QFont
except ImportError:
    print("PyQt5 is not installed. Please install it with: pip install PyQt5")
    sys.exit(1)

from .config import (
    load_config,
    AppConfig,
    SiteConfig,
    FiltersConfig,
    OutputConfig,
    SourceConfig,
    FilterRule,
)
from .sitemap import collect_urls_from_sources
from .filters import filter_and_group_urls, PageEntry
from .generator import generate_llms_txt, generate_llms_from_urls
from .logger import get_logger
from urllib.parse import urlparse

logger = get_logger(__name__)

try:
    import yaml
except ImportError:
    yaml = None  # 如果 yaml 未安装，会在保存配置时提示


class URLCollectionThread(QThread):
    """后台线程：收集 URL"""

    progress = pyqtSignal(str)
    finished = pyqtSignal(list, list)  # (urls, failed_urls)
    error = pyqtSignal(str)

    def __init__(self, config: AppConfig):
        super().__init__()
        self.config = config

    def run(self):
        try:
            import requests

            session = requests.Session()
            self.progress.emit("正在收集 URL...")

            # 收集失败的URL列表
            failed_urls = []
            urls = collect_urls_from_sources(
                self.config, session, failed_urls=failed_urls
            )
            self.finished.emit(urls, failed_urls)
        except Exception as e:
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config: Optional[AppConfig] = None
        self.all_urls: List[str] = []
        self.filtered_pages: List[PageEntry] = []
        self.failed_urls: List[dict] = []  # 存储失败的URL
        self.discovered_subdomains: set = set()  # 存储发现的子域名
        self.group_items: dict = {}  # 存储分组项
        self.collection_thread: Optional[URLCollectionThread] = None
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("LLMS Sitemap Generator - GUI Tool")
        # 让初始窗口尺寸尽量落在屏幕可用区域内（避开任务栏），避免底部按钮被遮挡
        try:
            screen = QApplication.primaryScreen()
            if screen:
                geo = screen.availableGeometry()
                w = min(1200, max(900, geo.width() - 80))
                h = min(800, max(650, geo.height() - 80))
                self.setGeometry(100, 60, w, h)
            else:
                self.setGeometry(100, 60, 1200, 800)
        except Exception:
            self.setGeometry(100, 60, 1200, 800)

        # 主窗口部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 主布局：使用 QSplitter 支持拖拽调整左右宽度
        main_layout = QHBoxLayout(central_widget)
        splitter = QSplitter(Qt.Horizontal)

        # 左侧：配置面板（内部可滚动 + 底部按钮固定）
        config_panel = self.create_config_panel()
        splitter.addWidget(config_panel)

        # 右侧：URL 预览区域
        preview_panel = self.create_preview_panel()
        splitter.addWidget(preview_panel)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        main_layout.addWidget(splitter)

    def create_config_panel(self) -> QWidget:
        """创建配置面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # 让内容区域可滚动：避免窗口高度较小时底部按钮被遮挡
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(10)

        # 站点配置
        site_group = QGroupBox("Site Settings / 站点配置")
        site_layout = QVBoxLayout()

        # Base URL：以英文为主，附带中文说明
        self.base_url_input = QLineEdit("https://example.com")
        base_url_label = QLabel("Base URL（站点主域名）:")
        base_url_label.setToolTip(
            "Website base URL, e.g. https://example.com or https://www.example.com"
        )
        site_layout.addWidget(base_url_label)
        site_layout.addWidget(self.base_url_input)

        self.default_lang_input = QLineEdit("en")
        default_lang_label = QLabel("Default Language（默认语言代码，如 en/zh）:")
        default_lang_label.setToolTip(
            "Two-letter language code (IETF), used to keep only this language in llms.txt"
        )
        site_layout.addWidget(default_lang_label)
        site_layout.addWidget(self.default_lang_input)

        # 是否自动从 sitemap 中发现子域（类似 crt.sh 思路，但基于站点自身 sitemap）
        self.auto_subdomains_check = QCheckBox(
            "Auto-discover subdomains from sitemap（自动从 sitemap 发现子域，推荐开启）"
        )
        self.auto_subdomains_check.setChecked(True)
        self.auto_subdomains_check.setToolTip(
            "Try to discover additional subdomains (e.g. blog.example.com, docs.example.com) "
            "by parsing sitemap.xml and automatically add them to allowed domains & sources."
        )
        site_layout.addWidget(self.auto_subdomains_check)

        # 子域名发现和选择区域
        subdomain_group = QGroupBox("Subdomain Discovery / 子域名发现")
        subdomain_layout = QVBoxLayout()

        # 发现按钮
        discover_btn_layout = QHBoxLayout()
        self.discover_subdomains_btn = QPushButton(
            "🔍 Discover Subdomains / 发现子域名"
        )
        self.discover_subdomains_btn.setToolTip(
            "Click to discover all subdomains from sitemap and homepage. "
            "After discovery, you can select which subdomains to include."
        )
        self.discover_subdomains_btn.clicked.connect(self.on_discover_subdomains)
        discover_btn_layout.addWidget(self.discover_subdomains_btn)

        self.select_all_subdomains_btn = QPushButton("Select All")
        self.select_all_subdomains_btn.clicked.connect(self.select_all_subdomains)
        self.select_all_subdomains_btn.setEnabled(False)
        discover_btn_layout.addWidget(self.select_all_subdomains_btn)

        self.deselect_all_subdomains_btn = QPushButton("Deselect All")
        self.deselect_all_subdomains_btn.clicked.connect(self.deselect_all_subdomains)
        self.deselect_all_subdomains_btn.setEnabled(False)
        discover_btn_layout.addWidget(self.deselect_all_subdomains_btn)

        discover_btn_layout.addStretch()
        subdomain_layout.addLayout(discover_btn_layout)

        # 子域名列表
        self.subdomain_list = QTreeWidget()
        self.subdomain_list.setHeaderLabels(
            ["Subdomain / 子域名", "Status / 状态", "Source / 来源"]
        )
        self.subdomain_list.setMaximumHeight(120)
        self.subdomain_list.setToolTip(
            "List of discovered subdomains. Check/uncheck to include/exclude from crawling."
        )
        subdomain_layout.addWidget(self.subdomain_list)

        subdomain_group.setLayout(subdomain_layout)
        site_layout.addWidget(subdomain_group)

        # 存储发现的子域名
        self.discovered_subdomains = set()

        # 站点描述：用于 llms.txt 顶部的 Site Overview，帮助的说明性文案
        self.site_desc_edit = QTextEdit()
        self.site_desc_edit.setPlaceholderText(
            "Optional: short site overview in EN (recommended), will appear at the top of llms.txt as "
            "'Site Overview'.\n"
            "例如（中文提示）：简要说明你的网站提供什么产品/服务、面向哪些用户、有哪些主要板块。"
        )
        self.site_desc_edit.setFixedHeight(70)
        site_layout.addWidget(QLabel("Site Description（站点概览，可选，建议英文）:"))
        site_layout.addWidget(self.site_desc_edit)

        site_group.setLayout(site_layout)
        content_layout.addWidget(site_group)

        # 数据源配置
        source_group = QGroupBox("Sources / 数据源")
        source_layout = QVBoxLayout()

        self.sitemap_url_input = QLineEdit("https://example.com/sitemap.xml")
        sitemap_label = QLabel("Sitemap URL（如果站点有 sitemap.xml，强烈推荐填写）:")
        sitemap_label.setToolTip(
            "Primary sitemap.xml or sitemap index URL for the site you are configuring."
        )
        source_layout.addWidget(sitemap_label)
        source_layout.addWidget(self.sitemap_url_input)

        # 额外爬取入口（例如 /blog），用于补充 sitemap 中没有覆盖到的内容
        self.crawl_url_input = QLineEdit("")
        self.crawl_url_input.setPlaceholderText(
            "e.g. https://example.com/blog 或 https://example.com/docs（可选）"
        )
        crawl_label = QLabel("Crawl Start URL（可选，建议填写 Blog 或 Docs 入口）:")
        crawl_label.setToolTip(
            "Optional crawl start URL to complement sitemap, e.g. /blog or /docs. "
            "For JS-heavy blogs that are hard to discover via sitemap, this is important."
        )
        source_layout.addWidget(crawl_label)
        source_layout.addWidget(self.crawl_url_input)

        crawl_row = QHBoxLayout()
        self.crawl_depth_spin = QSpinBox()
        self.crawl_depth_spin.setRange(1, 10)
        # 默认深度从 3 调低到 2，适合大多数 B2B 站点的「主导航 + 一级内容」采样，
        # 可以明显减少请求数量，加快初次跑站时间
        self.crawl_depth_spin.setValue(2)
        crawl_row.addWidget(QLabel("Max Depth（爬取深度）:"))
        crawl_row.addWidget(self.crawl_depth_spin)

        self.crawl_max_urls_spin = QSpinBox()
        self.crawl_max_urls_spin.setRange(10, 20000)
        # 默认单入口最多 URL 数从 500 调整到 200，
        # 在「sitemap + crawl」组合场景下更适合作为补充采样，避免 crawl 成为主要耗时瓶颈
        self.crawl_max_urls_spin.setValue(200)
        crawl_row.addWidget(QLabel("Max URLs（单入口最多 URL 数）:"))
        crawl_row.addWidget(self.crawl_max_urls_spin)

        source_layout.addLayout(crawl_row)

        # 静态重要 URL（每行一个），用于手动补充关键页面
        self.static_urls_edit = QTextEdit()
        self.static_urls_edit.setPlaceholderText(
            "Static URLs（optional）：one URL per line, for extremely important pages that are hard to discover.\n"
            "例如：\nhttps://docs.example.com/interface-documentation\nhttps://www.example.com/special-landing-page"
        )
        self.static_urls_edit.setFixedHeight(80)
        source_layout.addWidget(QLabel("Static URLs（手工补充 URL，可选）:"))
        source_layout.addWidget(self.static_urls_edit)

        source_group.setLayout(source_layout)
        content_layout.addWidget(source_group)

        # 过滤规则
        filter_group = QGroupBox("Filters / 过滤规则")
        filter_layout = QVBoxLayout()

        self.auto_filter_lang_check = QCheckBox(
            "Auto-filter languages（仅保留默认语言对应内容）"
        )
        self.auto_filter_lang_check.setChecked(True)
        filter_layout.addWidget(self.auto_filter_lang_check)

        # 是否启用内置的通用排除规则（搜索、分页、feed、404 等）
        self.use_default_excludes_check = QCheckBox(
            "Use built-in default excludes（search、tag、feed、404 等常见噪声）"
        )
        self.use_default_excludes_check.setChecked(True)
        filter_layout.addWidget(self.use_default_excludes_check)

        self.exclude_blog_check = QCheckBox("Exclude Blog Pages（排除 /blog 下文章）")
        self.exclude_blog_check.setChecked(False)  # 默认不排除blog
        self.exclude_blog_check.setToolTip(
            "If checked, excludes /blog/ paths. Uncheck to include blog articles."
        )
        filter_layout.addWidget(self.exclude_blog_check)

        # 一些常见可选排除项，用户可以直接勾选，无需写正则
        self.exclude_careers_check = QCheckBox("Exclude careers pages（排除 /careers）")
        self.exclude_careers_check.setChecked(True)
        filter_layout.addWidget(self.exclude_careers_check)

        self.exclude_news_check = QCheckBox(
            "Exclude news/press（排除 /news, /newsroom）"
        )
        self.exclude_news_check.setChecked(True)
        filter_layout.addWidget(self.exclude_news_check)

        self.exclude_admin_check = QCheckBox(
            "Exclude admin/login（排除 /admin, /login 等）"
        )
        self.exclude_admin_check.setChecked(False)
        filter_layout.addWidget(self.exclude_admin_check)

        # Profile 选择（minimal / recommended / full），用于生成时一键控制分组档位
        profile_row = QHBoxLayout()
        profile_row.addWidget(QLabel("Profile（输出档位，可选）:"))
        self.profile_combo = QComboBox()
        self.profile_combo.addItem("Auto（auto-select by config / 默认）", "")
        self.profile_combo.addItem("minimal", "minimal")
        self.profile_combo.addItem("recommended", "recommended")
        self.profile_combo.addItem("full", "full")
        profile_row.addWidget(self.profile_combo)
        filter_layout.addLayout(profile_row)

        filter_group.setLayout(filter_layout)
        content_layout.addWidget(filter_group)

        # 输出配置
        output_group = QGroupBox("Output / 输出文件")
        output_layout = QVBoxLayout()

        # 基本输出路径（llms.txt / llms-full.txt / llms.json）
        self.llms_txt_input = QLineEdit("llms.txt")
        self.llms_full_input = QLineEdit("llms-full.txt")
        self.llms_json_input = QLineEdit("llms.json")

        row_llms = QHBoxLayout()
        row_llms.addWidget(QLabel("llms.txt:"))
        row_llms.addWidget(self.llms_txt_input)
        output_layout.addLayout(row_llms)

        row_full = QHBoxLayout()
        row_full.addWidget(QLabel("llms-full.txt:"))
        row_full.addWidget(self.llms_full_input)
        output_layout.addLayout(row_full)

        row_json = QHBoxLayout()
        row_json.addWidget(QLabel("llms.json:"))
        row_json.addWidget(self.llms_json_input)
        output_layout.addLayout(row_json)

        # sitemap 输出
        self.sitemap_xml_input = QLineEdit("sitemap.xml")
        self.sitemap_index_input = QLineEdit("sitemap_index.xml")

        row_sitemap = QHBoxLayout()
        row_sitemap.addWidget(QLabel("sitemap.xml:"))
        row_sitemap.addWidget(self.sitemap_xml_input)
        output_layout.addLayout(row_sitemap)

        row_index = QHBoxLayout()
        row_index.addWidget(QLabel("sitemap_index.xml:"))
        row_index.addWidget(self.sitemap_index_input)
        output_layout.addLayout(row_index)

        # 生成时的最大页面数（防止一次性输出过大）
        max_pages_row = QHBoxLayout()
        max_pages_row.addWidget(QLabel("Max pages for generate（生成页数上限，0 表示不限）:"))
        self.generate_max_pages_spin = QSpinBox()
        self.generate_max_pages_spin.setRange(0, 100000)
        self.generate_max_pages_spin.setValue(0)
        max_pages_row.addWidget(self.generate_max_pages_spin)
        output_layout.addLayout(max_pages_row)

        output_group.setLayout(output_layout)
        content_layout.addWidget(output_group)

        content_layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        # 底部固定操作区：永远可见，不会被任务栏遮挡
        action_bar = QWidget()
        action_layout = QVBoxLayout(action_bar)
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setSpacing(6)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self.load_config_btn = QPushButton("📂 Load Config")
        self.load_config_btn.setToolTip(
            "Load configuration from YAML file (e.g., llmstxt.config.yml)"
        )
        self.load_config_btn.clicked.connect(self.load_config_file)
        btn_layout.addWidget(self.load_config_btn)

        self.save_config_btn = QPushButton("💾 Save Config")
        self.save_config_btn.setToolTip("Save current settings to YAML file")
        self.save_config_btn.clicked.connect(self.save_config_file)
        btn_layout.addWidget(self.save_config_btn)

        btn_layout.addStretch(1)
        action_layout.addLayout(btn_layout)

        # 主要动作按钮行
        action_row = QHBoxLayout()
        action_row.setSpacing(8)

        self.collect_btn = QPushButton("Collect URLs / 收集 URL")
        self.collect_btn.clicked.connect(self.collect_urls)
        action_row.addWidget(self.collect_btn)

        self.generate_btn = QPushButton("Generate llms.txt / 生成 llms.txt")
        self.generate_btn.clicked.connect(self.generate_output)
        self.generate_btn.setEnabled(False)
        action_row.addWidget(self.generate_btn)

        self.export_dead_links_btn = QPushButton("🐛 Export Dead Links / 导出死链")
        self.export_dead_links_btn.clicked.connect(self.export_dead_links)
        self.export_dead_links_btn.setEnabled(False)
        self.export_dead_links_btn.setToolTip(
            "Export URLs that returned 404 or other errors during crawling.\n"
            "导出爬取过程中返回 404 或其他错误的 URL。"
        )
        action_row.addWidget(self.export_dead_links_btn)

        action_layout.addLayout(action_row)

        # 进度条放在固定区底部，避免滚动时看不到
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        action_layout.addWidget(self.progress_bar)

        layout.addWidget(action_bar, 0)
        return panel

    def create_preview_panel(self) -> QWidget:
        """创建预览面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # 统计信息
        self.stats_label = QLabel("Waiting to collect URLs / 等待收集 URL ...")
        layout.addWidget(self.stats_label)

        # 分组树形视图 + URL 列表用 splitter 纵向分割，便于上下拖拽调整高度
        splitter = QSplitter(Qt.Vertical)

        self.group_tree = QTreeWidget()
        self.group_tree.setHeaderLabels(
            ["Group / 分组", "URL Count / 数量", "Status / 状态"]
        )
        self.group_tree.itemChanged.connect(self.on_group_item_changed)
        splitter.addWidget(self.group_tree)

        # 分组全选 / 全不选 按钮
        group_btn_row = QHBoxLayout()
        self.select_all_groups_btn = QPushButton("Select All Groups / 全选分组")
        self.select_all_groups_btn.setToolTip(
            "Check all groups so that all filtered URLs are included."
        )
        self.select_all_groups_btn.clicked.connect(self.select_all_groups)
        group_btn_row.addWidget(self.select_all_groups_btn)

        self.deselect_all_groups_btn = QPushButton("Deselect All Groups / 全不选")
        self.deselect_all_groups_btn.setToolTip(
            "Uncheck all groups quickly, then you can pick only a few groups."
        )
        self.deselect_all_groups_btn.clicked.connect(self.deselect_all_groups)
        group_btn_row.addWidget(self.deselect_all_groups_btn)

        layout.addLayout(group_btn_row)

        url_panel = QWidget()
        url_panel_layout = QVBoxLayout(url_panel)
        url_panel_layout.setContentsMargins(0, 0, 0, 0)
        url_panel_layout.setSpacing(6)

        url_label = QLabel("URL List / URL 列表:")
        url_panel_layout.addWidget(url_label)

        self.url_list = QTextEdit()
        self.url_list.setReadOnly(True)
        self.url_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        url_panel_layout.addWidget(self.url_list)

        splitter.addWidget(url_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter, 1)

        return panel

    def on_discover_subdomains(self):
        """发现子域名并显示在列表中"""
        base_url = self.base_url_input.text().strip()
        if not base_url:
            QMessageBox.warning(
                self,
                "Missing URL / 缺少 URL",
                "Please enter a Base URL first before discovering subdomains.\n"
                "请先输入基础网址再发现子域名。",
            )
            return

        import requests
        from .subdomain_discovery import discover_subdomains_comprehensive

        try:
            self.discover_subdomains_btn.setEnabled(False)
            self.discover_subdomains_btn.setText("🔍 Discovering... / 发现中...")

            session = requests.Session()
            session.headers.setdefault(
                "User-Agent",
                "llms-sitemap-generator/0.1.0 (+https://github.com/thordata/llms-sitemap-generator)",
            )

            # 发现子域名
            discovered = discover_subdomains_comprehensive(base_url, session)
            self.discovered_subdomains = discovered

            # 清空列表并添加发现的子域名
            self.subdomain_list.clear()

            if not discovered:
                QMessageBox.information(
                    self,
                    "Discovery Result / 发现结果",
                    "No subdomains discovered.\n未发现子域名。",
                )
                return

            # 解析主域名
            parsed = urlparse(base_url)
            main_domain = parsed.netloc.lower()

            for domain in sorted(discovered):
                item = QTreeWidgetItem(self.subdomain_list)
                item.setText(0, domain)
                item.setCheckState(0, Qt.Checked)

                # 判断是主域名还是子域名
                if domain == main_domain:
                    item.setText(1, "Main Domain / 主域名")
                    item.setText(2, "Primary")
                else:
                    item.setText(1, "Subdomain / 子域名")
                    item.setText(2, "Discovered")

            # 启用选择按钮
            self.select_all_subdomains_btn.setEnabled(True)
            self.deselect_all_subdomains_btn.setEnabled(True)

            QMessageBox.information(
                self,
                "Discovery Complete / 发现完成",
                f"Discovered {len(discovered)} subdomain(s):\n"
                f"发现 {len(discovered)} 个子域名：\n\n"
                + "\n".join(sorted(discovered)),
            )

        except Exception as e:
            QMessageBox.critical(
                self,
                "Discovery Failed / 发现失败",
                f"Failed to discover subdomains:\n{e}\n\n子域名发现失败：\n{e}",
            )
        finally:
            self.discover_subdomains_btn.setEnabled(True)
            self.discover_subdomains_btn.setText("🔍 Discover Subdomains / 发现子域名")

    def select_all_subdomains(self):
        """选择所有子域名"""
        for i in range(self.subdomain_list.topLevelItemCount()):
            item = self.subdomain_list.topLevelItem(i)
            item.setCheckState(0, Qt.Checked)

    def deselect_all_subdomains(self):
        """取消选择所有子域名"""
        for i in range(self.subdomain_list.topLevelItemCount()):
            item = self.subdomain_list.topLevelItem(i)
            item.setCheckState(0, Qt.Unchecked)

    def get_selected_subdomains(self) -> set:
        """获取用户选择的子域名"""
        selected = set()
        for i in range(self.subdomain_list.topLevelItemCount()):
            item = self.subdomain_list.topLevelItem(i)
            if item.checkState(0) == Qt.Checked:
                selected.add(item.text(0))
        return selected

    def build_config_from_ui(self) -> AppConfig:
        """从 UI 输入构建配置对象"""
        # 如果之前通过“加载配置”导入了完整配置，这里在其基础上进行修改，
        # 尽量保留高级 include / group_limits / profiles 等设置，避免 GUI 覆盖掉手写配置。
        base_config: Optional[AppConfig] = self.config

        base_url = self.base_url_input.text().strip()
        if not base_url:
            raise ValueError("Base URL 不能为空")

        default_language = self.default_lang_input.text().strip() or "en"
        parsed = urlparse(base_url)
        main_domain = parsed.netloc.lower()

        # 如果之前加载过配置，但现在用户输入的 base_url 已经切换到完全不同的站点，
        # 则视为“新站点配置”，避免继续沿用旧站点（如 thordata.com）的 allowed_domains 和 sources，
        # 以免出现“明明输入了新站点，但还是在爬旧站点”的困惑。
        if base_config is not None:
            old_host = urlparse(base_config.site.base_url).netloc.lower()

            def _root_domain(host: str) -> str:
                parts = host.split(".")
                return ".".join(parts[-2:]) if len(parts) >= 2 else host

            if _root_domain(old_host) != _root_domain(main_domain):
                # 不同根域名：重置为全新配置，仅保留过滤与输出策略
                base_config = None

        allowed_domains = [main_domain]

        # 如果 base_config 中已经有 allowed_domains，则合并（避免丢失手写的其他子域）
        if base_config is not None and base_config.site.allowed_domains:
            for d in base_config.site.allowed_domains:
                d = d.lower()
                if d and d not in allowed_domains:
                    allowed_domains.append(d)

        # 如果 sitemap URL 包含不同域名，也添加
        sitemap_url = self.sitemap_url_input.text().strip()
        if sitemap_url:
            parsed_sitemap = urlparse(sitemap_url)
            sitemap_domain = parsed_sitemap.netloc.lower()
            if sitemap_domain and sitemap_domain not in allowed_domains:
                allowed_domains.append(sitemap_domain)

        # 站点描述：优先使用 UI 中输入，其次沿用已有配置
        site_description = self.site_desc_edit.toPlainText().strip()
        if not site_description and base_config is not None:
            site_description = base_config.site.description or ""

        # 构建站点配置
        site = SiteConfig(
            base_url=base_url.rstrip("/"),
            default_language=default_language,
            allowed_domains=allowed_domains,
            description=site_description or None,
        )

        # -------- 数据源配置 --------
        sources: List[SourceConfig] = []

        if base_config is not None and base_config.sources:
            # 从已有配置拷贝一份，避免直接修改原对象
            for src in base_config.sources:
                copied = SourceConfig(
                    type=src.type,
                    url=src.url,
                    max_depth=src.max_depth,
                    max_urls=src.max_urls,
                    urls=list(src.urls),
                )
                sources.append(copied)

            # 如果 UI 中填写了 sitemap，则覆盖/补充 sitemap 源
            if sitemap_url:
                sitemap_source = next((s for s in sources if s.type == "sitemap"), None)
                if sitemap_source:
                    sitemap_source.url = sitemap_url
                else:
                    sources.append(SourceConfig(type="sitemap", url=sitemap_url))
        else:
            # 无已有配置时，用 UI 构建基础 sources
            if sitemap_url:
                sources.append(SourceConfig(type="sitemap", url=sitemap_url))

        # 根据 UI 的 crawl / static 设置补充数据源
        crawl_url = self.crawl_url_input.text().strip()
        if crawl_url:
            sources.append(
                SourceConfig(
                    type="crawl",
                    url=crawl_url,
                    max_depth=int(self.crawl_depth_spin.value()),
                    max_urls=int(self.crawl_max_urls_spin.value()),
                )
            )

        static_urls_text = self.static_urls_edit.toPlainText().strip()
        if static_urls_text:
            static_urls = [
                line.strip() for line in static_urls_text.splitlines() if line.strip()
            ]
            if static_urls:
                sources.append(SourceConfig(type="static", urls=static_urls))

        # 关键修复：总是添加一个从 base_url 开始的 crawl 源，作为 sitemap 的补充
        # 这样可以确保发现 sitemap 中没有覆盖到的深层页面
        # 检查是否已经有从 base_url 开始的 crawl 源
        has_base_crawl = any(
            s.type == "crawl" and s.url.rstrip("/") == base_url.rstrip("/")
            for s in sources
        )

        if not has_base_crawl:
            logger.info(
                f"Adding base crawl source from {base_url} to supplement sitemap"
            )
            sources.append(
                SourceConfig(
                    type="crawl",
                    url=base_url.rstrip("/"),
                    max_depth=int(self.crawl_depth_spin.value()),
                    max_urls=int(self.crawl_max_urls_spin.value()),
                )
            )

        # Optional: Auto-add common content sections if not excluded
        # This is a convenience feature that can be disabled if not needed
        # Users can manually add crawl sources for specific sections if needed
        common_sections = ["/blog", "/docs", "/documentation"]
        for section in common_sections:
            section_url = f"{base_url.rstrip('/')}{section}"
            has_section_crawl = any(
                s.type == "crawl" and s.url.rstrip("/") == section_url for s in sources
            )
            # Only auto-add if:
            # 1. Not already in sources
            # 2. Not explicitly excluded (for blog, check exclude_blog_check)
            # 3. User hasn't disabled this feature
            should_add = False
            if section == "/blog" and not self.exclude_blog_check.isChecked():
                should_add = True
            elif section in ["/docs", "/documentation"]:
                # For docs, always try to add if not present (docs are usually important)
                should_add = True
            
            if should_add and not has_section_crawl:
                logger.info(f"Auto-adding crawl source for {section_url}")
                sources.append(
                    SourceConfig(
                        type="crawl",
                        url=section_url,
                        max_depth=int(self.crawl_depth_spin.value()),
                        max_urls=int(self.crawl_max_urls_spin.value()),
                    )
                )

        # 如果 sources 列表仍然为空（理论上不会，但做安全兜底）
        if not sources:
            # 优先尝试 sitemap
            default_sitemap_url = f"{base_url.rstrip('/')}/sitemap.xml"
            sources.append(SourceConfig(type="sitemap", url=default_sitemap_url))
            # 同时添加一个从 base_url 开始的 crawl 源
            sources.append(
                SourceConfig(
                    type="crawl",
                    url=base_url.rstrip("/"),
                    max_depth=int(self.crawl_depth_spin.value()),
                    max_urls=int(self.crawl_max_urls_spin.value()),
                )
            )

        # -------- 过滤配置 --------
        if base_config is not None:
            include_rules = list(base_config.filters.include)
            # 先复制一份原始 exclude，再根据勾选情况增删
            base_excludes = list(base_config.filters.exclude)
            base_profiles = dict(base_config.filters.profiles)
            base_group_limits = dict(base_config.filters.group_limits)
            base_default_group_limit = base_config.filters.default_group_limit
        else:
            include_rules = []
            base_excludes = []
            base_profiles = {}
            base_group_limits = {}
            base_default_group_limit = None

        # 从 base_excludes 中移除由 GUI 控制的几类规则（避免重复 / 与勾选状态冲突）
        controlled_prefixes = [
            "^/blog",
            "^/careers",
            "newsroom",
            "/news",
            "^/admin",
            "/login",
        ]
        exclude_rules: List[FilterRule] = []
        for r in base_excludes:
            if any(
                r.pattern.startswith(pfx) or pfx in r.pattern
                for pfx in controlled_prefixes
            ):
                continue
            exclude_rules.append(r)

        # 只有当用户明确勾选"排除Blog"时才排除/blog/路径（不排除 blog 子域）
        if self.exclude_blog_check.isChecked():
            exclude_rules.append(FilterRule(pattern="^/blog/"))

        # 其他常见路径的排除项
        if self.exclude_careers_check.isChecked():
            exclude_rules.append(FilterRule(pattern="^/careers"))

        if self.exclude_news_check.isChecked():
            exclude_rules.append(FilterRule(pattern="newsroom"))
            exclude_rules.append(FilterRule(pattern="/news"))

        if self.exclude_admin_check.isChecked():
            exclude_rules.append(FilterRule(pattern="^/admin"))
            exclude_rules.append(FilterRule(pattern="/login"))

        # max_urls：如果已有配置中有更大的值，优先保留更大者
        existing_max = base_config.filters.max_urls if base_config else 0
        max_urls = max(existing_max or 0, 5000)

        filters = FiltersConfig(
            include=include_rules,
            exclude=exclude_rules,
            max_urls=max_urls,
            auto_group=True,
            use_default_excludes=self.use_default_excludes_check.isChecked(),
            auto_filter_languages=self.auto_filter_lang_check.isChecked(),
            profiles=base_profiles,
            group_limits=base_group_limits,
            default_group_limit=base_default_group_limit,
        )

        # 构建输出配置：在已有配置基础上，允许通过 UI 覆盖输出路径
        if base_config is not None:
            base_output = base_config.output
        else:
            base_output = OutputConfig(
                llms_txt="llms.txt",
                llms_full_txt="llms-full.txt",
                llms_json="llms.json",
                sitemap_xml="sitemap.xml",
                sitemap_apply_filters=False,
            )

        def _norm_path(text: str | None) -> str | None:
            t = (text or "").strip()
            return t or None

        output = OutputConfig(
            llms_txt=_norm_path(self.llms_txt_input.text()) or base_output.llms_txt,
            llms_full_txt=_norm_path(self.llms_full_input.text())
            or base_output.llms_full_txt,
            llms_json=_norm_path(self.llms_json_input.text())
            or base_output.llms_json,
            sitemap_xml=_norm_path(self.sitemap_xml_input.text())
            or base_output.sitemap_xml,
            sitemap_index=_norm_path(self.sitemap_index_input.text())
            or base_output.sitemap_index,
            sitemap_apply_filters=base_output.sitemap_apply_filters,
            generate_full_text=base_output.generate_full_text,
        )

        app_config = AppConfig(
            site=site, sources=sources, filters=filters, output=output
        )

        # 在 AppConfig 上挂一个 GUI 专用的动态属性，用于控制是否自动根据 sitemap 发现子域
        # 这样不会破坏现有的配置文件结构，但爬虫层可以检测到这个开关。
        setattr(
            app_config,
            "enable_auto_subdomains",
            bool(self.auto_subdomains_check.isChecked()),
        )

        # 添加用户选择的子域名（如果有）
        selected_subdomains = self.get_selected_subdomains()
        if selected_subdomains:
            setattr(
                app_config,
                "selected_subdomains",
                selected_subdomains,
            )

        return app_config

    def collect_urls(self):
        """收集 URL"""
        try:
            self.config = self.build_config_from_ui()
            # 验证配置：确保至少有一个数据源
            if not self.config.sources:
                QMessageBox.warning(
                    self,
                    "Configuration Error / 配置错误",
                    "No data sources configured. Please fill in at least one of:\n"
                    "未配置数据源。请至少填写以下一项：\n\n"
                    "- Sitemap URL（推荐）\n"
                    "- Crawl Start URL\n"
                    "- Static URLs",
                )
                return
        except ValueError as e:
            QMessageBox.warning(
                self,
                "Configuration Error / 配置错误",
                f"Cannot build configuration / 无法构建配置:\n{e}",
            )
            return
        except Exception as e:
            QMessageBox.warning(
                self,
                "Configuration Error / 配置错误",
                f"Unexpected error / 意外错误:\n{e}",
            )
            return

        self.collect_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # 不确定进度

        # 启动后台线程
        self.collection_thread = URLCollectionThread(self.config)
        self.collection_thread.progress.connect(self.on_progress)
        self.collection_thread.finished.connect(self.on_urls_collected)
        self.collection_thread.error.connect(self.on_error)
        self.collection_thread.start()

    def on_progress(self, message: str):
        self.stats_label.setText(message)

    def on_urls_collected(self, urls: List[str], failed_urls: List[dict]):
        self.all_urls = urls
        self.failed_urls = failed_urls  # Store failed URLs for export
        self.collect_btn.setEnabled(True)
        self.progress_bar.setVisible(False)

        # 启用/禁用导出死链按钮
        if hasattr(self, "export_dead_links_btn"):
            self.export_dead_links_btn.setEnabled(bool(failed_urls))

        if not urls:
            QMessageBox.warning(
                self,
                "No URLs Collected / 未收集到 URL",
                "No URLs were collected from the configured sources.\n"
                "未从配置的数据源收集到任何 URL。\n\n"
                "Possible reasons / 可能的原因：\n"
                "1. Sitemap URL is incorrect or inaccessible\n"
                "   Sitemap URL 不正确或无法访问\n"
                "2. Crawl Start URL is invalid or blocked\n"
                "   Crawl Start URL 无效或被阻止\n"
                "3. Allowed domains are too restrictive\n"
                "   允许的域名限制过于严格\n"
                "4. Network connectivity issues\n"
                "   网络连接问题\n\n"
                "Please check your configuration and try again.",
            )
            return

        # Show warning if there are failed URLs (404s, etc.)
        if failed_urls:
            dead_links_count = len(
                [u for u in failed_urls if u.get("status_code") == 404]
            )
            QMessageBox.information(
                self,
                "URL Collection Complete / URL 收集完成",
                f"Successfully collected {len(urls)} URLs.\n"
                f"成功收集 {len(urls)} 个 URL。\n\n"
                f"Found {len(failed_urls)} failed URLs ({dead_links_count} are 404 dead links).\n"
                f"发现 {len(failed_urls)} 个失败的 URL（其中 {dead_links_count} 个是 404 死链）。\n\n"
                f"You can export the failed URLs using 'Export Dead Links' button.\n"
                f"你可以使用'导出死链'按钮导出失败的 URL。",
            )

        # 应用过滤
        self.apply_filters()

    def on_error(self, error_msg: str):
        self.collect_btn.setEnabled(True)
        self.progress_bar.setVisible(False)

        # 提供针对常见错误的友好提示
        detailed_msg = error_msg
        if (
            "not well-formed" in error_msg.lower()
            or "invalid token" in error_msg.lower()
        ):
            detailed_msg = (
                f"{error_msg}\n\n"
                "The sitemap XML appears to be malformed. / Sitemap XML 格式不正确。\n\n"
                "Possible solutions / 可能的解决方案：\n"
                "1. Check if the sitemap URL is correct / 检查 sitemap URL 是否正确\n"
                "2. The sitemap might contain invalid characters / sitemap 可能包含无效字符\n"
                "3. Try disabling sitemap and use crawling instead / 尝试禁用 sitemap，改用爬取\n\n"
                "Tip: You can leave the sitemap field empty and the tool will crawl from the homepage.\n"
                "提示：可以将 sitemap 字段留空，工具将自动从首页开始爬取。"
            )
        elif "404" in error_msg or "not found" in error_msg.lower():
            detailed_msg = (
                f"{error_msg}\n\n"
                "The sitemap URL returned 404. / Sitemap URL 返回 404。\n\n"
                "The tool will automatically crawl from the homepage instead.\n"
                "工具将自动从首页开始爬取。"
            )

        QMessageBox.critical(
            self,
            "Collection Error / 收集错误",
            f"Error collecting URLs / 收集 URL 时出错:\n\n{detailed_msg}",
        )

    def apply_filters(self):
        """应用过滤规则"""
        if not self.config:
            return

        try:
            self.filtered_pages = filter_and_group_urls(self.config, self.all_urls)
        except Exception as e:
            QMessageBox.warning(self, "过滤错误", f"应用过滤规则时出错: {e}")
            return

        # 更新统计信息
        total = len(self.all_urls)
        filtered = len(self.filtered_pages)
        self.stats_label.setText(
            f"总 URL 数: {total} | 过滤后: {filtered} | 排除: {total - filtered}"
        )

        # 更新分组树
        self.update_group_tree()

        # 更新 URL 列表
        self.update_url_list()

        self.generate_btn.setEnabled(True)

    def update_group_tree(self):
        """更新分组树形视图"""
        self.group_tree.clear()
        self.group_tree.itemChanged.disconnect()  # 临时断开信号，避免触发过滤

        from collections import defaultdict

        groups = defaultdict(list)
        for page in self.filtered_pages:
            groups[page.group].append(page)

        self.group_items = {}  # 存储分组项，用于快速查找
        for group_name, pages in sorted(groups.items()):
            item = QTreeWidgetItem(self.group_tree)
            item.setText(0, group_name)
            item.setText(1, str(len(pages)))
            item.setCheckState(0, Qt.Checked)
            item.setData(0, Qt.UserRole, group_name)
            self.group_items[group_name] = item

        self.group_tree.itemChanged.connect(self.on_group_item_changed)  # 重新连接信号

    def update_url_list(self):
        """更新 URL 列表（只显示已勾选的分组）"""
        if not self.filtered_pages or not hasattr(self, "group_items"):
            self.url_list.clear()
            return

        # 获取已勾选的分组
        checked_groups = set()
        for group_name, item in self.group_items.items():
            if item.checkState(0) == Qt.Checked:
                checked_groups.add(group_name)

        # 过滤出已勾选分组的 URL
        filtered_urls = [
            page.url for page in self.filtered_pages if page.group in checked_groups
        ]

        # 只显示前 100 个
        display_urls = filtered_urls[:100]
        self.url_list.setPlainText("\n".join(display_urls))
        if len(filtered_urls) > 100:
            self.url_list.append(f"\n... 还有 {len(filtered_urls) - 100} 个 URL")

    def on_group_item_changed(self, item: QTreeWidgetItem, column: int):
        """分组项状态改变"""
        if column != 0:
            return

        group_name = item.data(0, Qt.UserRole)
        is_checked = item.checkState(0) == Qt.Checked

        # 更新 URL 列表显示（只显示已勾选的分组）
        self.update_url_list()

        # 更新统计信息
        self.update_stats()

    def update_stats(self):
        """更新统计信息"""
        if not hasattr(self, "group_items"):
            return

        checked_groups = set()
        for group_name, item in self.group_items.items():
            if item.checkState(0) == Qt.Checked:
                checked_groups.add(group_name)

        # 统计已勾选分组的 URL 数量
        checked_count = sum(
            len([p for p in self.filtered_pages if p.group == g])
            for g in checked_groups
        )

        total = len(self.all_urls)
        filtered = len(self.filtered_pages)
        self.stats_label.setText(
            f"总 URL 数: {total} | 过滤后: {filtered} | 已选分组: {checked_count} 个 URL"
        )

    def _set_all_groups_checked(self, checked: bool):
        """内部工具：批量勾选 / 取消勾选所有分组"""
        if not hasattr(self, "group_items"):
            return
        # 暂时断开信号，避免对每个分组都单独触发一次过滤
        try:
            self.group_tree.itemChanged.disconnect()
        except Exception:
            # 如果本来就没连接，不必报错
            pass

        state = Qt.Checked if checked else Qt.Unchecked
        for item in self.group_items.values():
            item.setCheckState(0, state)

        # 重新连接信号并刷新统计/UI
        self.group_tree.itemChanged.connect(self.on_group_item_changed)
        self.update_url_list()
        self.update_stats()

    def select_all_groups(self):
        """一键全选所有分组"""
        self._set_all_groups_checked(True)

    def deselect_all_groups(self):
        """一键取消选择所有分组"""
        self._set_all_groups_checked(False)

    def export_dead_links(self):
        """导出死链（404等失败的URL）"""
        if not hasattr(self, "failed_urls") or not self.failed_urls:
            QMessageBox.information(
                self,
                "No Dead Links / 无死链",
                "No failed URLs to export.\n没有失败的 URL 需要导出。",
            )
            return

        # 选择保存文件
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Dead Links / 导出死链",
            str(Path.cwd() / "dead_links.txt"),
            "Text Files (*.txt);;CSV Files (*.csv);;All Files (*)",
        )
        if not file_path:
            return

        try:
            # 根据文件扩展名决定格式
            is_csv = file_path.lower().endswith(".csv")

            with open(file_path, "w", encoding="utf-8") as f:
                if is_csv:
                    f.write("URL,Status Code,Error Message\n")
                    for item in self.failed_urls:
                        url = item.get("url", "")
                        status = item.get("status_code", "N/A")
                        error = item.get("error", "").replace(",", ";")
                        f.write(f"{url},{status},{error}\n")
                else:
                    f.write("# Dead Links / 死链列表\n")
                    f.write(f"# Generated by LLMS Sitemap Generator\n")
                    f.write(f"# Total: {len(self.failed_urls)} failed URLs\n\n")

                    # 按状态码分组
                    by_status = {}
                    for item in self.failed_urls:
                        status = item.get("status_code", "Unknown")
                        if status not in by_status:
                            by_status[status] = []
                        by_status[status].append(item)

                    for status in sorted(
                        by_status.keys(), key=lambda x: (x is None, x)
                    ):
                        items = by_status[status]
                        f.write(
                            f"\n## Status {status if status else 'Unknown'} ({len(items)} URLs)\n\n"
                        )
                        for item in items:
                            url = item.get("url", "")
                            error = item.get("error", "")
                            f.write(f"{url}\n")
                            if error:
                                f.write(f"  Error: {error}\n")

            QMessageBox.information(
                self,
                "Export Successful / 导出成功",
                f"Exported {len(self.failed_urls)} dead links to:\n"
                f"导出 {len(self.failed_urls)} 个死链到：\n\n"
                f"{file_path}",
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Export Failed / 导出失败",
                f"Failed to export dead links:\n{e}\n\n导出死链失败：\n{e}",
            )

    def generate_output(self):
        """生成输出文件"""
        if not self.config or not self.all_urls:
            QMessageBox.warning(
                self,
                "配置错误",
                "请先点击“收集 URL / Collect URLs”完成 URL 收集，再生成 llms.txt。",
            )
            return

        # 获取已勾选的分组
        checked_groups = None
        if hasattr(self, "group_items"):
            checked_groups = [
                group_name
                for group_name, item in self.group_items.items()
                if item.checkState(0) == Qt.Checked
            ]
            if not checked_groups:
                QMessageBox.warning(self, "未选择分组", "请至少选择一个分组")
                return

        try:
            output_path = Path("llms.txt")
            # 从下拉框读取 profile（minimal / recommended / full）
            profile = None
            if hasattr(self, "profile_combo"):
                profile = self.profile_combo.currentData()
                if not profile:
                    profile = None

            # GUI 默认以「快速模式」生成：不抓取页面内容，只复用前面已经收集好的 URL，
            # 避免再次触发爬虫，大幅缩短在大站点上的生成时间。
            max_pages = None
            if hasattr(self, "generate_max_pages_spin"):
                val = int(self.generate_max_pages_spin.value())
                if val > 0:
                    max_pages = val

            generate_llms_from_urls(
                self.config,
                self.all_urls,
                output_path,
                fetch_content=False,
                profile=profile,
                only_groups=checked_groups if checked_groups else None,
                max_pages=max_pages,
            )
            QMessageBox.information(
                self,
                "生成成功",
                f"已生成以下文件:\n"
                f"- llms.txt\n"
                f"- llms-full.txt\n"
                f"- llms.json\n"
                f"- sitemap.xml\n\n"
                f"保存位置: {output_path.parent.absolute()}",
            )
        except Exception as e:
            QMessageBox.critical(self, "生成失败", f"生成时出错: {e}")

    def load_config_file(self):
        """加载配置文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Configuration File",
            str(Path.cwd()),
            "YAML Files (*.yml *.yaml);;All Files (*)",
        )
        if not file_path:
            return

        try:
            config = load_config(Path(file_path))
            self.config = config

            # ------- 更新 UI：站点配置 -------
            self.base_url_input.setText(config.site.base_url)
            self.default_lang_input.setText(config.site.default_language)
            self.site_desc_edit.setPlainText(config.site.description or "")

            # ------- 数据源 -------
            if config.sources:
                # sitemap 源
                sitemap_source = next(
                    (s for s in config.sources if s.type == "sitemap"), None
                )
                if sitemap_source:
                    self.sitemap_url_input.setText(sitemap_source.url)
                else:
                    # 显示第一个数据源的URL
                    self.sitemap_url_input.setText(config.sources[0].url)

                # crawl 源（例如文档或 blog）
                crawl_source = next(
                    (s for s in config.sources if s.type == "crawl"), None
                )
                if crawl_source:
                    self.crawl_url_input.setText(crawl_source.url or "")
                    if crawl_source.max_depth is not None:
                        self.crawl_depth_spin.setValue(int(crawl_source.max_depth))
                    if crawl_source.max_urls is not None:
                        self.crawl_max_urls_spin.setValue(int(crawl_source.max_urls))
                else:
                    self.crawl_url_input.clear()

                # static 源：仅展示第一个 static 的 URL 列表
                static_source = next(
                    (s for s in config.sources if s.type == "static"), None
                )
                if static_source and static_source.urls:
                    self.static_urls_edit.setPlainText("\n".join(static_source.urls))
                else:
                    self.static_urls_edit.clear()
            else:
                self.sitemap_url_input.clear()
                self.crawl_url_input.clear()
                self.static_urls_edit.clear()

            # ------- 过滤规则 -------
            self.auto_filter_lang_check.setChecked(config.filters.auto_filter_languages)
            self.use_default_excludes_check.setChecked(
                config.filters.use_default_excludes
            )

            # 检查是否有 blog / careers / news / admin 等排除规则
            has_blog_exclude = any(
                "blog" in r.pattern.lower() and r.pattern.startswith("^/blog")
                for r in config.filters.exclude
            )
            self.exclude_blog_check.setChecked(has_blog_exclude)

            has_careers_exclude = any(
                r.pattern.startswith("^/careers") for r in config.filters.exclude
            )
            self.exclude_careers_check.setChecked(has_careers_exclude)

            has_news_exclude = any(
                ("newsroom" in r.pattern) or ("/news" in r.pattern)
                for r in config.filters.exclude
            )
            self.exclude_news_check.setChecked(has_news_exclude)

            has_admin_exclude = any(
                r.pattern.startswith("^/admin") or ("/login" in r.pattern)
                for r in config.filters.exclude
            )
            self.exclude_admin_check.setChecked(has_admin_exclude)

            # ------- Profile 下拉：根据配置中的 profiles 动态填充 -------
            self.profile_combo.clear()
            self.profile_combo.addItem("Auto（按配置文件或默认策略）", "")
            if config.filters.profiles:
                for name in sorted(config.filters.profiles.keys()):
                    self.profile_combo.addItem(name, name)
                # 如果有 recommended，优先选它
                idx = self.profile_combo.findData("recommended")
                if idx != -1:
                    self.profile_combo.setCurrentIndex(idx)

            # ------- 输出配置 -------
            # 如果配置中已有输出设置，则填充到 UI
            if config.output:
                if hasattr(self, "llms_txt_input"):
                    self.llms_txt_input.setText(config.output.llms_txt or "llms.txt")
                if hasattr(self, "llms_full_input"):
                    self.llms_full_input.setText(
                        config.output.llms_full_txt or "llms-full.txt"
                    )
                if hasattr(self, "llms_json_input"):
                    self.llms_json_input.setText(
                        config.output.llms_json or "llms.json"
                    )
                if hasattr(self, "sitemap_xml_input"):
                    self.sitemap_xml_input.setText(
                        config.output.sitemap_xml or "sitemap.xml"
                    )
                if hasattr(self, "sitemap_index_input"):
                    self.sitemap_index_input.setText(
                        config.output.sitemap_index or "sitemap_index.xml"
                    )

            # 显示更详细的信息
            sources_info = "\n".join(
                [f"  - {s.type}: {s.url}" for s in config.sources[:3]]
            )
            if len(config.sources) > 3:
                sources_info += f"\n  ... and {len(config.sources) - 3} more"

            QMessageBox.information(
                self,
                "Configuration Loaded",
                f"Successfully loaded: {Path(file_path).name}\n\n"
                f"Base URL: {config.site.base_url}\n"
                f"Allowed Domains: {len(config.site.allowed_domains)}\n"
                f"Data Sources: {len(config.sources)}\n"
                f"{sources_info}\n\n"
                f"Click 'Collect URLs' to start.",
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Load Failed",
                f"Cannot load configuration file:\n{file_path}\n\nError: {e}\n\n"
                f"Please check the file format and try again.",
            )

    def save_config_file(self):
        """保存配置文件"""
        try:
            config = self.build_config_from_ui()
        except Exception as e:
            QMessageBox.warning(
                self, "Configuration Error", f"Cannot build configuration: {e}"
            )
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Configuration File",
            str(Path.cwd() / "llmstxt.config.yml"),
            "YAML Files (*.yml *.yaml);;All Files (*)",
        )
        if not file_path:
            return

        if yaml is None:
            QMessageBox.critical(
                self,
                "Missing Dependency",
                "PyYAML is not installed. Cannot save configuration file.\n\n"
                "Please run: pip install PyYAML",
            )
            return

        try:
            from urllib.parse import urlparse

            # 构建配置字典
            config_dict = {
                "site": {
                    "base_url": config.site.base_url,
                    "default_language": config.site.default_language,
                    "allowed_domains": config.site.allowed_domains,
                },
                "sources": [
                    {
                        "type": src.type,
                        "url": src.url,
                        "max_depth": src.max_depth if src.max_depth else None,
                        "max_urls": src.max_urls if src.max_urls else None,
                        "urls": src.urls if src.urls else None,
                    }
                    for src in config.sources
                    if any([src.type, src.url, src.urls])
                ],
                "filters": {
                    "exclude": [{"pattern": r.pattern} for r in config.filters.exclude],
                    "auto_filter_languages": config.filters.auto_filter_languages,
                    "max_urls": config.filters.max_urls,
                    "auto_group": config.filters.auto_group,
                    "use_default_excludes": config.filters.use_default_excludes,
                },
                "output": {
                    "llms_txt": config.output.llms_txt,
                    "llms_full_txt": config.output.llms_full_txt,
                    "llms_json": config.output.llms_json,
                    "sitemap_xml": config.output.sitemap_xml,
                    "sitemap_apply_filters": config.output.sitemap_apply_filters,
                },
            }

            # 移除None值
            def remove_none(d):
                if isinstance(d, dict):
                    return {k: remove_none(v) for k, v in d.items() if v is not None}
                elif isinstance(d, list):
                    return [remove_none(item) for item in d if item is not None]
                return d

            config_dict = remove_none(config_dict)

            with open(file_path, "w", encoding="utf-8") as f:
                yaml.dump(
                    config_dict,
                    f,
                    allow_unicode=True,
                    default_flow_style=False,
                    sort_keys=False,
                )

            QMessageBox.information(
                self,
                "Configuration Saved",
                f"Configuration saved successfully:\n{file_path}\n\n"
                f"You can now:\n"
                f"1. Edit the file manually if needed\n"
                f"2. Load it again using 'Load Config' button\n"
                f"3. Use it with CLI: llms-sitemap-generator generate -c {Path(file_path).name}",
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Save Failed",
                f"Cannot save configuration file:\n{file_path}\n\nError: {e}",
            )


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
