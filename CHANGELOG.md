# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Build & Packaging Fixes (Latest)

#### EXE Build Fix
- **Fixed PyInstaller Relative Import Error**: Resolved "attempted relative import with no known parent package" error
  - Created `gui_entry.py` as a dedicated entry point for PyInstaller builds
  - Handles both normal execution and PyInstaller bundled execution
  - Uses absolute imports to avoid relative import issues
  - Updated `build_exe.py` to use `gui_entry.py` instead of `__main__.py`
  - Updated `BUILD_EXE.md` and `BUILD_EXE_CN.md` with troubleshooting guide

### Universalization & Quality Improvements

#### Universalization
- **Removed Hardcoded Site Names**: All site-specific references removed
  - Description generation now dynamically extracts site name from URL
  - Works for any website, not just specific sites
  - Improved generic description fallback logic
- **Generalized Content Discovery**: Auto-discovery of common content sections
  - Automatically detects and adds crawl sources for blog, docs, documentation
  - Configurable and works for any website structure
  - Removed hardcoded blog-specific logic

#### Quality Improvements
- **Enhanced Description Extraction**: Improved HTML parsing and content extraction
  - Better extraction of meta descriptions, paragraphs, and main content
  - Fallback to meaningful descriptions when meta tags are missing
  - Output format matches oxylabs.io/llms.txt standard
- **Fixed Language Filtering Logic**: Proper separation of llms.txt and sitemap.xml
  - `llms.txt` only includes default language (English) for LLM training
  - `sitemap.xml` includes all languages for SEO purposes
  - `sitemap_index.xml` also includes all languages
- **Improved Blog Crawling**: Better blog article collection
  - Fixed blog pagination link extraction (filters out className/page errors)
  - Increased blog priority in crawler
  - Higher blog group limits (500) to collect all articles

#### Code Quality
- **Generalized Comments**: Updated all code comments and examples
  - Removed site-specific references
  - Universal examples work for any website
  - Better documentation for all website types

### GUI & Output Format Enhancements

#### GUI Improvements
- **Site Description Input**: Added optional Site Description field in GUI
  - Users can input a brief description of their site
  - Description appears as Site Overview in llms.txt 
  - Supports multi-line text with proper formatting
- **Real-time Progress Feedback**: Enhanced URL collection progress display
  - Shows real-time URL count during collection
  - Better status messages for each operation phase
- **Configuration Loading Enhancement**: Improved config file loading
  - Automatically populates Site Description, Crawl URL, depth, and max URLs from saved config
  - More informative success messages with loaded config details

#### Output Format Optimization
- **Simplified Title Format**: Changed from `# {url} llms.txt` to `# {url}` 
- **Quoted Site Overview**: Site Overview now uses `> ` quote format (markdown blockquote style)
  - Multi-line descriptions properly formatted
  - More visually appealing and professional
- **Removed Redundant Groups Overview**: Removed "Groups Overview" statistics section
  - Directly shows grouped content (cleaner output)
content-focused approach

#### Smart Grouping Enhancements
- **Extended Category Recognition**: Added support for more B2B SaaS categories
  - Legal, Careers, Press, Partners, Datasets, SERP, Scrapers, Proxies
- **Optimized Group Weights**: Improved importance scoring
  - Products > Pricing > Docs > Proxies > Scrapers > Blog (B2B SaaS priority)
  - More accurate page ranking for business sites

#### Code Quality
- **Configuration Persistence**: Site Description now properly saved/loaded in config files
- **Better Error Handling**: Improved error messages and user feedback
- **Code Consistency**: Unified approach to config management

### Optimization & Code Quality Improvements

#### Code Quality
- **Unified Logging System**: Replaced all `print()` statements with standard `logging` module
  - Created `logger.py` for centralized logging configuration
  - All modules now use `logger.info()`, `logger.warning()`, `logger.error()`
  - Better control over log levels and debugging
- **Test Fixes**: Fixed pytest warnings about test functions returning values
  - Changed all test functions to use `assert` instead of `return True/False`
  - All tests now pass without warnings
- **Code Cleanup**: Improved error handling and code consistency

#### Performance
- Test execution time improved by ~57% (from 205s to 88s)
- Better error messages and logging for debugging

### Major: Complete GUI Redesign - Simplified & Smart Interface

**New Simplified GUI** (`gui_simple.py`):
- **User-friendly design**: Users only need to input URL, toggle switches, select options, and adjust numbers
- **Step-by-step interface**: Clear workflow from URL input to file generation
- **Smart defaults**: Pre-configured sensible values for most websites
- **Auto-detection**: Automatically finds sitemap and suggests optimal settings
- **Visual controls**: 
  - Toggle switches for boolean options
  - Dropdown menus for choices (language, output size)
  - Sliders for numeric values (crawl depth, max URLs)
- **Advanced options in tabs**: Complex settings hidden but accessible
- **All roadmap outputs available**: llms.txt, llms-full.txt, llms.json, sitemap.xml, sitemap_index.xml

### Fixed
- **URL Deduplication**: Fixed handling of trailing slashes
  - `https://example.com/page` and `https://example.com/page/` are now correctly treated as duplicates
  - Deduplication happens at collection stage with proper normalization
  - Better logging shows duplicate removal statistics
- **Critical Bug Fix**: Fixed issue where GUI would return zero URLs when only Base URL was filled in
  - Now automatically adds default sitemap and crawl sources if user only provides Base URL
  - Ensures at least one data source is always configured
  - Improved error messages with bilingual (EN/ZH) support
- Fixed GUI not respecting user-provided base URL (was hardcoded to thordata.com)
  - Added root domain detection to automatically reset config when switching sites
  - Prevents mixing domains from different sites

### Added
- **Bilingual GUI (EN/ZH)**: Complete English-first interface with Chinese tooltips
  - All labels, buttons, and messages now support bilingual display
  - English as primary language for global users
  - Chinese tooltips and hints for Chinese-speaking users
- **Group Selection UX**: Added "Select All Groups" and "Deselect All Groups" buttons
  - One-click selection/deselection of all URL groups
  - Improved workflow for large sites with many groups
- **Auto Subdomain Discovery**: Optional feature to automatically discover subdomains from sitemap
  - Similar to crt.sh functionality but based on site's own sitemap
  - Automatically adds discovered subdomains to allowed_domains and sources
  - Can be enabled/disabled via GUI checkbox
- Enhanced logging and progress feedback
  - Shows URL count collected from each source
  - Better error messages when no URLs are collected
  - More informative warnings and info messages

### Improved
- Better error handling in URL collection process
  - Graceful fallback when subdomain discovery fails
  - Clear error messages when sources are empty
  - Validation before starting URL collection
- Code quality and maintainability
  - Cleaner code structure
  - Better separation of concerns
  - Improved documentation

## [0.1.0] - 2026-02-10

### Added

#### Configuration Validator
- Complete configuration validation system
- URL, domain, and language code format validation
- Configuration file structure completeness checks
- User-friendly error messages and fix suggestions
- CLI support for `--no-validate` option (not recommended)
- Test suite covering all validation rules

#### Testing and Validation
- Integration test suite (`tests/test_integration.py`)
- Real URL collection and filtering tests
- Testing guide documentation (`docs/testing-guide.md`)

#### GUI Tool
- Complete visual GUI tool (based on PyQt5)
- Interactive configuration panel (site config, data sources, filter rules)
- URL grouping tree view (checkable, real-time filtering)
- Build configuration object from UI
- Configuration file load/save functionality
- Real-time preview of filtering results and statistics
- CLI command `llms-sitemap-generator gui` to launch GUI
- Background thread for URL collection (non-blocking UI)
- Progress bar display and error handling

#### Core Features
- Python CLI tool skeleton
- URL collection from sitemap and crawler
- Apply include/exclude rules
- Automatic grouping by path segments
- Basic summary extraction based on HTML meta tags
- URL importance scoring and per-group top-N truncation
- Generate standard `sitemap.xml` and `sitemap_index.xml`
- Site overview and group statistics
- Intelligent title cleaning
- Automatic multi-language detection and filtering
- URL deduplication
- Built-in default exclusion rules
- User-friendly `init` template

#### Core Feature Optimizations
- Separated sitemap.xml and llms.txt generation strategies
  - `sitemap.xml` defaults to include all URLs (all languages and blog) for SEO
  - `llms.txt` only includes filtered curated URLs (default language only, excludes blog) for LLM
- Added `sitemap_apply_filters` configuration option
- Fixed page counting issue (count after deduplication)
- Added `auto_filter_languages` configuration option
- Optimized group_limits default values

### Changed

- Improved error handling and user prompts
- Optimized configuration file load/save logic
- Updated code comments to English
- Repository internationalization (English as primary, Chinese as secondary)

### Documentation

- Created `docs/gui-usage.md` (GUI usage guide)
- Created `docs/testing-guide.md` (testing guide)
- Created `docs/validation.md` (configuration validation documentation)
- Updated `docs/roadmap.md` (marked completed features)
- Updated `README.md` (added GUI usage instructions)
- Created `BUILD_EXE.md` and `BUILD_EXE_CN.md` (build guides)

### Tools and Scripts

- Created `build_exe.py` (PyInstaller build script)
- Created `requirements-gui.txt` (GUI dependencies list)
- Created `tests/test_gui.py` (GUI test script)
- Created `tests/test_validators.py` (validator test script)
