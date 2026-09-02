## ADDED Requirements

### Requirement: First-run portable data migration assistant
The system SHALL provide a first-run migration assistant that detects the transition from a legacy portable (zip) installation to the new installer distribution and offers to migrate user data from the old portable `data/` directory to the new three-tier paths. The assistant MUST be user-confirmed (not automatic), and MUST be skippable for fresh installs.

#### Scenario: Fresh install skips migration
- **WHEN** the new installer version starts for the first time and no migration marker exists and no old data is detected
- **THEN** the migration assistant does not appear and normal startup proceeds

#### Scenario: Migration assistant offers to migrate
- **WHEN** the new installer version starts and no migration marker exists
- **THEN** the assistant prompts the user to locate their old portable `Toolkit/` directory

### Requirement: User locates old portable directory
The migration assistant SHALL let the user specify the old portable installation directory via a directory picker. The assistant MUST NOT auto-scan or guess the location, to avoid migrating the wrong data. The user-selected directory is the source of truth for migration.

#### Scenario: User selects old portable directory
- **WHEN** the user clicks "Browse" in the migration dialog and selects a directory
- **THEN** the assistant validates that the directory contains a `data/` subdirectory before enabling the "Migrate" button

#### Scenario: Invalid directory rejected
- **WHEN** the user selects a directory without a `data/` subdirectory
- **THEN** the assistant shows an error and keeps the "Migrate" button disabled

### Requirement: Tier-mapped copy semantics
The migration SHALL copy (not move) user data from the old portable layout to the new three-tier paths using this mapping: `data/config/*.json` → config roaming; `data/db/*.db` → data local `db/`; `data/backup/` → data local `backup/`; `data/logs/` → skipped (logs not migrated); `output/trace/` → output `trace/`; `output/trace_report/` → output `trace_report/`. Existing files in the destination SHALL NOT be overwritten unless the source is newer.

#### Scenario: Config files migrated to roaming
- **WHEN** migration runs against an old directory containing `data/config/toolkit_config.json`
- **THEN** the file is copied to the config roaming root

#### Scenario: Database files migrated to local
- **WHEN** migration runs against an old directory containing `data/db/perfetto_capture_history.db`
- **THEN** the file is copied to the data local `db/` directory

#### Scenario: Trace output migrated to Documents
- **WHEN** migration runs against an old directory containing `output/trace/` with trace files
- **THEN** the trace files are copied to the output root's `trace/` subdirectory

#### Scenario: Logs are not migrated
- **WHEN** migration runs against an old directory containing `data/logs/`
- **THEN** the logs directory is skipped and no log files are copied

#### Scenario: Existing destination file preserved
- **WHEN** a destination file already exists and is newer than the source file
- **THEN** the source file is not copied over it

### Requirement: Migration marker prevents re-migration
After a successful migration (or explicit skip), the system SHALL write a marker file `config/.migrated_from_portable` containing the migration timestamp and source path. On subsequent launches, the presence of this marker SHALL suppress the migration assistant.

#### Scenario: Marker written after migration
- **WHEN** migration completes successfully
- **THEN** a `.migrated_from_portable` marker is written to the config roaming root

#### Scenario: Marker suppresses re-prompt
- **WHEN** the app launches and the marker file exists
- **THEN** the migration assistant does not appear

#### Scenario: Explicit skip writes marker
- **WHEN** the user clicks "Skip" in the migration dialog
- **THEN** the marker is written so the assistant does not reappear on next launch

### Requirement: Migration failure is non-fatal and retriable
If the migration copy fails partway (e.g., locked file, permission error), the system SHALL log the error, preserve already-copied files, write a partial-migration note, and allow the user to retry from the assistant. Migration failure MUST NOT block application startup.

#### Scenario: Partial migration on copy error
- **WHEN** a copy operation fails midway through the mapping
- **THEN** successfully copied files are kept, the error is logged, and the user can retry

#### Scenario: Startup proceeds despite migration failure
- **WHEN** migration fails and the user dismisses the error
- **THEN** the application starts normally with whatever data was already migrated
