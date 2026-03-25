# Trigex — Trigger Extraction for Guaranteed Regex Activation

This project studies a simple question:

Given a regular expression, can we extract a small set of substrings such that every valid match contains at least one of them?

Those substrings form a guaranteed trigger set. They can be used as a cheap pre-check before running the full regex engine.

## What the project does

- Parses a regex into an AST
- Extracts a sound trigger set for the pattern
- Validates the extracted triggers on generated sample matches
- Compares plain regex matching with trigger-filtered matching
- Prints a lightweight ASCII tree of the regex structure

## Supported regex features

- Concatenation
- Alternation with `|`
- Grouping with `()`
- Optional with `?`
- Repetition with `*` and `+`
- Character classes with `[]`, ranges like `[a-z]`, and negation like `[^ab]`
- Escapes such as `\d`, `\s`, `\w`, and escaped literal metacharacters

Unsupported syntax such as `.`, anchors, unsupported escape sequences, and brace repetition is rejected explicitly.

## How it works

1. `parser/regex_parser.py` builds an AST using recursive descent.
2. `extractor/trigger_extractor.py` builds sound trigger candidates and returns one compact ranked trigger set.
3. `validator/validator.py` generates bounded samples and checks them with Python `re`.
4. `benchmark/performance.py` compares plain `re.search` with trigger-gated matching.
5. `visualization/visualizer.py` prints the regex tree as ASCII.

## Run the project

From the project root:

```bash
python3 main.py 'pre(ab|ac)post'
```

Run with benchmarking:

```bash
python3 main.py '((ab|aab|aaab|aaaab)+c)d' --benchmark --sizes 1000 --rounds 20
```

Run tests:

```bash
python3 -m unittest tests.test_cases
```

## Example output

Command:

```bash
python3 main.py 'pre(ab|ac)post'
```

Output:

```text
Pattern
-------
pre(ab|ac)post

Triggers
--------
'post'

Validation
----------
Valid on generated samples: True
Checked samples: 2
Sample preview: ['preabpost', 'preacpost']

Regex Tree
----------
Concat
├── Literal('p')
├── Literal('r')
├── Literal('e')
├── Group
│   └── Alternate
│       ├── Concat
│       │   ├── Literal('a')
│       │   └── Literal('b')
│       └── Concat
│           ├── Literal('a')
│           └── Literal('c')
├── Literal('p')
├── Literal('o')
├── Literal('s')
└── Literal('t')
```

Another example:

```bash
python3 main.py 'ab|cd'
```

```text
Triggers
--------
'ab', 'cd'
```

This means every valid match contains at least one returned token, even when there is no single substring shared by all branches.

## Benchmark snapshot

Local run for a heavier pattern:

```bash
python3 main.py '((ab|aab|aaab|aaaab)+c)d' --benchmark --sizes 1000 --rounds 20
```

Observed result:

```text
size      positives negatives matches skipped plain(s)    filtered(s) speedup
1000      400       600       400     600     0.022375    0.011701    1.91x
```

For very permissive supported patterns such as `a*`, the benchmark may report `0` negative samples because every generated text matches. In that case the benchmark still runs and reports the real outcome instead of failing.

## When trigger filtering helps

Filtering provides the most benefit when:

1. **High negative ratio** — most input texts do not match the regex. Filtering skips their full NFA traversal at the cost of one fast trigger scan.
2. **Specific triggers** — longer trigger tokens (e.g. `"post"`) appear less often by chance than short ones (e.g. `"a"`), so more negatives are filtered.
3. **Expensive patterns** — regex patterns with alternation, repetition, and backreferences take longer to evaluate, making each skipped evaluation more valuable.

In a network inspection system scanning millions of packets, even a 10 % reduction in full NFA evaluations can meaningfully reduce CPU load.

## Streaming search implementation

The `AhoCorasick` class in `extractor/aho_corasick.py` implements the Aho-Corasick multi-pattern automaton, which scans a text in a single O(n) pass regardless of how many trigger tokens exist. It also exposes `to_compiled_regex()`, which converts the trigger set to Python's C-compiled regex for native-speed search in the benchmark.

## Notes

- Validation is bounded, not exhaustive.
- Trigger extraction is conservative: if the code is unsure, it returns fewer triggers rather than unsafe ones.
- The extractor returns one ranked sound trigger set. It is designed to be compact and useful for filtering, but it does not claim a mathematically proven global optimum for every supported regex.
- Finite non-negated character classes can produce trigger sets such as `[ab] -> {'a', 'b'}`. Negated classes stay conservative.
