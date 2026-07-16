# Ruleset Notebook Implementation Plan

## 1. Product decision

Version 1 will be a plain-text term-rewriting workbench organized around cached
jobs. It will not implement interactive notebook cells or HTML-like output.

The durable unit is:

| Job ID | Rules | Notebook inputs | Results / traces |
|---|---|---|---|
| stable unique ID | exact ordered rules text | exact multi-input source text | exact generated output and trace text |

Each Run action creates a new immutable job. A job captures the source text and
settings used by the evaluator, its status, and the generated results. Selecting
an old job reloads that complete snapshot. If the user wants to change it, the UI
duplicates it into a new editable draft; it never rewrites history in place.

This model gives v1 a small UI and strong reproducibility. It also leaves a clean
upgrade path: cells, syntax highlighting, tree views, and HTML rendering can
later project the same structured engine and job data.

## 2. Goals and boundaries

### V1 goals

- Use ordinary UTF-8 text for rules, inputs, and persisted output.
- Provide a job-history table with one row per cached run.
- Provide three resizable text panes below the table:
  - editable ordered rules;
  - editable notebook inputs, one term per non-empty line;
  - read-only results and traces.
- Capture an immutable snapshot whenever Run starts.
- Assign every attempt a stable, sortable job ID.
- Cache completed, limited, cancelled, and evaluation-error jobs.
- Optionally cache parse failures so a failed run remains reproducible.
- Reload any cached job without reevaluating it.
- Duplicate a cached job into a new draft for editing and rerunning.
- Parse a compact term and ordered-rule syntax.
- Rewrite nested terms deterministically using one innermost strategy.
- Record structured trace events and format them as plain text.
- Stop safely at normal form, a step limit, a depth limit, cancellation, or an
  error.
- Keep evaluation and cache scanning off performance-sensitive GUI paths.
- Keep all language and engine code independent of Qt.

### Explicitly deferred

- Per-cell editors, Run buttons, execution counters, and cell reordering.
- HTML, Markdown, rich text, or embedded output widgets.
- Interactive trace trees and binding inspector widgets.
- In-place editing of historical jobs.
- A database or cache index; v1 scans one JSON job file per cached run.
- Alternative rewrite strategies or branching exploration.
- Modules, imports, remote jobs, grading, or collaborative editing.
- Content-addressed result deduplication.
- Proving termination or confluence.
- Arbitrary Python in guards or replacements.

## 3. V1 workflow

### New draft

1. The application opens with a draft containing example rules and inputs, or a
   blank draft if the user chooses New Draft.
2. The user edits the Rules and Notebook Inputs panes as plain text.
3. Results / Traces remains empty or shows the last draft validation message.
4. Edits mark the draft dirty but do not affect cached jobs.

### Run

1. The user selects Run or presses `Ctrl+Enter`.
2. The controller freezes rules text, input text, settings, and creation time in a
   `JobRequest` and allocates a job ID.
3. The parser validates the complete snapshot.
4. If valid, evaluation runs in a worker using only snapshot data.
5. Structured engine results are formatted into deterministic plain text.
6. A complete job file is written atomically to the cache.
7. The row appears in Jobs and the output pane displays its saved result text.

A parse failure should be representable as a job with empty/diagnostic results.
Whether the UI caches it automatically or offers “Save Failed Attempt” is an
implementation choice to settle before Phase 4; automatic caching is preferred
because it preserves the invariant that every Run has a job ID.

### Reload

1. Selecting a Jobs row loads its file and validates its JSON format/version.
2. Rules, inputs, and results panes show the saved text verbatim.
3. Historical mode makes Rules and Inputs read-only.
4. Duplicate as Draft copies rules, inputs, and settings into editable draft state
   without copying the old job ID or results.

### Delete and export

- Delete Cached Job removes only the selected cache file after confirmation.
- Export copies the selected job file to a user-selected location.
- Open Job File reads a compatible exported job without adding it to the cache
  until the user explicitly imports or duplicates/runs it.

## 4. Window design

Use a vertical layout with a compact Jobs table above a horizontal three-way
splitter.

```text
+--------------------------------------------------------------------------------+
| Jobs                                                                           |
| Job ID       | Rules | Inputs | Result summary | Status      | Created          |
| 01J...A      | 2     | 2      | 5; 14          | normal form| 2026-07-15 13:10 |
| 01J...B      | 2     | 1      | step 100       | step limit | 2026-07-15 13:12 |
+------------------------+--------------------------+----------------------------+
| Rules                  | Notebook inputs          | Results / traces           |
|                        |                          |                            |
| add-zero:              | add(2, 3)                | job: 01J...A               |
| add(x, 0) => x         | add(10, 4)               | input 1: add(2, 3)         |
|                        |                          | ...                        |
| add-step: ...          |                          | result: 5                  |
+------------------------+--------------------------+----------------------------+
| [New Draft] [Run] [Stop] [Duplicate] [Export] [Delete]       status: ready     |
+--------------------------------------------------------------------------------+
```

### Jobs table

Use `QTableView` backed by a `QAbstractTableModel`. Suggested columns:

- Job ID: shortened for display, full value in tooltip/copy action.
- Rules: count of active rule lines.
- Inputs: count of parsed input terms.
- Result summary: compact final values or failure summary.
- Status: normal form, parse error, runtime error, step limit, depth limit,
  cancelled, or internal error.
- Created: local display of a timezone-aware timestamp.

Default order is newest first. The model can parse each small JSON record while
building the table projection; a separate lightweight `JobSummary` remains a
future optimization if cached traces grow large.
Add Refresh and copy-job-ID actions. Search and filters are post-v1 unless the
cache becomes cumbersome during development.

### Rules pane

- Use `QPlainTextEdit`, not one widget per rule.
- One rule occupies one logical line in v1.
- File order is rule priority.
- Blank lines and `#` comments are ignored.
- Diagnostics show line and column and highlight the corresponding text range.
- No add/delete/reorder buttons are required; normal text editing handles those
  operations.

### Notebook inputs pane

- Use `QPlainTextEdit`.
- One input term occupies one non-empty line.
- Blank lines and `#` comments are ignored.
- Run evaluates all parsed input lines in source order as one job.
- A failure for one validly parsed input records that input's error and continues
  with later inputs unless Stop cancels the whole job.
- No cell concepts appear in the v1 data or UI model.

### Results / traces pane

- Use a read-only `QPlainTextEdit` with a monospaced font.
- Show job metadata, then one trace section per input.
- Preserve and display the exact saved output text when reloading a job.
- Provide Copy All and Save/Export through common text/file actions.
- Use structured engine data to generate output; do not build traces by scraping
  debug log lines.
- Large output should be inserted in one bounded update or loaded from file,
  rather than appended one GUI event per rewrite step.

### Actions and state

- New Draft: leave historical mode and create editable source buffers.
- Run: snapshot and evaluate the current draft.
- Stop: cancel the active job; disabled when idle.
- Duplicate as Draft: copy selected job source/settings to a fresh draft.
- Open Job File: inspect an exported job.
- Export Job: copy selected job to a user path.
- Delete Cached Job: remove the selected local cached record.
- Refresh Jobs: rescan cached JSON job files.
- Exit: prompt only for unsaved draft changes or an active run.

## 5. Plain-text source formats

### Terms

```ebnf
term           = identifier | literal | symbol_or_call | grouped ;
literal        = integer | float | string | "true" | "false" ;
symbol_or_call = identifier, ["(", [term, {",", term}], ")"] ;
grouped        = "(", term, ")" ;
identifier     = (letter | "_"), {letter | digit | "_" | "-"} ;
```

Identifier meaning is contextual. In rules and guards, a lowercase leaf is a
variable, while an identifier followed by parentheses is a function symbol. An
uppercase leaf is a concrete symbolic constant. In notebook inputs, all leaves
are concrete symbols because inputs do not declare pattern variables.

### Rules

```text
[name:] left-hand-side => right-hand-side
[name:] left-hand-side => right-hand-side when guard-expression
```

Examples:

```text
add(x, 0) => x
add(x, y) => add(inc(x), dec(y)) when y > 0
negative: add(x, y) => error("negative operand") when y < 0
```

Explicit rule names must be non-empty and effective names must be unique within
one job. When no name is supplied, parsing generates `<lhs-symbol>-<line-number>`
(for example, `add-2`). This keeps trace text readable without requiring naming
ceremony. A replacement or guard may reference only variables bound by its LHS.

### Guards and built-ins

Guards parse into a restricted AST. Never pass source to Python `eval` or `exec`.
V1 supports comparisons (`==`, `!=`, `<`, `<=`, `>`, `>=`) joined by `and` and
parentheses. Operands are literals or bound variables.

Built-in reductions cover `inc`, `dec`, `add`, `sub`, `mul`, and `div` when their
arguments are compatible numeric literals. Division by zero and incompatible
types produce typed runtime errors.

### Multi-input parsing

- Split rules and inputs by physical lines after preserving original source.
- Ignore blank lines and lines whose first non-space character is `#`.
- Do not support multiline terms or rules in v1.
- Keep physical line numbers so diagnostics correspond to the text editor.
- Preserve original source text in the job even if the formatter has a canonical
  internal representation.

## 6. Job identity and lifecycle

Use a UUIDv7 or ULID-style identifier so IDs are unique and naturally sortable.
Do not derive v1 identity solely from content: running the same draft twice should
produce two jobs with distinct timestamps and IDs.

Lifecycle states:

```text
DRAFT -> QUEUED -> RUNNING -> terminal status -> CACHED
```

Terminal statuses are:

- `NORMAL_FORM`
- `PARSE_ERROR`
- `RUNTIME_ERROR`
- `STEP_LIMIT`
- `DEPTH_LIMIT`
- `CANCELLED`
- `INTERNAL_ERROR`

Jobs are immutable once cached. If writing the cache fails, the UI still displays
the in-memory result but marks it `not cached` and offers Retry Save/Export. A job
must never appear as cached until its atomic replacement succeeds.

## 7. Job file format

Use one versioned JSON object per `<job-id>.rsjob` file. JSON is standard-library
data, inspectable in a text editor, and removes the need to maintain custom header
and section delimiters. The object stores metadata plus the exact `rules_text`,
`inputs_text`, and `results_text` strings.

```json
{
  "format": "ruleset-notebook-job",
  "version": 1,
  "job_id": "01J...",
  "created_at": "2026-07-15T13:10:00-05:00",
  "status": "normal form",
  "rule_count": 2,
  "input_count": 1,
  "result_summary": "5",
  "rules_text": "add(x, 0) => x\n...",
  "inputs_text": "add(2, 3)\n",
  "results_text": "result: 5\n..."
}
```

### Reading and writing

- Parse and validate the complete JSON object when listing or selecting a job.
- Validate the format tag, version, required fields, scalar types, and counts.
- Keep exact source/result strings; JSON escaping handles newlines and quotes.
- Write a temporary file, flush it, then atomically replace the target.
- Never deserialize Python objects or execute file content.
- Reject unsupported future versions with a clear error.
- Ignore malformed cache files while retaining valid jobs.
- JSONL is deferred for a future single append-only history file; it is not needed
  for the current one-file-per-job cache.

## 8. Core domain and application models

Use frozen dataclasses and tuples for engine values:

```python
@dataclass(frozen=True, slots=True)
class Rule:
    name: str
    lhs: Term
    rhs: Term
    guard: GuardExpr | None
    source_line: int

@dataclass(frozen=True, slots=True)
class RewriteEvent:
    index: int
    before: Term
    after: Term
    rule_name: str
    position: tuple[int, ...]
    bindings: Mapping[str, Term]

@dataclass(frozen=True, slots=True)
class InputResult:
    source_line: int
    input_term: Term
    output_term: Term
    events: tuple[RewriteEvent, ...]
    stop_reason: StopReason
    error: EngineError | None

@dataclass(frozen=True, slots=True)
class JobRecord:
    job_id: JobId
    rules_text: str
    inputs_text: str
    results_text: str
    settings: EvaluationSettings
    status: JobStatus
    created_at: datetime
    completed_at: datetime | None
```

Application state:

- `Draft`: mutable rules text, inputs text, settings, and dirty flag.
- `JobRequest`: immutable run snapshot plus allocated identity.
- `JobRecord`: immutable completed/failed run ready for persistence.
- `JobSummary`: lightweight header projection for the table.
- `JobStore`: lists JSON records, atomically writes records, deletes
  cached files, and exports/imports files.
- `RunController`: owns the active worker and cancellation token.

The selected historical job and editable draft are separate state. This prevents
a table selection from silently overwriting unsaved draft work.

## 9. Rewriting semantics

### Matching

- Literals match equal literals of the same type.
- Applications match symbol and arity, then recurse.
- A variable binds the first subject subtree it sees.
- Repeated variables require structural equality.
- Matching returns a new immutable bindings map or a typed failure.

### Substitution

- Replace RHS variables recursively from match bindings.
- Reject unbound RHS/guard variables during rule validation.
- Retain defensive runtime checks against invalid internal rule objects.

### Deterministic strategy

V1 is left-to-right innermost:

1. Traverse children from left to right.
2. Choose the deepest leftmost reducible position.
3. Try rules in source-file order.
4. Apply the first matching rule whose guard succeeds.
5. If no user rule applies, try a documented built-in reduction.
6. Record one event and restart traversal from the root.
7. Stop when no position is reducible or a safety condition fires.

Count successful rewrites rather than match attempts. Check cancellation during
traversal and after every step. Enforce configurable maximum steps and term depth.
The evaluator returns a structured result for every input; it never prints trace
lines directly.

## 10. Architecture

```text
RulesetNotebook/
|-- pyproject.toml
|-- README.md
|-- plan.md
|-- todo.md
|-- src/ruleset_notebook/
|   |-- __main__.py
|   |-- domain/
|   |   |-- terms.py
|   |   |-- rules.py
|   |   `-- results.py
|   |-- language/
|   |   |-- lexer.py
|   |   |-- term_parser.py
|   |   |-- rule_file_parser.py
|   |   |-- input_file_parser.py
|   |   `-- formatter.py
|   |-- engine/
|   |   |-- matcher.py
|   |   |-- substitution.py
|   |   |-- builtins.py
|   |   `-- evaluator.py
|   |-- jobs/
|   |   |-- models.py
|   |   |-- text_format.py
|   |   |-- store.py
|   |   `-- service.py
|   `-- ui/
|       |-- main_window.py
|       |-- job_table_model.py
|       |-- text_panes.py
|       `-- run_controller.py
`-- tests/
    |-- unit/
    |-- integration/
    `-- ui/
```

Dependency direction:

```text
PySide6 UI -> jobs/application services -> language + engine -> domain
```

The domain, language, engine, job parser, and job store do not import Qt. The UI
may use Qt adapters for settings and atomic files, but core job serialization must
remain testable without a `QApplication`.

## 11. Background execution and consistency

- Use `QThreadPool/QRunnable` or `QThread/QObject`; choose one and document
  ownership before implementation.
- A worker receives only a frozen `JobRequest`.
- A worker never reads editors, updates models, or writes widgets.
- Completion returns on the GUI thread, formats/persists the job, refreshes the
  Jobs table, and selects the new row.
- Stop sets a thread-safe token and is idempotent.
- Only one active job is needed in v1.
- Starting a run while one is active is disabled.
- New Draft, selecting a job, and closing the application must not make a running
  result attach to the wrong view.
- The job ID connects request, result, persistence, and UI row.

## 12. Testing strategy

### Engine and language

- Token and source-span tests, including comments and physical line numbers.
- Term/rule/input parsing and canonical formatting.
- Rule-name uniqueness and RHS/guard variable validation.
- Matching, substitution, guards, nested rewrites, and ordered priority.
- Normal form, step/depth limits, cancellation, and runtime errors.
- Exact structured events: rule, position, bindings, before, and after.

### Job files and cache

- Deterministic write/read round trip for every terminal status.
- Exact preservation of rules, inputs, and generated results blocks.
- Header-only summary reads.
- Malformed JSON records, invalid versions/IDs, and
  unsupported versions.
- Atomic-write failure leaves no valid-looking partial job.
- Cache scan ignores temporary/unrelated files and reports malformed job files
  without preventing valid rows from loading.
- Duplicate as Draft copies source/settings but not identity or results.
- Same source run twice produces distinct IDs.

### UI

Use `pytest-qt` where practical:

- Window shows Jobs plus the three text panes.
- Draft mode is editable; historical mode is read-only.
- Run snapshots exact current text and adds the completed job row.
- Selecting a row loads its exact cached text without evaluation.
- Duplicate returns copied source to editable draft mode.
- Stop cancels a looping job without freezing the event loop.
- Deleting a job removes its row/file but not unrelated records.
- Unsaved draft prompts do not lose text.
- Large trace loading remains responsive enough for the configured step cap.

### Quality gates

- `ruff format --check .`
- `ruff check .`
- `mypy src`
- `pytest`
- Windows manual smoke test from a clean environment.

## 13. Delivery phases

### Phase 0: baseline

- Add package metadata, dependencies, test/lint/type configuration, and entry
  point.
- Preserve the current `app.py` example in characterization tests.
- Launch an empty PySide6 main window.

Exit: all configured checks run and the application launches.

### Phase 1: text language and immutable domain

- Implement term/rule/result types, lexer, parsers, formatter, and diagnostics.
- Parse entire rules and input text files with physical source locations.

Exit: documented example text parses, invalid lines have useful diagnostics, and
format round trips pass.

### Phase 2: evaluator and structured traces

- Implement matching, substitution, guards, nested deterministic rewriting,
  built-ins, limits, cancellation, and structured trace results.

Exit: addition reaches `5`; loops stop safely; exact events are asserted.

### Phase 3: job file and cache

- Implement job IDs, lifecycle models, JSON serialization, cache scans, atomic
  writes, reads, deletion, import/export, and duplicate-as-draft behavior.

Exit: every terminal status round-trips and the cache can rebuild its job list
from files alone.

### Phase 4: v1 PySide6 workflow

- Build Jobs `QTableView`, three `QPlainTextEdit` panes, actions, modes, settings,
  background runner, cancellation, and cache refresh.

Exit: users can edit a plain-text draft, run it, reload the resulting job, and
duplicate it without UI cells or rich output.

### Phase 5: hardening and release

- Complete automated UI tests, malformed-cache recovery, accessibility, large
  trace behavior, help text, Windows smoke tests, and packaging.

Exit: the acceptance scenario passes from a clean installation with no known
data-loss or UI-freeze defects.

## 14. V1 acceptance scenario

1. Launch and see the Jobs table plus Rules, Notebook Inputs, and Results / Traces
   text panes.
2. Paste the documented addition rules into Rules.
3. Put `add(2, 3)` and `add(10, 4)` on separate lines in Notebook Inputs.
4. Run once and receive a new job ID.
5. See one Jobs row showing two rules, two inputs, final-result summary, status,
   and creation time.
6. See both deterministic traces in plain text, including rule names, bindings,
   positions, results, and stop reasons.
7. Start a looping job and see it become a cached step-limit job without freezing
   the window.
8. Select the first job and recover its exact rules, inputs, and trace without
   reevaluating it.
9. Duplicate that job, edit an input, and Run; confirm a distinct job ID and that
   the original cached file is unchanged.
10. Restart the app and confirm the Jobs table is rebuilt from cached text files.
11. Export a job, open the exported file, and recover the same three text blocks.

## 15. Risks and mitigations

- **History mutation:** cached jobs are immutable; edits occur only in Draft.
- **Source/result drift:** one atomic job file stores rules, inputs, settings, and
  generated output together.
- **Cache corruption:** strict JSON validation, temporary-file writes,
  atomic replace, and graceful per-file scan errors.
- **Slow startup:** keep the table projection lightweight; defer `JobSummary`
  optimization until cache size requires it.
- **Non-termination:** engine-owned step/depth limits and cancellation.
- **Unsafe guards:** whitelist grammar, never Python evaluation.
- **UI freezes:** worker evaluation and bounded GUI updates.
- **Trace growth:** configured step cap and plain-text loading rather than one
  widget per event.
- **Ambiguous v1 scope:** text panes and jobs only; cells and HTML are explicitly
  Phase 2 product work after v1.

## 16. Post-v1 evolution

The next presentation layer can split a job's plain input file into visual cells,
one per parsed input line. Each cell can show the corresponding `InputResult` and
reuse the existing structured events. A later HTML/Markdown renderer can format
the same `JobRecord` without changing job identity or evaluator semantics.

Recommended order:

1. Add a read-only interactive trace tree beside the canonical saved text.
2. Add visual input cells as an alternate editor for the same input source.
3. Add per-cell run by defining whether it creates a whole job or a child job.
4. Add HTML/Markdown rendering as a projection, with plain text retained for
   portability and debugging.
5. Add content hashes and result reuse only after file-format compatibility is
   stable.
6. Consider SQLite only when querying/filtering volume justifies an index; job
   text files remain import/export artifacts.
