## ADDED Requirements

### Requirement: Chapter data schema definition

The system SHALL define per-chapter data schemas as YAML files (`chapters/{id}_data.yaml`) that describe the data fields an LLM agent must populate for each analysis chapter.

Each data schema SHALL include:
- `id` and `title` — chapter identifier and display name
- `trigger` — conditions under which the chapter should be included (referencing atomic skill names or data availability)
- `data_schema` — typed fields grouped into named sections, each field specifying `key`, `label`, `format`, and optional `severity` thresholds

#### Scenario: LLM loads fps data schema

- **WHEN** LLM agent begins the fps chapter analysis
- **THEN** the agent loads `chapters/fps_data.yaml` and discovers it needs to populate `core_metrics` (total_frames, actual_fps, jank_rate, jank_count, quality_rating) and `interval_distribution` (range, count, percentage columns)
- **AND** the schema defines field formats (integer, decimal_1, percentage, text) for correct value rendering

#### Scenario: Chapter with optional sections

- **WHEN** data_schema contains a section with `required: false`
- **THEN** the agent MAY skip that section if the corresponding SQL query returns no data or is not applicable to the current trace

### Requirement: Chapter render configuration

The system SHALL define per-chapter render configurations as YAML files (`chapters/{id}_render.yaml`) that specify how chapter data maps to Jinja2 HTML fragments.

Each render config SHALL list `sections` where each section specifies:
- `id` — matching a section in the data schema
- `fragment` — the Jinja2 template file name (from `fragments/`)
- `optional` — whether the section can be omitted from rendering
- `extra` — additional rendering parameters (e.g., `show_distribution_bar: true`)

#### Scenario: Render fps chapter with distribution bar

- **WHEN** `build_report.py chapter --chapter-id fps` is invoked with fps chapter data
- **THEN** the script reads `chapters/fps_render.yaml`, finds `core_metrics → metric_grid` and `interval_distribution → data_table`, and renders both using the corresponding Jinja2 fragments
- **AND** the distribution table includes a CSS bar chart because `extra.show_distribution_bar` is true

### Requirement: Reusable Jinja2 HTML fragments

The system SHALL provide 6 reusable Jinja2 HTML fragments in `templates/fragments/`:

| Fragment | Purpose |
|----------|---------|
| `metric_grid.j2` | A grid of labeled metric cards with severity coloring |
| `data_table.j2` | A standard data table with optional distribution bar |
| `conclusion_text.j2` | A conclusion block with overall rating, summary, highlights, risks, and recommendations |
| `distribution_bar.j2` | A CSS-based horizontal bar chart for distribution visualization |
| `root_cause_table.j2` | A list of root cause cards with severity badges |
| `severity_badge.j2` | A colored severity label (embedded in other fragments) |

#### Scenario: Render conclusion with all sections

- **WHEN** `build_report.py conclusion` is invoked with a complete conclusion data JSON
- **THEN** `conclusion_text.j2` renders the overall rating badge, summary paragraph, highlights list, risks list, and recommendations list
- **AND** the rating badge is colored based on `rating_color` field (green/yellow/red)

#### Scenario: Render metric grid with severity coloring

- **WHEN** `metric_grid.j2` receives items with `_severity` values (excellent/good/warning/critical)
- **THEN** each metric card is rendered with a CSS class `severity-{level}` for appropriate color styling

### Requirement: Incremental chapter build workflow

The system SHALL support an incremental workflow where each chapter is analyzed and rendered independently, with structured data retained in context for final cross-chapter analysis.

The workflow SHALL follow this sequence:
1. **Phase 0**: Explore trace → determine chapter list → `build_report.py init` writes header
2. **Phase 1**: For each chapter, LLM loads `{id}_data.yaml` → executes 1-3 SQL queries → formats chapter_data → calls `build_report.py chapter` → retains chapter_data in context → discards raw SQL results
3. **Phase 2**: LLM loads all chapter_data + `cross-chapter-rules.md` → performs cross-chapter correlation analysis → generates root_causes and conclusion → calls `build_report.py chapter` for root_causes and `build_report.py conclusion`
4. **Phase 3**: `build_report.py assemble` combines all chapter HTML + conclusion into final `report.html`

#### Scenario: 3-chapter analysis with context retention

- **WHEN** LLM analyzes fps, cpu, and gpu chapters sequentially
- **THEN** after fps chapter completes, `chapter_data/fps.json` is on disk and fps structured data remains in LLM context
- **AND** after cpu chapter completes, both fps and cpu chapter_data remain in context
- **AND** raw SQL results (>1K rows) from each chapter are discarded after rendering
- **AND** Phase 2 receives all 3 chapter_data structures for cross-chapter correlation

### Requirement: build_report.py script with four subcommands

The system SHALL provide `scripts/build_report.py` with four subcommands:

| Subcommand | Input | Output |
|------------|-------|--------|
| `init` | `--header` JSON string | `header.json` in output directory |
| `chapter` | `--chapter-id`, `--data` JSON string | `chapters/{id}.html` in output directory |
| `conclusion` | `--data` JSON string | `conclusion.html` in output directory |
| `assemble` | `--template` base.html path | `report.html` in output directory |

#### Scenario: Chapter command with data JSON

- **WHEN** `build_report.py chapter --chapter-id fps --data chapter_data.json` is called
- **THEN** the script reads `chapters/fps_render.yaml` for render config, reads `chapters/fps_data.yaml` for field metadata, loads the corresponding Jinja2 fragments, renders the HTML, and writes `chapters/fps.html`

#### Scenario: Assemble command with 5 chapters

- **WHEN** `build_report.py assemble` is called after chapters fps, cpu, gpu, memory, root_causes are rendered
- **THEN** the script reads all chapter HTML files and `conclusion.html`, inserts them into `base.html`, and writes the final `report.html`

### Requirement: Report output directory structure

The system SHALL produce the following directory layout for each analysis:

```
<output_base>/<trace_stem>/
├── header.json
├── chapters/
│   ├── fps.html
│   ├── cpu.html
│   └── ...
├── chapter_data/
│   ├── fps.json
│   ├── cpu.json
│   └── ...
├── conclusion.html
└── report.html
```

The output base SHALL be:
- Development: `<project_root>/data/output/trace_report/`
- Packaged exe: `<exe_dir>/output/perfetto_report/`

#### Scenario: Output path in development environment

- **WHEN** running in development mode with `root_dir=/project/`
- **THEN** report for trace `trace-sun-BQ2A` is written to `/project/data/output/trace_report/trace-sun-BQ2A/`

#### Scenario: Output path in packaged exe

- **WHEN** running as PyInstaller-frozen exe at `C:/Toolkit/Toolkit.exe`
- **THEN** report for trace `trace-sun-BQ2A` is written to `C:/Toolkit/output/perfetto_report/trace-sun-BQ2A/`

### Requirement: History panel integration

The system SHALL display analysis report entries in the `perfetto_capture` history panel.

Each trace entry with an associated analysis report SHALL show a report sub-node that, when double-clicked, opens the `report.html` file in the system browser.

#### Scenario: Trace with analysis report

- **WHEN** history panel is refreshed and a trace has an associated `report.html` in its output directory
- **THEN** the trace tree item shows a child node labeled with the analysis timestamp
- **AND** double-clicking the report node opens `report.html` in the default browser

#### Scenario: Trace without analysis report

- **WHEN** a trace has been captured but no analysis has been performed
- **THEN** the trace tree item shows no report sub-node

### Requirement: Report file naming convention

The system SHALL name the final report file using the pattern `perfetto-report-{app_short}-{date}-{type}.html` rather than a generic `report.html`.

Naming components:
- `app_short`: Extracted from the package name (e.g., `com.tencent.tmgp.sgame` → `sgame`). If no package name is available, use the process name.
- `date`: Date in YYYYMMDD format, extracted from the trace filename or the current analysis date.
- `type`: Analysis type keyword — `jank` (frame jank/卡顿), `startup` (启动), `memory` (内存), `comprehensive` (综合), etc.

#### Scenario: Report naming for game jank analysis

- **WHEN** analyzing `trace-sun-BQ2A.250831.001-2026-04-02-20-42-00.perfetto-trace` for the app `com.tencent.tmgp.sgame` (王者荣耀) with jank focus
- **THEN** the final report file is named `perfetto-report-sgame-20260402-jank.html`
- **AND** the file is placed in `data/output/trace_report/<trace_stem>/`

#### Scenario: Report naming when app is unknown

- **WHEN** the target app package name cannot be determined
- **THEN** `app_short` falls back to the process name from the process table
- **AND** if that is also unavailable, use `unknown`

### Requirement: SKILL.md SHALL guide agent to generate HTML reports

The `SKILL.md` file SHALL contain a dedicated "报告生成" (Report Generation) section that instructs the LLM agent to use `scripts/build_report.py` for HTML report generation.

The section SHALL include:
1. The `build_report.py` pipeline phases (init → chapter → conclusion → assemble)
2. Output directory and file naming conventions
3. Shell command examples for each phase
4. Chapter selection rules based on analysis skills used
5. data JSON format description for each chapter
6. Chat output convention: only report path + root cause summary, no full markdown report

The section SHALL NOT include a markdown report template (superseded by the HTML report system).

#### Scenario: Agent completes jank analysis

- **WHEN** the LLM agent has completed all SQL analysis steps for a jank-focused trace analysis
- **THEN** the agent reads the "报告生成" section of SKILL.md
- **AND** follows the pipeline to generate an HTML report at the standard output location
- **AND** outputs only the report path and a root cause summary in the chat

#### Scenario: Agent outputs in chat

- **WHEN** the HTML report has been successfully generated
- **THEN** the agent's chat output SHALL be limited to: (1) clickable path to the HTML report, (2) 3-5 line root cause summary
- **AND** the agent SHALL NOT output full data tables, metric grids, or detailed findings in chat (those belong in the HTML report)

### Requirement: build_report.py SHALL support programmatic import

The `scripts/build_report.py` module SHALL expose importable functions in addition to the CLI interface, allowing it to be used without subprocess calls.

The following functions SHALL be importable:

| Function | Signature | Description |
|----------|-----------|-------------|
| `init_report` | `(output_dir: str, header: dict) -> None` | Initialize report directory with header.json |
| `build_chapter` | `(chapter_id: str, data: dict, output_dir: str, *, chapters_dir: str = None, fragments_dir: str = None) -> None` | Render a single chapter to HTML |
| `build_conclusion` | `(data: dict, output_dir: str, *, fragments_dir: str = None) -> None` | Render conclusion to HTML |
| `assemble_report` | `(output_dir: str, *, template_path: str = None, output_path: str = None) -> None` | Assemble all chapters + conclusion into final HTML |

The existing CLI subcommands (`init`, `chapter`, `conclusion`, `assemble`) SHALL continue to work unchanged, delegating to the new functions internally.

#### Scenario: Import and use programmatically

- **WHEN** another Python script imports `from build_report import init_report, build_chapter, build_conclusion, assemble_report`
- **THEN** the script can call these functions directly with plain Python arguments
- **AND** the functions do not call `sys.exit()` on error (they raise exceptions instead)

#### Scenario: CLI backward compatibility

- **WHEN** `python build_report.py chapter --chapter-id fps --data data.json -o out/fps.html` is invoked
- **THEN** the command executes successfully, delegating to `build_chapter()` internally
