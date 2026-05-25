# base-history-tree Specification

## Purpose
TBD - created by archiving change refactor-history-panel. Update Purpose after archive.
## Requirements
### Requirement: BaseHistoryTreeWidget provides common context menu

`BaseHistoryTreeWidget` SHALL provide a configurable right-click context menu framework. Subclasses SHALL register menu actions via a declarative API, and the base class SHALL handle menu rendering and theme styling.

#### Scenario: Subclass registers custom context menu actions
- **WHEN** a subclass calls `self._register_context_action("📂 打开所在目录", self._on_open_directory)` during initialization
- **THEN** right-clicking on a tree item displays the registered action in the context menu

#### Scenario: Context menu theme matches application theme
- **WHEN** the context menu is opened in dark theme
- **THEN** menu background uses `theme_colors.get_colors()["dark"]` colors
- **WHEN** the context menu is opened in light theme
- **THEN** menu background uses `theme_colors.get_colors()["light"]` colors

#### Scenario: Context menu supports conditional actions
- **WHEN** the user right-clicks on a tree item
- **THEN** each registered action's visibility callback is evaluated against the selected item's `UserRole` data
- **AND** actions whose callback returns `False` are hidden from the menu

### Requirement: BaseHistoryTreeWidget supports send-to-agent signal

`BaseHistoryTreeWidget` SHALL expose a `send_to_agent_requested` signal with a standardized payload format for sending file context to the Agent Chat panel.

#### Scenario: Build standard send payload for a file
- **WHEN** `_build_send_payload(file_path="/path/to/trace.perfetto-trace", context_type="trace")` is called
- **THEN** the returned dict contains `{"file_path": "/path/to/trace.perfetto-trace", "file_name": "trace.perfetto-trace", "context_type": "trace", "missing": false}`

#### Scenario: Missing file detected
- **WHEN** `_build_send_payload(file_path="/nonexistent/file", context_type="trace")` is called
- **THEN** the returned dict contains `"missing": true`

### Requirement: BaseHistoryTreeWidget supports keyword filtering

`BaseHistoryTreeWidget` SHALL provide a `filter_by_keyword(keyword, column)` method that shows/hides tree items based on case-insensitive substring matching.

#### Scenario: Filter hides non-matching items
- **WHEN** `filter_by_keyword("pixel", 0)` is called with a tree containing items "Pixel 7" and "Samsung S24"
- **THEN** the "Pixel 7" item is visible and the "Samsung S24" item is hidden

#### Scenario: Empty keyword shows all items
- **WHEN** `filter_by_keyword("", 0)` is called
- **THEN** all previously hidden items become visible again

### Requirement: BaseHistoryTreeWidget supports multi-selection

`BaseHistoryTreeWidget` SHALL support `ExtendedSelection` mode and provide `_get_selected_items_data()` to retrieve `UserRole` data for all selected items.

#### Scenario: Get data from multiple selected items
- **WHEN** user Ctrl-clicks three items in the tree
- **THEN** `_get_selected_items_data()` returns a list of three dicts, each containing the `UserRole` data of the corresponding item

### Requirement: BaseHistoryTreeWidget provides formatting utilities

`BaseHistoryTreeWidget` SHALL provide static utility methods `_format_size(bytes)` and `_format_time(datetime_or_str)` for consistent formatting across subclasses.

#### Scenario: Format file size in human-readable form
- **WHEN** `_format_size(1536000)` is called
- **THEN** it returns `"1.5 MB"`
- **WHEN** `_format_size(512)` is called
- **THEN** it returns `"512 B"`

### Requirement: Icons use codicon.ttf font system

All icons in tree items, context menu actions, and UI labels SHALL use the `codicon.ttf` font system provided by `toolkit/gui/codicons.py`. Unicode Emoji icons SHALL NOT be used.

#### Scenario: Tree item icon uses codicon
- **WHEN** a tree item displays a session folder icon
- **THEN** the icon character is obtained via `icon_char("folder")` from the codicon font, NOT the Unicode emoji "📁"

#### Scenario: Context menu action uses codicon
- **WHEN** a context menu action "打开所在目录" is created
- **THEN** the action text uses `icon_char("folder-opened")` as the icon prefix, NOT the Unicode emoji "📂"

#### Scenario: Status icons use codicon
- **WHEN** an analysis task tree displays task status
- **THEN** completed status uses `icon_char("check")` NOT "✅", failed status uses `icon_char("error")` NOT "❌", pending status uses `icon_char("watch")` NOT "⏳"

### Requirement: Subclasses inherit consistent tree styling

`BaseHistoryTreeWidget` SHALL apply base QTreeWidget styling via `theme_colors.get_colors()` so that all history trees have consistent appearance without hardcoded color values.

#### Scenario: Dark theme tree styling
- **WHEN** `set_theme("dark")` is called
- **THEN** the tree uses dark theme colors from `theme_colors.get_colors("dark")` for background, text, hover, and selection

