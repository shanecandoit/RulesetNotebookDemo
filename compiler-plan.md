# C Compiler Pipeline - Experiment Plan

## 1. Goal

Build a second, independent pipeline that takes the same rules/inputs text
Ruleset Notebook already parses and pushes it through a small "compiler":

```text
rules.txt + inputs.txt
    -> (1) YAML intermediate representation
    -> (2) generated C source
    -> (3) gcc compile
    -> (4) captured compiler errors, if any
    -> (5) run the binary AND the Python evaluator, compare output/trace
```

The near-term target is a **simple demo**: the existing `add`/`inc`/`dec`
arithmetic ruleset from `app.py` (see `DEFAULT_RULES` /
`evaluate_with_trace`) compiling to a small C program that reproduces the
same normal form and the same step-by-step trace as the Python engine, with
pytest driving every stage end to end.

This is an experiment track, not a v1 requirement. It should not block or
complicate the PySide6/job-cache work described in [plan.md](plan.md); treat
it as a separate, independently testable subsystem that happens to share the
term/rule data model.

## 2. Why a YAML step instead of rules text -> C directly

Rules/inputs text -> C in one hop couples the hand-written text grammar to
code generation, so every grammar tweak risks breaking the compiler. Splitting
at YAML gives:

- a stable, inspectable intermediate representation (IR) that's easy to unit
  test on its own (parse -> YAML -> parse back and diff the AST);
- a natural point to hand-author test fixtures without going through the text
  parser at all;
- a place to add compiler-only metadata later (e.g. numeric type hints, arity
  checks) without touching the notebook's text format.

The YAML IR is a thin, direct serialization of the existing `Term`/`Rule`
model - it is not a new language design.

## 3. Prerequisite: extract a Qt-free language core

`app.py` currently imports `PySide6` at module scope, so anything that wants
`parse_rules`, `parse_term`, `Term`, `Rule`, `evaluate_with_trace`, etc. must
also import Qt. The compiler pipeline (and its pytest suite) must not require
a working PySide6/Qt install just to parse text and run the reference
evaluator.

Before Stage 1 work starts:

1. Move `Term`, `Const`, `Var`, `Func`, `match`, `substitute`, `Rule`,
   `evaluate`, `evaluate_with_trace`, `parse_term`, `parse_rules`,
   `parse_inputs`, `parse_guard`, and the demo syntax errors into
   `src/ruleset_notebook/language.py` (name open to bikeshedding).
2. Re-export or import from there in `app.py` so the existing GUI keeps
   working unchanged.
3. Add `tests/unit/test_language.py` (or repoint the existing
   `tests/unit/test_prototype.py` / `test_demo_parser.py`) at the new module.

This also happens to be useful for v1 independently of the compiler
experiment, since [plan.md](plan.md) already calls for the language layer to
stay independent of Qt.

## 4. Stage 1 - rules/inputs text to YAML IR

New module: `src/ruleset_notebook/compiler/ir.py`.

Direct structural mapping of the existing `Term`/`Rule` classes:

```yaml
rules:
  - name: add-zero
    lhs: {func: add, args: [{var: x}, {const: 0}]}
    rhs: {var: x}
    guard: null
  - name: add-step
    lhs: {func: add, args: [{var: x}, {var: y}]}
    rhs:
      func: add
      args:
        - {func: inc, args: [{var: x}]}
        - {func: dec, args: [{var: y}]}
    guard: {var: y, op: ">", value: 0}

inputs:
  - line: 1
    term: {func: add, args: [{const: 2}, {const: 3}]}
  - line: 2
    term: {func: add, args: [{const: 10}, {const: 4}]}
```

Functions:

- `term_to_ir(term: Term) -> dict`
- `ir_to_term(node: dict) -> Term`
- `rules_to_yaml(rules: list[Rule]) -> str`
- `inputs_to_yaml(inputs: list[tuple[int, Term]]) -> str`
- `yaml_to_ir(text: str) -> dict` (schema-validated, see below)

Guards are restricted to the existing `?x <op> integer` shape, so they
serialize as a flat `{var, op, value}` record rather than an expression tree.
If guards grow more general later, this record becomes a tagged union the
same way terms already are.

**Schema validation:** use a small hand-written validator (a handful of
`isinstance`/`KeyError` checks with clear messages) rather than pulling in a
schema library - the IR is small and stable, and clear Python exceptions are
easier to unit test than a schema-library stack trace.

**Round-trip test contract:** `ir_to_term(term_to_ir(t)) == t` for every term
shape the demo grammar can produce, and the same for a full rules file
parsed from text, serialized to YAML, and reloaded. This is the cheapest,
least brittle test in the whole pipeline and should be the first thing
written.

## 5. Stage 2 - YAML IR to C source

New module: `src/ruleset_notebook/compiler/codegen.py`.

### Chosen approach for the demo: a data-driven runtime, not per-rule codegen

Two designs were considered:

| Approach | Description | Tradeoff |
|---|---|---|
| **Data-driven runtime (chosen for the demo)** | Emit a small, fixed, hand-written C runtime (`runtime/term.c`, `runtime/term.h`) implementing generic `match`, `substitute`, `rewrite_step`, `evaluate_with_trace` over a tagged-union `Term`. Codegen only emits **data**: static tables describing each rule's LHS/RHS/guard, plus a generated `main()` that builds the input terms and calls the runtime. | Small, easy to get byte-for-byte correct relative to the Python engine, easy to test (the runtime is compiled once and reused). This is "compiling data into a C program," not "compiling rules into native control flow." |
| **True per-rule codegen (stretch goal)** | Emit a distinct C function per rule that pattern-matches with `if`/`switch` and constructs the RHS directly, closer to what a real term-rewriting compiler (or a pattern-match compiler à la Maranget) would produce. | More representative of "compiling rules to C," more C code to generate and debug, more ways for generated code to fail to compile. |

Start with the data-driven runtime so Stages 3–5 and the pytest harness can
be built and proven out against something simple. Keep `codegen.py`
structured so the data-driven backend and a future per-rule backend can
coexist behind the same `yaml_to_c_source(ir) -> str` entry point.

### Term representation in C

```c
typedef enum { TERM_CONST_INT, TERM_VAR, TERM_FUNC } TermTag;

typedef struct Term {
    TermTag tag;
    long int_value;        /* TERM_CONST_INT */
    const char *name;      /* TERM_VAR name, or TERM_FUNC name */
    struct Term **args;    /* TERM_FUNC only */
    int arg_count;         /* TERM_FUNC only */
} Term;
```

The demo grammar's `Const` only needs to support integers (see
`DEFAULT_RULES`); string/float/bool constants are explicitly out of scope
for this experiment and should raise a clear "unsupported for compilation"
error from `codegen.py` rather than silently mishandling them.

Memory: allocate every `Term` with `malloc` and never `free` - the compiled
binary is a short-lived CLI process that runs one job and exits, so leaking
for the process lifetime is the correct, simplest choice. Do not add a GC or
arena allocator for this experiment.

Built-ins (`+`, `-`, `inc`, `dec`) are implemented once in the runtime, since
they are fixed prototype behavior in `substitute()`, not user-defined rules.

## 6. Stage 3 - invoke gcc

New module: `src/ruleset_notebook/compiler/toolchain.py`.

```python
def compile_c(source_path: Path, output_path: Path, *, timeout: float = 30.0) -> CompileResult:
    result = subprocess.run(
        ["gcc", "-std=c11", "-Wall", "-Wextra", "-Werror", "-O0",
         "-o", str(output_path), str(source_path)],
        capture_output=True, text=True, timeout=timeout,
    )
    return CompileResult(
        ok=result.returncode == 0,
        stdout=result.stdout,
        stderr=result.stderr,
        returncode=result.returncode,
        binary_path=output_path if result.returncode == 0 else None,
    )
```

Notes:

- `-Wall -Wextra -Werror` is deliberate: warnings from *generated* code are
  almost always codegen bugs (implicit int, unused variable, format-string
  mismatch), and turning them into hard failures catches them at compile
  time instead of as a silent runtime divergence in Stage 5.
- Always pass an explicit `timeout` - a hung `gcc` (e.g. spawned into a
  broken toolchain) must not hang the test suite.
- Resolve `gcc` via `shutil.which("gcc")` once and pass the full path in, so
  the toolchain module has one place that knows whether a compiler is even
  available.
- On this machine, MinGW-w64 gcc is already installed via scoop:
  `C:\Users\shane\scoop\apps\mingw\current\bin\gcc.exe`, version 16.1.0
  (`x86_64-posix-seh`). Document this as the expected dev-machine toolchain;
  don't assume MSVC (`cl.exe`) is available or targeted.
- Binaries built by MinGW gcc on Windows are `.exe`; build the output path
  with that suffix explicitly rather than assuming a POSIX-style bare
  executable name.

## 7. Stage 4 - reporting compiler errors

`CompileResult.stderr` from gcc is real GCC diagnostic text (file:line:col,
squiggles, `note:` continuations). For the pytest suite, do not try to parse
or match specific GCC diagnostic wording - GCC's exact message text is not a
stable contract across versions. Instead:

- Assert `CompileResult.ok is True` for all "should compile" fixtures, and
  print the full `stderr` on failure (pytest does this by default when an
  assert fails on a dataclass/string - no extra work needed as long as the
  test failure message includes `result.stderr`).
- For deliberately-invalid-codegen regression tests (if any get added later),
  assert `ok is False` and that `stderr` is non-empty - not its exact
  contents.
- Surface `CompileResult` through the same reporting path a future "Run"
  action in the app could use: `status: compile error` plus the raw stderr
  text, mirroring how `parse error` already works in `app.py`.

## 8. Stage 5 - run both programs and diff

`toolchain.py` also runs the compiled binary:

```python
def run_binary(binary_path: Path, *, timeout: float = 10.0) -> RunResult:
    result = subprocess.run(
        [str(binary_path)], capture_output=True, text=True, timeout=timeout,
    )
    return RunResult(stdout=result.stdout, stderr=result.stderr, returncode=result.returncode)
```

And the pipeline runs the existing Python reference:

```python
def run_python_reference(rules: list[Rule], inputs: list[tuple[int, Term]]) -> str:
    ...  # calls evaluate_with_trace per input, formats identically to Stage 9's contract
```

### Output contract (this is the part that keeps the comparison from being brittle)

Do **not** compare Python's `repr()`-flavored trace text against whatever a
hand-written C `printf` happens to produce. Instead, define one canonical,
versioned line-oriented trace format that both the C runtime and a small
Python formatter target on purpose:

```text
INPUT 1 LINE 1 TERM add(2, 3)
STEP 0 add(2, 3)
STEP 1 add(3, 2) RULE add-step
STEP 2 add(4, 1) RULE add-step
STEP 3 add(5, 0) RULE add-step
STEP 4 5 RULE add-zero
RESULT 5
STATUS normal-form
```

This is deliberately *not* the same text the GUI's `results_edit` pane shows
(that format is free to stay human-oriented and can change independently).
The compiler's canonical format exists purely so two independent programs
can agree on it byte-for-byte:

- fixed field order, single spaces, no trailing whitespace;
- integers only, no locale-dependent number formatting;
- rule name only in the trace (no binding dump) to start - bindings can be
  added later once C-side term printing is solid.

`compare_outputs(python_text, c_text) -> DiffResult` is then a straight
string/line diff, and a failing test can print a unified diff for a readable
pytest failure.

## 9. Test strategy

```text
tests/
  unit/
    test_language.py           # existing engine, moved (see Section 3)
  compiler/
    conftest.py                 # gcc_path fixture, skip marker
    test_ir_roundtrip.py        # Stage 1, no subprocess, fast
    test_codegen_smoke.py       # Stage 2, no gcc: generated source is non-empty,
                                 #   contains expected symbol names, no assert on exact text
    test_toolchain.py           # Stage 3/4, requires gcc, tiny hand-written C fixtures
    test_end_to_end.py          # Stages 1-5 together, requires gcc
  fixtures/
    demo_add.rules
    demo_add.inputs
```

Key decisions to keep the gcc-wrapping tests useful instead of flaky:

- **Skip, don't fail, when gcc is missing.**
  ```python
  requires_gcc = pytest.mark.skipif(
      shutil.which("gcc") is None, reason="gcc not found on PATH"
  )
  ```
  A session-scoped `gcc_path` fixture resolves the path once and every
  compiler test depends on it, so a missing toolchain produces one clear
  "skipped: gcc not found" summary instead of N confusing failures.

- **Everything filesystem-touching uses `tmp_path`.** Each test gets its own
  directory for the generated `.c` file and `.exe`; nothing is written into
  the repo, and parallel test runs (`pytest -n auto`) can't collide.

- **Explicit timeouts on every `subprocess.run`.** A miscompiled or
  infinite-looping generated program must produce a test *failure*
  (`subprocess.TimeoutExpired`), never a hung CI job. Treat a step limit in
  the term-rewriting sense (Section 8's `STATUS step-limit`) as the normal,
  expected way runaway rules terminate - the process-level timeout is a
  backstop for genuine C bugs (e.g. an infinite C `while`, not a term
  rewriting loop), so it should be generous relative to the runtime's own
  step limit.

- **Mark the gcc-dependent tests `slow`/`compiler`** via `pytest.ini`
  markers, so `pytest -m "not compiler"` gives a fast default loop for
  everyday development, and CI (or a pre-push check) runs the full marker
  set including compilation.

- **No golden-file diffing of generated C source.** Comparing generated `.c`
  text against a stored golden file is exactly the kind of brittle test the
  user flagged as a risk - it breaks on any harmless formatting change to
  the code generator. Prefer behavioral assertions (it compiles, it runs, it
  produces the right canonical trace) over text-equality assertions on
  generated source. The one exception: `test_codegen_smoke.py` may assert
  small substrings are present (e.g. the rule name appears somewhere in the
  emitted data table) as a fast, gcc-free sanity check before paying for a
  real compile.

- **One fixture pair per interesting behavior**, not one giant ruleset:
  `demo_add` (normal form), a guard-driven fixture, and a deliberately
  looping ruleset that should hit `STATUS step-limit` identically on both
  sides. Small fixtures make a failing diff easy to read.

## 10. Milestones

1. Extract the Qt-free language core (Section 3) and repoint existing tests.
2. Stage 1: IR + round-trip tests. No C, no gcc yet.
3. Toolchain spike: a single pytest test that writes a **hand-written**
   "hello world" `.c` file, compiles it with `compile_c`, runs it, and
   checks stdout - proves the subprocess/tmp_path/timeout/skip plumbing
   before any codegen exists.
4. Stage 2: data-driven codegen backend + runtime (`term.c`/`term.h`) for
   the `add`/`inc`/`dec` demo ruleset only.
5. Stage 5: canonical trace formatter on the Python side; wire up
   `compare_outputs`.
6. End-to-end test: `demo_add.rules` + `demo_add.inputs` -> YAML -> C ->
   compiled -> run -> byte-identical canonical trace vs. the Python
   reference. This is the "simple demo" deliverable.
7. Add the guard fixture and the step-limit fixture once (6) is green.
8. Stretch: per-rule codegen backend (Section 5's second table row) behind
   the same `yaml_to_c_source` entry point, with its own end-to-end test
   reusing the same canonical-trace comparison.

## 11. Open questions / risks

- **Nested-position rewriting.** `app.py`'s current `evaluate()` reduces
  arguments before the root (`Func` args evaluated first, then a root
  rewrite attempt), while `evaluate_with_trace()` used by the GUI only
  rewrites at the root (`position=root` in every trace line, per
  `_attempt_rewrite`). Decide which semantics the compiler targets - most
  likely `evaluate_with_trace`'s root-only strategy, since that's what the
  GUI actually shows and caches. Call this out explicitly in code review; it
  is easy to silently compile the wrong one.
- **Integer overflow / width.** Python ints are arbitrary precision; C
  `long` is not. Fine to ignore for the demo ruleset (small numbers) but
  worth a one-line comment in `codegen.py` so it isn't mistaken for a solved
  problem.
- **MinGW vs. MSVC.** If this ever needs to run in CI on a different Windows
  image (or on Linux/macOS runners), gcc's location and default target may
  differ; keep the compiler invocation confined to `toolchain.py` so
  swapping toolchains later doesn't touch codegen.
- **Scope discipline.** It's tempting to grow the C runtime toward a "real"
  compiler (arbitrary-arity built-ins, strings, floats, AC matching). Resist
  until the milestone-6 demo is solid - see [reading.md](reading.md) for how
  much further this rabbit hole can go.
