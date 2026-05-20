## ADDED Requirements

### Requirement: Structured log events for analysis modules
The system SHALL provide `logger.bind()`-based structured logging primitives so that analysis modules (e.g., `perfetto_analysis`) can emit field-rich log events without manual string formatting.

#### Scenario: Engine emits an analysis completion event
- **WHEN** `perfetto_analysis` engine finishes analyzing a trace and calls `logger.bind(process="Game", fps=59.8, frame_time_ms=16.5).info("analysis_done")`
- **THEN** the terminal sink SHALL render a human-readable key-value format such as `analysis_done | process=Game fps=59.8 frame_time_ms=16.5`
- **AND** the file sink SHALL persist the complete structured record (including all bind fields)

### Requirement: Structured fields survive the bridge to GUI
The system SHALL propagate bind fields through `InterceptHandler` and `GUISink` so that `BottomPanel` can access and display them.

#### Scenario: User views a structured log in the GUI
- **WHEN** a structured log record reaches the `BottomPanel`
- **THEN** the panel SHALL display the base message and an expandable section containing all extra fields in key=value form

### Requirement: Trace correlation via trace_id field
The system SHALL support (and encourage) a `trace_id` bind field so that all logs related to a single trace analysis can be correlated.

#### Scenario: Multi-phase analysis logs
- **WHEN** `perfetto_analysis` begins a trace analysis and binds `trace_id="abc123"`
- **THEN** all subsequent log records from that analysis SHALL carry `trace_id="abc123"` until the context is reset or overwritten
- **AND** the GUI panel SHALL allow filtering logs by `trace_id`

### Requirement: Backward-compatible API for existing log calls
The system SHALL NOT require changes to existing `logger.info("message")` or `logging.getLogger(__name__).warning("msg")` calls.

#### Scenario: Existing non-structured code still logs
- **WHEN** a legacy module calls `logger.info("done")` without any bind fields
- **THEN** the log SHALL be forwarded normally with an empty extra-fields set
