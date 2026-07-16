# Ruleset Notebook

Ruleset Notebook is a planned PySide6 desktop workbench for experimenting with
term-rewriting systems. Version 1 deliberately uses plain text instead of rich
notebook cells: write a rules file, write a list of input terms, run them, and
keep the complete run as a reloadable job.

> Status: working v1 prototype. The PySide6 interface and CLI now share the term
> model, text parser, and rewrite engine under `src/ruleset_notebook`. Job storage
> and the current window remain intentionally simple.

## Version 1 in one table

The core v1 record is a cached job:

| Job ID | Rules | Notebook inputs | Results / traces |
|---|---|---|---|
| `01J...` | Exact rules text used by the run | Exact input text used by the run | Final results, step traces, status, and errors |

Every run creates a new job ID and captures all three text blocks. Reloading a
job restores the exact rules, inputs, results, and traces from that run. Editing
and running a restored job creates a new job rather than changing the historical
record.

This keeps the first version simple and useful:

- the input format is ordinary UTF-8 text;
- a job is a reproducible snapshot, not a mutable collection of UI cells;
- generated results are cached with the inputs that produced them;
- old runs remain inspectable after rules or inputs change;
- richer cell and HTML-style presentation can be added later without changing
  the rewriting engine.

## Intended v1 interface

The application has a compact job-history table and three plain-text panes:

```text
+------------------------------------------------------------------------+
| Jobs                                                                   |
| Job ID       | Rules | Inputs | Result | Status      | Created          |
| 01J...A      | 2     | 1      | 5      | normal form| 2026-07-15 13:10 |
+----------------------+----------------------------+--------------------+
| Rules                | Notebook inputs            | Results / traces   |
|                      |                            |                    |
| add-zero:            | add(2, 3)                  | input: add(2, 3)   |
| add(x, 0) => x       |                            | ...                |
|                      |                            | result: 5          |
+----------------------+----------------------------+--------------------+
```

- **Jobs:** one row per cached run. Selecting a row loads its saved text into the
  three panes.
- **Rules:** a plain-text editor with one ordered rule per line.
- **Notebook inputs:** a plain-text editor with one input term per non-empty line.
- **Results / traces:** read-only plain text containing the result and reduction
  trace for every input.

The essential actions are New Draft, Run, Stop, Open Job File, Save/Export Job,
Duplicate Job as Draft, and Delete Cached Job. V1 does not need per-cell Run
buttons, draggable cells, rich output widgets, or an HTML renderer.

## Plain-text workflow

Rules are written in order:

```text
add(x, 0) => x
add(x, y) => add(inc(x), dec(y)) when y > 0
```

Rule names are optional. A named rule can still use
`add-zero: add(x, 0) => x`. When the prefix is omitted, the parser generates a
trace name from the LHS symbol and physical line number, such as `add-2`.

Within a rule, lowercase leaf names such as `x` and `y` are variables. Function
symbols are unambiguous because they are followed by parentheses. Use an
uppercase leaf such as `Zero` when a rule needs a concrete symbolic constant.
Notebook inputs are concrete terms, so a lowercase leaf there remains a symbol.

In the current v1 parser, negative numbers are signed integer literals (for
example, `-3`), not a separate unary operator. Floats, quoted strings, and
span-aware diagnostics remain planned parser work.

Notebook inputs are also plain text, one term per non-empty line:

```text
add(2, 3)
add(10, 4)
```

Running the draft snapshots both blocks before evaluation. The result pane is
generated text, for example:

```text
input 1: add(2, 3)
  0. add(2, 3)
  1. add(3, 2)    [add-step; x=2, y=3]
  2. add(4, 1)    [add-step; x=3, y=2]
  3. add(5, 0)    [add-step; x=4, y=1]
  4. 5            [add-zero; x=5]
result: 5
status: normal form
```

Blank lines and lines beginning with `#` are ignored. A syntax error reports its
line and column and prevents the draft from becoming a completed job. The failed
attempt may still be cached with `parse error` status so the exact failure can be
revisited.

## Job file format

V1 jobs are versioned JSON objects stored as human-readable UTF-8 `.rsjob` files.
The JSON object keeps the three authoritative text blocks as ordinary string
fields, so rules and traces do not need a custom delimiter parser:

```json
{
  "format": "ruleset-notebook-job",
  "version": 1,
  "job_id": "01J...",
  "status": "normal form",
  "result_summary": [["add(2, 3)", "5"]],
  "rules_text": "add(x, 0) => x\n...",
  "inputs_text": "add(2, 3)\n",
  "results_text": "result: 5\n..."
}
```

`result_summary` is a list of `[input, output]` pairs. The Jobs table renders
those pairs compactly as `input:output; input:output`.

Each job still has its own file and is written atomically. The Jobs table scans
the cache directory and parses valid JSON records; malformed files are ignored
with a warning. JSONL remains a possible future format for one append-only history
file, but is unnecessary while the cache is one file per job.

## Term rewriting behavior

Term rewriting repeatedly replaces a matching part of a term with another term.
The initial language supports:

- literals such as integers, floats, strings, and booleans;
- symbols such as `zero`;
- nested terms such as `pair(left, tree(a, b))`;
- contextual lowercase pattern variables such as `x`;
- ordered `LHS => RHS` rules;
- restricted guards such as `x > 0 and x <= 10`;
- a small, documented set of numeric built-ins.

V1 uses deterministic left-to-right innermost rewriting. Enabled rules are tried
in file order, and the first valid match wins. Every successful rewrite is added
to the plain-text trace.

Evaluation has explicit step and term-depth limits and can be cancelled. A loop
therefore produces a partial cached trace with a `step limit` result rather than
freezing the application or overflowing Python's call stack. Guards use a
restricted parser and never execute arbitrary Python.

## Architecture direction

The parser and rewriting engine remain independent of PySide6:

```text
PySide6 UI -> job/draft services -> parser + engine -> immutable domain
```

The editable `Draft` owns current rules and input text. Starting a run creates an
immutable `JobRequest` snapshot. Evaluation runs outside the GUI thread and
returns a structured result. A formatter turns that result into the saved trace
text, and the job store atomically caches the whole record.

The structured result remains internal even though v1 displays plain text. This
is the seam that later supports tree widgets, notebook cells, HTML rendering, or
interactive trace views without rewriting the evaluator.

## Running the prototype

After the editable install, launch the GUI with either command:

```powershell
python -m ruleset_notebook
ruleset-notebook
```

The root script remains as a compatibility shortcut for repo development:

```powershell
python app.py
```

The CLI is a separate front end over the same parser and domain model:

```powershell
ruleset-notebook-cli "add(2, 3)"
```

Shared behavior lives in `language.py` and `engine.py`; the GUI lives in
`ui/main_window.py`. The root `app.py` contains no parser or evaluator logic.

## Development roadmap

1. Package the project and characterize the current engine with tests.
2. Add immutable terms, rule/input text parsing, formatting, and diagnostics.
3. Implement deterministic nested rewriting, guards, limits, cancellation, and
   structured trace results.
4. Build the PySide6 job table and three plain-text panes.
5. Implement immutable run snapshots and the atomic text-file job cache.
6. Complete reload, duplicate-as-draft, deletion, tests, and desktop polish.
7. Later, add notebook cells and HTML-like result presentation as projections of
   the same job and trace models.

See [plan.md](plan.md) for the architecture and product plan, and
[todo.md](todo.md) for the implementation checklist.

## Planned development setup

Once packaging is added:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m ruleset_notebook
```

Planned checks:

```powershell
ruff format --check .
ruff check .
mypy src
pytest
```

## Building a Windows executable

The project includes a PyInstaller build script that produces a standalone
application bundle. Install the packaging dependency first, then run the script:

```powershell
python -m pip install -e ".[dev]"
python build.py
```

The output is written to `dist/RulesetNotebook/`. The executable does not require
Python to be installed on the target machine. To distribute, zip the entire
`dist/RulesetNotebook` directory.

Known PySide6 packaging notes:
- The `--onedir` mode is used because it is more reliable than `--onefile` for
  Qt applications on Windows.
- UPX compression is explicitly disabled. It offers little benefit for this Qt
  bundle and can fail on Python and Shiboken binaries with modern Windows load
  configuration metadata.
- PyInstaller follows the package GUI entry point and the PySide6 hooks collect
  the Qt libraries and platform plugins the demo actually uses. The build does not
  use `--collect-all PySide6`, which would pull in unrelated Qt modules and their
  optional native dependencies.
- Antivirus software may flag the bundled executable; this is a common
  false-positive for PyInstaller-packaged Qt apps.

Version 1 is a plain-text job runner and history browser. It is not yet a visual
notebook, HTML document, theorem prover, or general Python environment. Cells,
rich output, branching exploration, modules, caching by content hash, automated
grading, and alternative rewrite strategies are later work.

License information has not yet been added.
