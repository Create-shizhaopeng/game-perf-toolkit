## ADDED Requirements

### Requirement: Installer build via Velopack
The build pipeline SHALL produce a Velopack Setup.exe (one-click installer) from the PyInstaller `--onedir` output, via the `vpk pack` command. The build MUST use `--onedir` mode (not `--onefile`, which is incompatible with Velopack). The pack ID SHALL be `LVGameToolkit` and the version SHALL be derived from the git tag.

#### Scenario: Build produces Setup.exe
- **WHEN** the build script runs `vpk pack --packId LVGameToolkit --packVersion <ver> --packDir dist/publish --mainExe Toolkit.exe`
- **THEN** a `Setup.exe` installer and a versioned delta update package are produced in the dist directory

#### Scenario: Onefile build is rejected
- **WHEN** the PyInstaller build is configured with `--onefile`
- **THEN** the Velopack pack step fails with a clear error indicating `--onedir` is required

### Requirement: Runtime update hook at process start
The application SHALL invoke `velopack.App().run()` as the first operation in `main()` (after stdio fix, before logging setup and plugin loading), to allow Velopack to apply pending updates which may quit/restart the process.

#### Scenario: Pending update applied on next launch
- **WHEN** a delta update was downloaded in a previous session and the app launches
- **THEN** `velopack.App().run()` applies the update and restarts into the new version before normal startup proceeds

#### Scenario: No pending update
- **WHEN** the app launches with no pending update
- **THEN** `velopack.App().run()` returns immediately and normal startup proceeds

### Requirement: Background update check in GUI mode
The GUI mode SHALL perform a background update check via `velopack.UpdateManager` after the main window is shown, pointing at the GitHub Releases feed. When an update is available, the user SHALL be notified (non-blocking). Update download SHALL happen in the background; the update applies on the next launch.

#### Scenario: Update available notification
- **WHEN** `UpdateManager.check_for_updates()` returns a newer version from the feed
- **THEN** the user is notified (non-blocking) that an update is available and downloading

#### Scenario: No update available
- **WHEN** the feed reports the current version is latest
- **THEN** no notification is shown and startup proceeds silently

#### Scenario: Update feed unreachable
- **WHEN** the update check fails due to network error or unreachable feed
- **THEN** the failure is logged at debug level and startup proceeds without interruption

### Requirement: Delta-based updates
Updates SHALL use Velopack's delta mechanism so users download only the diff between versions, not the full package. This applies to both initial update downloads and subsequent version increments.

#### Scenario: Small delta download between minor versions
- **WHEN** an update from v1.2.0 to v1.2.1 is applied
- **THEN** only the changed blocks are downloaded, not the full application package

### Requirement: Code signing support
The build pipeline SHALL support optional code signing of the installer and update packages via Velopack's signing integration. When signing credentials are configured, the build MUST sign outputs; when not configured (internal dev builds), the build MUST succeed unsigned.

#### Scenario: Signed build when credentials present
- **WHEN** signing credentials are configured in the build environment
- **THEN** the produced Setup.exe and delta packages are code-signed

#### Scenario: Unsigned build when credentials absent
- **WHEN** no signing credentials are configured
- **THEN** the build produces unsigned outputs and logs a warning about Windows SmartScreen

### Requirement: MCP server mode skips update application
Because applying an update restarts the process (which would break an MCP stdio connection), the MCP server mode (`mcp-serve`) SHALL skip the update-application hook. Update checks and application SHALL occur only in GUI mode.

#### Scenario: MCP server does not apply updates
- **WHEN** the app is launched with `mcp-serve`
- **THEN** the `velopack.App().run()` update-application path is bypassed to avoid disrupting the stdio session
