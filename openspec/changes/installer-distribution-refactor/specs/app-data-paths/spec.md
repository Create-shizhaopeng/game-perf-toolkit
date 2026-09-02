## ADDED Requirements

### Requirement: Three-tier user data path resolution
The system SHALL resolve user data paths through a three-tier hierarchy using `platformdirs`: config layer (roaming, `%APPDATA%`), data layer (local, `%LOCALAPPDATA%` for db/logs/backup/cache), and output layer (Documents, user-configurable). The resolution MUST be identical in GUI and headless (MCP server) modes, without requiring a `QCoreApplication` instance.

#### Scenario: Config path resolves to roaming APPDATA
- **WHEN** any module requests a config file path via `get_config_path(module, filename)`
- **THEN** the resolved path is under `%APPDATA%\Roaming\lv-toolkit\LV Game Toolkit\` with the flattened name `<module>_<filename>`

#### Scenario: DB path resolves to local APPDATA
- **WHEN** any module requests a database path via `get_db_path(module, db_name)`
- **THEN** the resolved path is `%LOCALAPPDATA%\lv-toolkit\LV Game Toolkit\db\<module>_<db_name>.db`

#### Scenario: Output path resolves to Documents
- **WHEN** any module requests the output directory via `get_output_dir(module)`
- **THEN** the resolved path is under the configured output root (default `Documents\LV Game Toolkit`), with the module subdirectory created if absent

#### Scenario: Headless MCP server resolves paths identically to GUI
- **WHEN** the application runs as MCP server (`mcp-serve`) without a `QCoreApplication`
- **THEN** all path resolution returns appname-isolated paths identical to GUI mode

### Requirement: Stable path API surface
The system SHALL preserve the existing public function signatures of `get_config_path`, `get_db_path`, `get_output_dir`, and `get_backup_path` so that call sites using these wrappers require no changes. Internal implementations SHALL route through the three-tier roots instead of `get_exe_dir()`.

#### Scenario: Existing wrapped call sites keep working
- **WHEN** a module calls `get_config_path("llm_manager", "llm_providers.json")`
- **THEN** the function returns a path under the config roaming root with the same flattened-name semantics as before

### Requirement: get_exe_dir semantics narrowed to read-only program root
`get_exe_dir()` SHALL return the read-only program resource root only: the frozen executable's directory (or `sys._MEIPASS` vicinity) in frozen mode, the project root in dev mode. It MUST NOT be used for writing user data. Direct `get_exe_dir() / "data"` concatenation in call sites SHALL be replaced with the appropriate tier function.

#### Scenario: get_exe_dir in frozen mode
- **WHEN** the application runs from a PyInstaller frozen build
- **THEN** `get_exe_dir()` returns the directory containing the frozen executable

#### Scenario: get_exe_dir in dev mode
- **WHEN** the application runs from source
- **THEN** `get_exe_dir()` returns the project root directory

### Requirement: Dev mode path override
The system SHALL support a `LV_TOOLKIT_DATA_DIR` environment variable that, when set in dev mode, redirects the data-tier root to a project-local directory (e.g., `data/`) for test fixtures and developer convenience. Frozen mode MUST ignore this variable and always use OS-standard paths.

#### Scenario: Dev override redirects data tier
- **WHEN** `LV_TOOLKIT_DATA_DIR` is set to a path and the app runs in dev mode
- **THEN** `get_db_path` and `get_backup_path` resolve under the override directory

#### Scenario: Frozen mode ignores override
- **WHEN** `LV_TOOLKIT_DATA_DIR` is set and the app runs frozen
- **THEN** path resolution uses OS-standard APPDATA/LOCALAPPDATA/Documents locations regardless

### Requirement: Configurable output directory
The output root SHALL default to `Documents\LV Game Toolkit` and be overridable via `toolkit_config.json["output_dir"]`. Changes to this config key SHALL propagate to all consumers via the `config_changed` signal (FileConfigService), without requiring an app restart.

#### Scenario: Default output root
- **WHEN** `output_dir` is not set in config and the app starts fresh
- **THEN** `get_output_dir()` resolves under `Documents\LV Game Toolkit`

#### Scenario: User changes output directory at runtime
- **WHEN** the user picks a new output directory in the settings panel and saves
- **THEN** the `config_changed` signal fires and subsequent `get_output_dir()` calls resolve under the new root
