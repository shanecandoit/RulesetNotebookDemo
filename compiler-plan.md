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

First, run a small Ivy program on the development machine, then emit Ivy for
the addition example and a guarded rule with an ordered fallback. Compare
results with Python on a small integer subset. For feature parity, the
lowering must preserve left-to-right innermost evaluation, first-match rule
priority, guard behavior, and built-in fallback. It must also preserve
structural equality for repeated variables and explicitly handle duplication
and erasure of bindings when wiring the net.

Trace and limit parity require counting source rewrite steps and recording
their positions. A single source step can take multiple IVM interactions.
Matching the C backend's signed 64-bit arithmetic also needs an encoding or
runtime support for wider values. [IVM extrinsics](https://vine.dev/docs/ivy-ivm/extrinsics)
