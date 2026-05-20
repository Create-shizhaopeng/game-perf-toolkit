## ADDED Requirements

### Requirement: UnifiedLogger provides a single logger interface
The system SHALL expose `UnifiedLogger` in `toolkit/core/unified_logger.py` as the single point of entry for all logging.

#### Scenario: Module emits a log message
- **WHEN** a module calls `logger.info("msg", key="val")` via `loguru`
- **THEN** the message SHALL reach all registered sinks (terminal, GUI, file)

#### Scenario: Legacy logging code continues to work
- **WHEN** a module calls `logging.getLogger(__name__).warning("msg")` (existing 61+ code)
- **THEN** the message SHALL be intercepted by `InterceptHandler` and forwarded into the `UnifiedLogger` pipeline without throwing

### Requirement: File sink supports rotation
The system SHALL persist logs to `data/logs/app_{date}.log` with daily rotation and automatic compression of old logs.

#### Scenario: Application runs across multiple days
- **WHEN** the app is launched on day N and day N+1
- **THEN** a new log file SHALL be created for each day and files older than 30 days SHALL be eligible for cleanup (or archived with compression)

#### Scenario: Log file reaches maximum size
- **WHEN** a single day's log exceeds a configurable size limit (default: 10 MB)
- **THEN** the file SHALL rotate intra-day with suffix numbering (e.g., `app_2026-05-20_001.log`)

### Requirement: GUISink bridges backend logs to GUI panel
The system SHALL include a non-blocking `GUISink` that forwards loguru records to `LogManager` (and thus to `BottomPanel`) without blocking the emitting thread.

#### Scenario: Backend error occurs while user is in GUI
- **WHEN** an unhandled exception in a worker thread triggers `logger.exception(...)`
- **THEN** the error SHALL appear in the GUI bottom panel within 300 ms

#### Scenario: High-frequency logging
- **WHEN** a module emits more than 100 log messages per second
- **THEN** the GUI thread SHALL remain responsive (no visible jank) because the GUISink uses a bounded queue with batch emission

### Requirement: Per-module file sinks
The system SHALL allow modules to register dedicated log files (opt-in) by module name.

#### Scenario: Perfetto analysis module registers its own sink
- **WHEN** `UnifiedLogger.add_module_sink("perfetto_analysis", level="INFO")` is called
- **THEN** all log records tagged with module="perfetto_analysis" SHALL also be written to `data/logs/perfetto_analysis_{date}.log`
