import argparse

from benchmark.performance import format_benchmark_results, run_benchmark_suite
from extractor.trigger_extractor import extract_triggers
from parser.regex_parser import ParserError
from utils.helpers import format_triggers, make_heading, preview_list
from validator.validator import validate_triggers
from visualization.visualizer import visualize_pattern


SUPPORTED_SYNTAX_HINT = (
    "Supported syntax: concatenation, |, (), ?, *, +, [], ranges like [a-z], "
    "negated classes like [^ab], and escapes such as \\d, \\s, \\w."
)


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be a positive integer")
    return parsed


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract guaranteed trigger tokens from a regex pattern.",
    )
    parser.add_argument(
        "pattern",
        nargs="?",
        default="pre(ab|ac)post",
        help="Regex pattern to analyze.",
    )
    parser.add_argument(
        "--benchmark",
        action="store_true",
        help="Run a small timing comparison.",
    )
    parser.add_argument(
        "--sizes",
        nargs="*",
        type=positive_int,
        default=[1000, 5000],
        help="Dataset sizes used for benchmarking.",
    )
    parser.add_argument(
        "--rounds",
        type=positive_int,
        default=10,
        help="Benchmark repetitions for each dataset size.",
    )
    return parser


def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()

    if args.sizes == []:
        parser.error("--sizes requires at least one positive integer")

    try:
        triggers = extract_triggers(args.pattern)
        validation = validate_triggers(args.pattern)
        tree = visualize_pattern(args.pattern)
    except ParserError as error:
        print(make_heading("Parse Error"))
        print(error)
        print()
        print(SUPPORTED_SYNTAX_HINT)
        raise SystemExit(1) from error

    print(make_heading("Pattern"))
    print(args.pattern)
    print()

    print(make_heading("Triggers"))
    print(format_triggers(triggers))
    print()

    print(make_heading("Validation"))
    print(f"Valid on generated samples: {validation.is_valid}")
    print(f"Checked samples: {len(validation.checked_samples)}")
    print(f"Sample preview: {preview_list(validation.checked_samples)}")
    if validation.counterexamples:
        print(f"Counterexamples: {preview_list(validation.counterexamples)}")
    print()

    print(make_heading("Regex Tree"))
    print(tree)

    if args.benchmark:
        print()
        print(make_heading("Benchmark"))
        try:
            results = run_benchmark_suite(
                args.pattern,
                sizes=tuple(args.sizes),
                rounds=args.rounds,
            )
        except ValueError as error:
            print(make_heading("Benchmark Error"))
            print(error)
            raise SystemExit(1) from error
        print(format_benchmark_results(results))


if __name__ == "__main__":
    main()
