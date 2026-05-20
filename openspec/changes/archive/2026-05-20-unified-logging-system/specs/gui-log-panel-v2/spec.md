## ADDED Requirements

### Requirement: BottomPanel displays a unified "Console" source
The system SHALL add a synthetic log source named "控制台" (or "Console") to `BottomPanel` that aggregates all backend logs coming through `InterceptHandler`.

#### Scenario: User switches to Console source
- **WHEN** the user opens the source dropdown in `BottomPanel` and selects "控制台"
- **THEN** all backend logs (including those from `logging`), grouped by original logger name, SHALL be displayed

### Requirement: Search and filter in BottomPanel
The system SHALL add a persistent text search field to `BottomPanel` that filters log entries case-insensitively across message text and source name.

#### Scenario: User searches for an error keyword
- **WHEN** the user types "error" into the search field
- **THEN** the panel SHALL display only log entries whose message or source contains "error" (case-insensitive)
- **AND** the count of matched entries SHALL be shown next to the search field

#### Scenario: Combined source + level + text filter
- **WHEN** the user selects source "perfetto_capture", level "error", and types "timeout"
- **THEN** the panel SHALL display exactly the intersection of all three filters

### Requirement: Export visible log entries
The system SHALL provide an "导出" button in `BottomPanel` that exports the currently visible (filtered) log entries to a user-selected `.log` file.

#### Scenario: User exports filtered results
- **WHEN** the user applies a filter (source + search) and clicks "导出"
- **THEN** a file dialog SHALL appear and, upon confirmation, write all currently visible entries in chronological order using the same format as the terminal sink

### Requirement: Structured field expansion in GUI
The system SHALL display structured log fields as a collapsible detail view in each log row.

#### Scenario: User expands a structured log entry
- **WHEN** a log entry contains extra fields (from `logger.bind(...)`)
- **THEN** a small expand icon SHALL appear on the row
- **AND** clicking it SHALL reveal all extra fields as a neatly formatted key-value list

### Requirement: Performance guarantees for large log volumes
The system SHALL ensure that `BottomPanel` remains performant when `LogManager` holds the full 5000-entry history.

#### Scenario: Panel shows full history
- **WHEN** 5000 log entries are loaded into `BottomPanel`
- **THEN** scrolling, filtering, and searching SHALL complete within 100 ms per operation
- **AND** memory usage SHALL not exceed a reasonable bound due to retained QTextDocument content
