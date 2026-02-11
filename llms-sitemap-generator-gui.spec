# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules
from PyInstaller.utils.hooks import collect_all

datas = []
binaries = []
hiddenimports = ['llms_sitemap_generator', 'llms_sitemap_generator.cli', 'llms_sitemap_generator.config', 'llms_sitemap_generator.crawler', 'llms_sitemap_generator.filters', 'llms_sitemap_generator.generator', 'llms_sitemap_generator.gui_main', 'llms_sitemap_generator.html_summary', 'llms_sitemap_generator.logger', 'llms_sitemap_generator.site_analyzer', 'llms_sitemap_generator.sitemap', 'llms_sitemap_generator.subdomain_discovery', 'llms_sitemap_generator.url_utils', 'llms_sitemap_generator.validators', 'yaml', 'yaml.cyaml', 'requests', 'requests.packages.urllib3', 'charset_normalizer', 'idna']
hiddenimports += collect_submodules('PyQt5')
tmp_ret = collect_all('PyQt5')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['D:\\thordata_work\\llms-sitemap-generator\\src\\llms_sitemap_generator\\gui_entry.py'],
    pathex=['D:\\thordata_work\\llms-sitemap-generator\\src'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='llms-sitemap-generator-gui',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='NONE',
)
