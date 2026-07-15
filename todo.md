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
- [x] Preserve the current `app.py` example behavior in characterization tests.
- [ ] Remove or replace the top-level proof-of-concept script only after those
  tests pass against the new engine.

## 1. Domain types

- [ ] Implement immutable term variants for variables, literals, and applications.
- [ ] Represent application children as tuples.
- [ ] Define structural equality and hashing tests.
- [ ] Define `SourcePosition` and `SourceSpan` with line/column/offset data.
- [ ] Define typed diagnostics with code, severity, message, span, and hint.
- [ ] Implement immutable `Rule` with UUID, name, ASTs, guard, and enabled state.
- [ ] Implement `EvaluationSettings` with validated step/depth limits.
- [ ] Define `RewriteEvent`, `EvaluationResult`, `StopReason`, and engine errors.
- [ ] Add readable `repr` output for development without making it canonical
  serialization.

## 2. Term lexer and parser

- [ ] Tokenize identifiers, `?variables`, integers, floats, strings, punctuation,
  comparison operators, and keywords.
- [ ] Track source spans across whitespace and newlines.
- [ ] Support escaped quotes, backslashes, tabs, and newlines in strings.
- [ ] Produce a diagnostic for invalid characters and unterminated strings.
- [ ] Parse bare symbols and function-like applications.
- [ ] Parse nested and grouped terms.
- [ ] Reject variables in notebook input mode.
- [ ] Reject missing commas, missing parentheses, and trailing unexpected tokens
  with precise spans.
- [ ] Decide whether negative numbers are signed literals or unary syntax and
  encode that decision in tests and the README syntax section.
- [ ] Add parameterized valid/invalid parser tests.

## 3. Formatting and rule validation

- [ ] Implement a canonical term formatter.
- [ ] Escape literal strings deterministically.
- [ ] Add parse/format/parse round-trip tests.
- [ ] Parse or assemble rules from name, LHS, RHS, and guard source fields.
- [ ] Require at least one non-variable symbol/literal shape in an LHS if needed
  to prevent catch-all accidents; document the final choice.
- [ ] Collect all variables bound by the LHS.
- [ ] Reject RHS references to variables not present in the LHS.
- [ ] Accept optional explicit rule names and generate
  `<lhs-symbol>-<line-number>` when omitted.
- [ ] Reject duplicate effective rule names so saved trace lines identify rules
  unambiguously.
- [ ] Return validation diagnostics without throwing UI-facing exceptions.

## 4. Guards

- [ ] Add guard AST nodes for values, comparisons, conjunctions, and grouping.
- [ ] Parse `==`, `!=`, `<`, `<=`, `>`, `>=`, and `and`.
- [ ] Resolve guard variables only from match bindings.
- [ ] Reject unbound guard variables during validation.
- [ ] Define comparison behavior for mismatched literal types.
- [ ] Return a typed guard failure for invalid runtime comparisons.
- [ ] Confirm no guard path imports or calls Python `eval`/`exec`.
- [ ] Test true, false, compound, grouped, missing-variable, and type-error cases.

## 5. Matcher and substitution

- [ ] Match equal literals with deliberate bool/int behavior.
- [ ] Match applications by symbol and arity before recursing.
- [ ] Bind a new pattern variable to the subject subtree.
- [ ] Require repeated pattern variables to match structurally equal subtrees.
- [ ] Ensure a failed match does not leak partial bindings.
- [ ] Substitute RHS variables recursively from an immutable bindings map.
- [ ] Retain a defensive error for unbound substitution variables.
- [ ] Test nested terms, repeated variables, arity mismatch, literal mismatch, and
  immutable input preservation.

## 6. Rewrite engine

- [ ] Define a term-position representation using child-index tuples.
- [ ] Implement reading and replacing a subtree at a position.
- [ ] Enumerate candidate positions in left-to-right innermost order.
- [ ] Try enabled rules in list order at each candidate position.
- [ ] Evaluate a rule guard after successful matching and before substitution.
- [ ] Apply only the first successful rule per step.
- [ ] Restart traversal from the root after every successful step.
- [ ] Implement numeric built-ins for `inc`, `dec`, `add`, `sub`, `mul`, and `div`,
  or revise the acceptance example to match the final primitive set.
- [ ] Define user-rule versus built-in priority and cover it with tests.
- [ ] Detect division by zero and invalid primitive operand types.
- [ ] Count successful rewrite steps consistently.
- [ ] Stop at normal form.
- [ ] Stop exactly at `max_steps` and return the partial term.
- [ ] Stop before a replacement exceeds `max_depth`.
- [ ] Check cancellation during traversal and between steps.
- [ ] Optionally detect repeated full terms and annotate a likely cycle.
- [ ] Ensure ordinary evaluation is iterative enough to avoid Python recursion
  failure on a long rewrite sequence.

## 7. Trace data

- [ ] Record input, output, rule UUID/name, bindings, position, and event kind for
  every successful rewrite.
- [ ] Freeze or copy bindings before storing them.
- [ ] Record the final stop reason independently of rewrite events.
- [ ] Add optional elapsed time without using it in equality assertions.
- [ ] Test the exact rule sequence and positions for root and nested rewrites.
- [ ] Test trace output for normal form, limit, cancellation, and runtime error.
- [ ] Add a deterministic plain-text formatter for complete multi-input results.

## 8. Draft and job models

- [ ] Implement mutable `Draft` with rules text, inputs text, settings, and dirty
  state.
- [ ] Keep selected historical job state separate from the editable draft.
- [ ] Implement sortable `JobId` generation using UUIDv7 or ULID semantics.
- [ ] Implement immutable `JobRequest` containing exact source text, parsed rules
  and inputs, settings, identity, and creation timestamp.
- [ ] Implement immutable `JobRecord` containing all request fields plus terminal
  status, results text, structured results, and completion timestamp.
- [ ] Implement lightweight `JobSummary` for header-only table rows.
- [ ] Create default addition rule/input text in one example factory.
- [ ] Ensure every Run attempt receives a unique job ID.
- [ ] Decide and test automatic caching of parse-error attempts; automatic caching
  is the preferred v1 behavior.
- [ ] Implement Duplicate as Draft without copying job ID, status, or results.

## 9. Plain-text job format and cache

- [ ] Define `RULESET-NOTEBOOK-JOB 1` and the `.rsjob` extension.
- [ ] Define required metadata headers, header ordering, timestamps, status names,
  counts, and result-summary escaping.
- [ ] Define `RULES`, `INPUTS`, and `RESULTS-AND-TRACES` section delimiters.
- [ ] Reject or escape source lines that conflict with reserved delimiters.
- [ ] Serialize exact UTF-8 rules, inputs, and generated output blocks.
- [ ] Normalize newlines consistently and document the choice.
- [ ] Parse headers without loading complete traces.
- [ ] Fully validate header values and section order on record load.
- [ ] Reject duplicate/missing sections and unsupported future versions.
- [ ] Implement one cache file per job ID.
- [ ] Scan only `.rsjob` headers to build the job list.
- [ ] Ignore temporary/unrelated files while reporting malformed job files.
- [ ] Write a temporary file, flush it, and atomically replace the target.
- [ ] Never expose a row as cached before atomic persistence succeeds.
- [ ] Implement read, write, delete, import/open, and export operations.
- [ ] Test all terminal statuses and simulated write failures.
- [ ] Test that two identical runs produce distinct IDs and files.

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
- [ ] Continue to later inputs after a per-input runtime error unless cancelled.
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
- [ ] Implement Open Job File with validation and clear errors.
- [ ] Implement Export Job using `.rsjob` by default.
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

- [ ] `add(2, 3)` reaches `5` with documented rules/built-ins.
- [ ] Two input lines produce two result/trace sections in one job.
- [ ] Trace text reports every rule, position, and binding in order.
- [ ] Reordering rule source lines changes priority deterministically.
- [ ] A nested redex rewrites at the expected non-root position.
- [ ] A self-loop becomes a cached step-limit job at exactly the limit.
- [ ] Stop produces a cached cancelled job and returns control to the UI.
- [ ] Selecting a row reloads exact rules, inputs, and output without evaluation.
- [ ] Duplicate creates an editable draft and a later run gets a new job ID.
- [ ] The original job file remains unchanged after duplicate/edit/run.
- [ ] Restart rebuilds all valid Jobs rows from cache headers.
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
