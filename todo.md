# Ruleset Notebook Implementation Checklist

This checklist turns [plan.md](plan.md) into implementation-sized tasks. Check an
item only when its code, tests, and relevant documentation are complete.

## 0. Repository baseline

- [x] Add `pyproject.toml` with Python 3.11+, PySide6, and a console entry point.
- [x] Add development dependencies: pytest, pytest-qt, ruff, and mypy.
- [x] Configure `src/ruleset_notebook` package discovery.
- [x] Add `.gitignore` entries for virtual environments, caches, coverage, build
  output, and local Qt settings.
- [x] Add `tests/unit`, `tests/integration`, and `tests/ui` packages.
- [x] Add `__main__.py` so `python -m ruleset_notebook` launches the app.
- [x] Add a CI-friendly command or script that runs formatting, linting, typing,
  and tests.
- [x] Add GitHub Actions checks on Windows, macOS, and Linux.
- [x] Preserve the current `app.py` example behavior in characterization tests.
- [x] Replace the top-level proof-of-concept with a compatibility launcher after
  migrating its characterization tests to the shared engine.
- [x] Make the GUI and CLI use the same domain types and text parser.
- [x] Add a PyInstaller build script that produces a standalone Windows executable.
- [x] Build and archive PyInstaller bundles per operating system in CI; publish
  version-tagged bundles as GitHub Releases.

## 1. Domain types

- [x] Implement immutable term variants for variables, literals, and applications.
- [x] Represent application children as tuples.
- [x] Define structural equality and hashing tests.
- [x] Define `SourcePosition` and `SourceSpan` with line/column/offset data.
- [x] Define typed diagnostics with code, severity, message, span, and hint.
- [x] Implement immutable `Rule` with UUID, name, ASTs, guard, and enabled state.
- [x] Implement `EvaluationSettings` with validated step/depth limits.
- [x] Define `RewriteEvent`, `EvaluationResult`, `StopReason`, and engine errors.
- [x] Add readable `repr` output for development without making it canonical
  serialization.

## 2. Term lexer and parser

- [ ] Tokenize identifiers, integers, floats, strings, punctuation,
  comparison operators, and keywords.
- [ ] Track source spans across whitespace and newlines.
- [x] Support escaped quotes, backslashes, tabs, and newlines in strings.
- [x] Produce a diagnostic for invalid characters and unterminated strings.
- [x] Parse bare symbols and function-like applications.
- [x] Interpret lowercase leaves as variables in rule context and as symbols in
  notebook-input context; reserve uppercase leaves for rule constants.
- [ ] Parse nested and grouped terms.
- [x] Reject variables in notebook input mode (lowercase leaves parse as symbols,
  never `Var` nodes).
- [ ] Reject missing commas, missing parentheses, and trailing unexpected tokens
  with precise spans.
- [x] Decide whether negative numbers are signed literals or unary syntax and
  encode that decision in tests and the README syntax section.
- [x] Add parameterized valid/invalid parser tests.

## 3. Formatting and rule validation

- [x] Implement a canonical term formatter.
- [x] Escape literal strings deterministically.
- [x] Add parse/format/parse round-trip tests.
- [x] Parse or assemble rules from name, LHS, RHS, and guard source fields.
- [x] Require at least one non-variable symbol/literal shape in an LHS if needed
  to prevent catch-all accidents; document the final choice.
- [x] Collect all variables bound by the LHS.
- [x] Reject RHS references to variables not present in the LHS.
- [x] Accept optional explicit rule names and generate
  `<lhs-symbol>-<line-number>` when omitted.
- [x] Reject duplicate effective rule names so saved trace lines identify rules
  unambiguously.
- [x] Return validation diagnostics without throwing UI-facing exceptions.
- [x] Add a non-throwing `validate_rules_text` pass that reports incomplete or
  invalid rule lines with line/column information while the draft is being edited.
- [x] Show rule-validation feedback in the GUI (status text first; inline
  highlighting can follow) and keep Run behavior consistent with that result.

## 4. Guards

- [x] Add guard AST nodes for values, comparisons, conjunctions, and grouping.
- [x] Parse `==`, `!=`, `<`, `<=`, `>`, `>=`, and `and`.
- [x] Resolve guard variables only from match bindings.
- [x] Reject unbound guard variables during validation.
- [x] Define comparison behavior for mismatched literal types.
- [x] Return a typed guard failure for invalid runtime comparisons.
- [x] Confirm no guard path imports or calls Python `eval`/`exec`.
- [x] Test true, false, compound, grouped, missing-variable, and type-error cases.

## 5. Matcher and substitution

- [x] Match equal literals with deliberate bool/int behavior.
- [x] Match applications by symbol and arity before recursing.
- [x] Bind a new pattern variable to the subject subtree.
- [x] Require repeated pattern variables to match structurally equal subtrees.
- [x] Ensure a failed match does not leak partial bindings.
- [x] Substitute RHS variables recursively from an immutable bindings map.
- [x] Retain a defensive error for unbound substitution variables.
- [x] Test nested terms, repeated variables, arity mismatch, literal mismatch, and
  immutable input preservation.

## 6. Rewrite engine

- [x] Define a term-position representation using child-index tuples.
- [x] Implement reading and replacing a subtree at a position.
- [x] Enumerate candidate positions in left-to-right innermost order.
- [x] Try enabled rules in list order at each candidate position.
- [x] Evaluate a rule guard after successful matching and before substitution.
- [x] Apply only the first successful rule per step.
- [x] Restart traversal from the root after every successful step.
- [x] Implement numeric built-ins for `inc`, `dec`, `add`, `sub`, `mul`, and `div`,
  or revise the acceptance example to match the final primitive set.
- [x] Define user-rule versus built-in priority and cover it with tests.
- [x] Detect division by zero and invalid primitive operand types.
- [x] Count successful rewrite steps consistently.
- [x] Stop at normal form.
- [x] Stop exactly at `max_steps` and return the partial term.
- [x] Stop before a replacement exceeds `max_depth`.
- [x] Check cancellation during traversal and between steps.
- [ ] Optionally detect repeated full terms and annotate a likely cycle.
- [x] Ensure ordinary evaluation is iterative enough to avoid Python recursion
  failure on a long rewrite sequence.

## 7. Trace data

- [x] Record input, output, rule UUID/name, bindings, position, and event kind for
  every successful rewrite.
- [x] Freeze or copy bindings before storing them.
- [x] Record the final stop reason independently of rewrite events.
- [ ] Add optional elapsed time without using it in equality assertions.
- [x] Test the exact rule sequence and positions for root and nested rewrites.
- [ ] Test trace output for normal form, limit, cancellation, and runtime error.
- [ ] Add a deterministic plain-text formatter for complete multi-input results.

## 8. Draft and job models

- [ ] Implement mutable `Draft` with rules text, inputs text, settings, and dirty
  state.
- [ ] Keep selected historical job state separate from the editable draft.
- [ ] Implement sortable `JobId` generation using UUIDv7 or ULID semantics.
- [ ] Implement immutable `JobRequest` containing exact source text, parsed rules
  and inputs, settings, identity, and creation timestamp.
- [x] Implement immutable `JobRecord` containing exact rules/inputs/results text,
  counts, status, summary, timestamp, and job ID.
- [ ] Implement lightweight `JobSummary` for header-only table rows.
- [x] Create a tested project example catalog with addition, guarded choice,
  structural data, and boolean drafts; let the GUI load any example explicitly.
- [x] Ensure every Run attempt receives a unique job ID.
- [x] Cache parse-error attempts as records with a parse-error status.
- [ ] Implement Duplicate as Draft without copying job ID, status, or results.

## 9. JSON job format and cache

- [x] Define versioned JSON format `ruleset-notebook-job` version 1 and the
  `.rsjob` extension.
- [x] Define required metadata, counts, status, summary, and exact text fields.
- [x] Serialize exact UTF-8 rules, inputs, and generated output as JSON strings.
- [x] Validate JSON format/version, required fields, scalar types, and counts.
- [x] Implement one cache file per job ID.
- [x] Ignore malformed cache files while retaining valid records.
- [x] Write a temporary file and atomically replace the target.
- [x] Never expose a row as cached before atomic persistence succeeds.
- [x] Implement read, write, and delete operations.
- [x] Implement import/open and export operations (see
  [docs/import-export.md](docs/import-export.md)).
- [ ] Test all terminal statuses and simulated write failures.
- [x] Test that two identical runs produce distinct IDs and files.
- [ ] Consider JSONL only if the cache later becomes one append-only history file.

## 10. Main window shell

- [ ] Create `QApplication` startup with organization/application names.
- [ ] Create `QMainWindow` with a Jobs table above a horizontal three-way splitter.
- [ ] Add labeled Rules, Notebook Inputs, and Results / Traces panes.
- [ ] Use `QPlainTextEdit` for all three panes; set results read-only.
- [ ] Use a monospaced font and useful minimum pane widths.
- [ ] Add File, Edit, Run, View, and Help menus.
- [ ] Create shared `QAction` objects for menus, toolbar, shortcuts, and enabled
  state.
- [ ] Add status bar fields for mode, selected/active job, cache state, and run
  status.
- [ ] Restore geometry and splitter sizes with `QSettings`.
- [ ] Add Reset Layout.
- [ ] Set accessible names, tooltips, tab order, and visible focus behavior.
- [ ] Test window construction and close under `pytest-qt`.

## 11. Jobs table

- [ ] Implement `JobTableModel` using header-only `JobSummary` values.
- [ ] Add Job ID, Rules, Inputs, Result Summary, Status, and Created columns.
- [ ] Sort newest jobs first by default.
- [ ] Display shortened IDs while exposing the full ID for copy/tooltips.
- [ ] Add Refresh Jobs and Copy Job ID actions.
- [ ] Load the complete record only when a row is selected.
- [ ] Show malformed cache-file warnings without hiding valid jobs.
- [ ] Preserve selection across safe refreshes.
- [ ] Confirm Delete removes only the selected job file/row.
- [ ] Test model roles, sorting, selection, refresh, and cache scan errors.

## 12. Plain-text editing workflow

- [ ] Implement editable Draft mode for Rules and Notebook Inputs.
- [ ] Implement read-only Historical mode for all three saved blocks.
- [ ] Prompt before New Draft or historical selection would discard dirty draft
  text.
- [ ] Parse one rule per non-empty, non-comment line in source order.
- [ ] Parse one input term per non-empty, non-comment line.
- [ ] Highlight diagnostics at physical line/column positions.
- [ ] Add New Draft, Run, Stop, Duplicate as Draft, Open Job File, Export Job,
  Delete Cached Job, and Refresh actions.
- [ ] Bind `Ctrl+Enter` to Run the entire draft.
- [ ] Display generated results in one bounded text update.
- [ ] Preserve exact saved results text when selecting an old job.
- [ ] Keep text editing as the only v1 rule/input manipulation mechanism.
- [ ] Test mode transitions and unsaved-draft prompt branches.

## 13. Worker and run controller

- [ ] Choose and document `QThreadPool/QRunnable` or `QThread/QObject` ownership.
- [ ] Pass an immutable `JobRequest` to the worker.
- [ ] Add success, typed failure, and finished signals keyed by job ID.
- [ ] Marshal all model, cache, and widget updates to the GUI thread.
- [ ] Add one cancellation token for the active job.
- [ ] Make Stop idempotent.
- [ ] Disable Run while a job is active.
- [x] Continue to later inputs after a per-input runtime error unless cancelled.
- [ ] Prevent selection/new-draft changes from attaching output to the wrong view.
- [ ] Cache the terminal job before marking it cached in the table.
- [ ] Show in-memory output plus Retry Save/Export when cache writing fails.
- [ ] Test event-loop responsiveness with a deliberately looping ruleset.
- [ ] Log unexpected exceptions while returning `INTERNAL_ERROR` output.

## 14. Results and trace text

- [ ] Define deterministic job, input, step, result, and status line formats.
- [ ] Include rule name, bindings, and rewritten position on every rewrite line.
- [ ] Format root and nested positions consistently.
- [ ] Include an explicit stop reason for every input.
- [ ] Include partial output for step/depth limit and cancellation.
- [ ] Include line-located diagnostics for parse errors.
- [ ] Add Copy All and Export actions.
- [ ] Avoid one GUI update per event.
- [ ] Test exact output for normal form, multiple inputs, parse/runtime errors,
  limits, and cancellation.
- [ ] Keep structured result objects available internally for post-v1 views.

## 15. File and cache workflow

- [ ] Implement New Draft using the starter text factory.
- [x] Implement Open Job File with validation and clear errors.
- [x] Implement Export Job using `.rsjob` by default.
- [ ] Implement Duplicate as Draft.
- [ ] Implement confirmed Delete Cached Job.
- [ ] Keep selected/draft state untouched when open/export/delete fails.
- [ ] Prompt Save/Discard/Cancel for dirty drafts when appropriate.
- [ ] Cancel or safely detach an active run during shutdown.
- [ ] Store cache directory and local UI preferences in `QSettings`.
- [ ] Rebuild the Jobs table from files on startup.
- [ ] Test all destructive prompt and I/O failure branches.

## 16. Help, polish, and accessibility

- [ ] Add a concise syntax and job-file reference.
- [ ] Explain Draft versus Historical mode in the UI.
- [ ] Add About dialog with version and license.
- [ ] Use palette roles rather than fixed theme colors.
- [ ] Add application/status icons with text and tooltips as backup.
- [ ] Verify high-DPI behavior and resizing.
- [ ] Verify keyboard access to Jobs, all text panes, and run/file actions.
- [ ] Verify screen-reader names for icon-only controls.
- [ ] Make errors state the failed action and recovery step.
- [ ] Remove debug prints from normal startup/execution.

## 17. Automated acceptance tests

- [x] `add(2, 3)` reaches `5` with documented rules/built-ins.
- [ ] Two input lines produce two result/trace sections in one job.
- [ ] Trace text reports every rule, position, and binding in order.
- [x] Reordering rule source lines changes priority deterministically.
- [x] A nested redex rewrites at the expected non-root position.
- [ ] A self-loop becomes a cached step-limit job at exactly the limit.
- [ ] Stop produces a cached cancelled job and returns control to the UI.
- [ ] Selecting a row reloads exact rules, inputs, and output without evaluation.
- [ ] Duplicate creates an editable draft and a later run gets a new job ID.
- [ ] The original job file remains unchanged after duplicate/edit/run.
- [ ] Restart rebuilds all valid Jobs rows from cached JSON job files.
- [ ] Export/open round-trips the complete job text.
- [ ] Malformed files do not prevent valid jobs from loading.
- [ ] The window remains responsive during evaluation and large trace loading.

## 18. Release readiness

- [ ] Run `ruff format --check .`.
- [ ] Run `ruff check .`.
- [ ] Run `mypy src`.
- [ ] Run the full pytest suite.
- [ ] Perform a clean-environment install and launch test.
- [ ] Perform the complete v1 acceptance scenario in `plan.md` on Windows.
- [ ] Smoke-test draft prompts, cancellation, cache failures, deletion, and large
  traces.
- [ ] Confirm README setup commands match actual package metadata.
- [ ] Document known limitations and defer rich notebook features explicitly.
- [ ] Build a Windows artifact only after source installation is reliable.

## Post-v1 backlog

- [ ] Add a read-only interactive trace tree backed by structured events.
- [ ] Add visual notebook cells as an alternate projection of input lines.
- [ ] Define per-cell run semantics relative to immutable job identity.
- [ ] Add HTML/Markdown rendering while retaining portable plain text.
- [ ] Add syntax highlighting after plain editing is stable.
- [ ] Add outermost/user-directed strategies and breakpoints.
- [ ] Add branching exploration of all applicable rewrites.
- [ ] Add named modules, constants, and imports.
- [ ] Add content hashes and result reuse after format stability.
- [ ] Consider SQLite only when cache query volume requires an index.
- [ ] Add notebook tests, grading reports, and packaging/signing workflows.
