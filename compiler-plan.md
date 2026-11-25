# C compiler experiment

The first milestone is a standalone executable for the notebook's addition
example. It embeds a C function for each rule and a `main()` for the two
input terms. The executable must reproduce the Python evaluator's results,
rewrite steps, and stop reasons.

## Pipeline

1. Parse the rules and input text with `language.py`. The parsed `Rule` and
   `Term` objects supply the code generator with patterns, guard expressions,
   replacements, and input line numbers.
2. Emit one C11 source file. Each rule function checks the pattern, compares
   repeated bindings, evaluates its guard, and constructs the replacement.
   Generated `main()` constructs each input and calls the shared runtime.
3. Compile with GCC and run the executable. Compare its versioned trace to
   the trace from `evaluate_with_trace()`, formatted for the same protocol.

## Semantics for the first milestone

- Search left to right, visiting children before the enclosing term. At each
  position, try user rules in source order, followed by the built-in operation.
- Emit a step for each rule or built-in rewrite. Keep the rewrite name, kind,
  position, and complete term after the step.
- Use signed 64-bit integer literals and check built-in arithmetic for
  overflow. Support applications, pattern variables, integer comparisons, and
  short-circuiting guard conjunctions. Built-in division with a nonzero
  divisor requires floating-point support.
- Apply the Python evaluator's step and depth limit behavior. For addition,
  `add(2, 3)` and `add(10, 4)` finish in 10 and 13 steps respectively.
  Each `inc` and `dec` is a separate nested rewrite.

## Verification and follow-up

The integration suite covers addition, structural matching, guard evaluation,
rule precedence, and step and depth limits. GCC-dependent tests use a temporary
directory and skip when GCC is absent.

YAML serialization remains a possible interchange format. The first backend
takes the parser's existing objects directly. Wider literal support and
notebook UI integration are follow-up work.

See the [C producer usage guide](docs/c-code-producer.md) for commands and an
overview of the generated program.

## Ivy backend experiment

Ivy is a second target for the parsed `Rule` and `Term` objects. Its runtime
reduces interaction nets built from labeled combinators and other agents.
[Ivy overview](https://vine.dev/docs/ivy-ivm/ivy) · [IVM overview](https://vine.dev/docs/ivy-ivm/ivm)

### Run the prototype

Build both tools from the tested Vine revision so their Ivy syntax agrees.
Run this command from the Vine checkout. [Tested Vine revision](https://github.com/VineLang/vine/tree/cf0c325834d5bf4c8d43aa36f7fb76faf2496988)

```bash
cargo build --locked -p vine-cli --bin vine --bin ivm
```

Put the resulting `vine` and `ivm` executables on your `PATH`, or supply
their paths with `--vine` and `--ivm`. Run this from the Ruleset Notebook
repository root with Python 3.11 or newer.

```bash
PYTHONPATH=src python -m ruleset_notebook.compiler.ivy \
  rules.txt inputs.txt -o notebook.ivy --verify
```

The producer lowers the parsed rules and inputs to Vine and calls
`vine build` to emit the Ivy file. Its generated program matches rules in
source order at each left-to-right innermost position. Each successful
notebook rewrite contributes one step to the same `TRACE 1` protocol used by
C. Verification compares the full trace with Python, including positions,
partial results, and stop reasons. Use `--max-steps` and `--max-depth` to
set the limits embedded in the program.

Run `ivm run notebook.ivy` from the repository root to see IVM's interaction
statistics alongside the notebook trace. An individual notebook step can
involve multiple IVM interactions. Use `--no-stats` for just the notebook
trace. [IVM overview](https://vine.dev/docs/ivy-ivm/ivm)

The prototype supports integer literals, application patterns, repeated
variables, integer guards, and the integer built-ins `inc`, `dec`, `add`,
`sub`, and `mul`. Vine's exact `Int` arithmetic covers the C backend's signed
64-bit range and agrees with Python on integers beyond that range.
Built-in true division and additional literal types require wider language
support.
