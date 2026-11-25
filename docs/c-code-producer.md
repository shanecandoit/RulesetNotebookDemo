# C code producer

The C producer takes the same rules and inputs you enter in Ruleset Notebook
and writes a self-contained C11 file. It embeds the supplied rules and inputs
in the program, so you can build and run the file without Python or Qt.

## Generate and run a program

Run these Bash commands from the Ruleset Notebook repository root. Use Python
3.11 or newer for generation and GCC on your `PATH` for compilation. The
example uses a temporary directory for the source files and executable.

```bash
demo_dir=$(mktemp -d)

cat > "$demo_dir/rules.txt" <<'RULES'
add-zero: add(x, 0) => x
add-step: add(x, y) => add(inc(x), dec(y)) when y > 0
RULES

cat > "$demo_dir/inputs.txt" <<'INPUTS'
add(2, 3)
add(10, 4)
INPUTS

PYTHONPATH=src python -m ruleset_notebook.compiler \
  "$demo_dir/rules.txt" "$demo_dir/inputs.txt" \
  -o "$demo_dir/notebook.c"

gcc -std=c11 -Wall -Wextra -Werror \
  "$demo_dir/notebook.c" -o "$demo_dir/notebook.exe"

"$demo_dir/notebook.exe"
```

The executable prints `RESULT 5` and `RESULT 14`, each with
`STATUS normal form`. It also prints the full rewrite trace. Rewrite
positions are zero-based child indexes, with `root` for the entire term.

Give the producer two UTF-8 files, one rule or input per line. Blank lines and
lines beginning with `#` are skipped. Input numbers in the trace follow the
order of the parsed terms, while `LINE` shows the original file line number.
Regenerate the C file when you change either source file.

Use `--verify` to compile and run the generated source in a temporary
directory and compare its trace with Python. The command reports a trace diff
or GCC diagnostics on failure.

```bash
PYTHONPATH=src python -m ruleset_notebook.compiler \
  "$demo_dir/rules.txt" "$demo_dir/inputs.txt" \
  -o "$demo_dir/notebook.c" --verify
```

Omit `-o` to write C source to standard output. Use `--max-steps` and
`--max-depth` to override the defaults of 100 rewrites per input and a
maximum term depth of 1,000.

## Benchmark and verify

Run the benchmark from the repository root. With no file arguments, it
repeats the 97-rewrite countdown with unchanged branches of width 0, 128,
and 512. The widest branch is tested with both repeated and distinct terms.

```bash
PYTHONPATH=src python -m ruleset_notebook.compiler.benchmark
```

Pass a rules file and an inputs file to measure your own workload. Use
`--runs` to set the number of timed runs. The benchmark also accepts
`--max-steps` and `--max-depth`.

```bash
PYTHONPATH=src python -m ruleset_notebook.compiler.benchmark \
  "$demo_dir/rules.txt" "$demo_dir/inputs.txt" --runs 7
```

The report shows total rewrites and Python positions examined, plus median
times for Python evaluation, Python trace formatting, and running the C
process with stdout captured. The GCC time is measured once per case.
The output also reports the C trace size. Each C run is checked against the
Python trace. A mismatch prints a unified diff and returns a nonzero exit
code.

Each run uses the C producer in the current checkout. To test edits to a
generated file or another C implementation, pass
`--c-source path/to/candidate.c` with the two input files. The candidate must
use the same inputs and limits and emit the same `TRACE 1` format.

## How it works

The producer uses the notebook parser, then generates a C function for each
rule. The function checks the left-hand pattern, tests any guard using the
matched terms, and builds the right-hand term. Repeated variables must match
structurally equal terms. The generated `main()` constructs and runs each
input in source order.

The shared C runtime walks children left to right before visiting their
parent. At each position, it tries the generated functions in rule order,
then tries a built-in operation if no rule applies. It records the resulting
term, rewrite kind, name, and position after each successful step.

The backend supports applications, pattern variables, signed 64-bit integer
literals, and integer guards with comparisons and `and`. Generation
rejects string, Boolean, and floating-point literals. Built-in addition,
subtraction, multiplication, increment, and decrement check for overflow.
If a `div` call falls through to the built-in with a nonzero divisor, it
reports an unsupported operation because the Python built-in returns a
floating-point result. User-defined `div` rules can produce integer results.
