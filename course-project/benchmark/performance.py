from dataclasses import dataclass
import re
import time

from extractor.aho_corasick import AhoCorasick
from extractor.trigger_extractor import extract_triggers
from validator.validator import generate_samples


SEARCH_ALPHABET = "abcxyzABCXYZ012_-! "


@dataclass
class BenchmarkResult:
    pattern: str
    triggers: list[str]
    dataset_size: int
    positive_count: int
    negative_count: int
    match_count: int
    skipped_count: int
    plain_time: float
    filtered_time: float

    @property
    def speedup(self) -> float:
        if self.filtered_time == 0:
            return 0.0
        return self.plain_time / self.filtered_time


def benchmark_pattern(
    pattern: str,
    dataset_size: int = 5000,
    positive_ratio: float = 0.4,
    rounds: int = 5,
    max_repeat: int = 3,
) -> BenchmarkResult:
    validate_benchmark_inputs(
        dataset_size=dataset_size,
        positive_ratio=positive_ratio,
        rounds=rounds,
        max_repeat=max_repeat,
    )
    compiled = re.compile(pattern)
    triggers = extract_triggers(pattern)
    # Build Aho-Corasick automaton from triggers.  For the benchmark timing
    # loop, convert to a compiled regex so the trigger scan runs at C speed
    # (equivalent to the AC automaton compiled to native code in production).
    trigger_ac = AhoCorasick.from_triggers(triggers) if triggers else None
    trigger_filter = trigger_ac.to_compiled_regex() if trigger_ac is not None else None
    dataset = build_benchmark_inputs(
        pattern,
        dataset_size=dataset_size,
        positive_ratio=positive_ratio,
        max_repeat=max_repeat,
    )

    positive_count = sum(1 for text in dataset if compiled.search(text))
    negative_count = len(dataset) - positive_count

    # Warmup: one pass of each to warm CPU caches before timing
    run_plain_matching(compiled, dataset)
    run_filtered_matching(compiled, dataset, trigger_filter)

    # Interleave plain and filtered rounds for a fair comparison: both see
    # the same cache state each round instead of one benefiting from the
    # other's warmup.
    plain_time = 0.0
    filtered_time = 0.0
    plain_matches = 0
    filtered_matches = 0
    skipped_count = 0

    for _ in range(rounds):
        t0 = time.perf_counter()
        plain_matches = run_plain_matching(compiled, dataset)
        plain_time += time.perf_counter() - t0

        t0 = time.perf_counter()
        filtered_matches, skipped_count = run_filtered_matching(compiled, dataset, trigger_filter)
        filtered_time += time.perf_counter() - t0

    if plain_matches != filtered_matches:
        raise ValueError("trigger-filtered matching changed the final match count")

    return BenchmarkResult(
        pattern=pattern,
        triggers=triggers,
        dataset_size=len(dataset),
        positive_count=positive_count,
        negative_count=negative_count,
        match_count=plain_matches,
        skipped_count=skipped_count,
        plain_time=plain_time,
        filtered_time=filtered_time,
    )


def run_benchmark_suite(
    pattern: str,
    sizes: tuple[int, ...] = (1000, 5000, 10000),
    positive_ratio: float = 0.4,
    rounds: int = 5,
    max_repeat: int = 3,
) -> list[BenchmarkResult]:
    results: list[BenchmarkResult] = []
    for size in sizes:
        results.append(
            benchmark_pattern(
                pattern,
                dataset_size=size,
                positive_ratio=positive_ratio,
                rounds=rounds,
                max_repeat=max_repeat,
            )
        )
    return results


def build_benchmark_inputs(
    pattern: str,
    dataset_size: int = 5000,
    positive_ratio: float = 0.4,
    max_repeat: int = 3,
) -> list[str]:
    compiled = re.compile(pattern)
    target_positive = choose_target_positive_count(dataset_size, positive_ratio)
    target_negative = dataset_size - target_positive

    positive_pool = generate_samples(
        pattern,
        max_repeat=max_repeat,
        sample_limit=max(50, target_positive),
        class_limit=8,
    )
    positive_pool = [sample for sample in positive_pool if compiled.fullmatch(sample)]
    if not positive_pool:
        raise ValueError("could not build positive samples for benchmark")

    positive_texts = build_positive_texts(positive_pool, target_positive)
    negative_pool = build_negative_pool(compiled, positive_pool, target_negative)

    available_negative_count = min(target_negative, len(negative_pool))
    positive_count = dataset_size - available_negative_count

    positives = repeat_to_length(positive_texts, positive_count)
    negatives = repeat_to_length(negative_pool, available_negative_count)
    dataset = interleave_samples(positives, negatives)
    return dataset[:dataset_size]


def build_negative_pool(compiled: re.Pattern[str], positive_pool: list[str], needed: int) -> list[str]:
    candidates: list[str] = []

    for sample in positive_pool:
        candidates.extend(mutate_sample(sample))

    for index in range(max(needed * 2, 20)):
        candidates.append(make_noise(index))
        candidates.append(f"{make_noise(index)}::{make_noise(index + 1)}")

    for length in range(0, 4):
        candidates.extend(generate_search_strings(length))

    negatives: list[str] = []
    seen: set[str] = set()

    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if compiled.search(candidate) is not None:
            continue
        negatives.append(candidate)
        if len(negatives) >= needed:
            break

    return negatives


def build_positive_texts(positive_pool: list[str], needed: int) -> list[str]:
    texts: list[str] = []
    for index in range(needed):
        sample = positive_pool[index % len(positive_pool)]
        prefix = make_noise(index)
        suffix = make_noise(index + 7)
        texts.append(f"{prefix}{sample}{suffix}")
    return texts


def mutate_sample(sample: str) -> list[str]:
    if not sample:
        return ["!", "x", "xx"]

    mutated = [
        f"!{sample}",
        f"{sample}!",
        sample + sample[0],
        sample[:-1],
        sample[1:],
        sample[::-1],
        f"_{sample}_",
    ]

    first = sample[0]
    swap = "!" if first != "!" else "x"
    mutated.append(swap + sample[1:])
    return mutated


def make_noise(index: int) -> str:
    pieces = [
        "ZZZZZZZZ",
        "______",
        "90909090",
        "xyxyxyxy",
        "CABCAB",
        "------",
        "   ",
        "!!@@!!",
    ]
    return pieces[index % len(pieces)] * (1 + index % 3)


def generate_search_strings(length: int) -> list[str]:
    if length == 0:
        return [""]

    values = [""]
    for _ in range(length):
        next_values: list[str] = []
        for value in values:
            for char in SEARCH_ALPHABET:
                next_values.append(value + char)
        values = next_values
    return values


def repeat_to_length(pool: list[str], size: int) -> list[str]:
    if size <= 0:
        return []
    if not pool:
        raise ValueError("cannot repeat values from an empty pool")

    values: list[str] = []
    index = 0
    while len(values) < size:
        values.append(pool[index % len(pool)])
        index += 1
    return values


def interleave_samples(positives: list[str], negatives: list[str]) -> list[str]:
    dataset: list[str] = []
    limit = max(len(positives), len(negatives))

    for index in range(limit):
        if index < len(positives):
            dataset.append(positives[index])
        if index < len(negatives):
            dataset.append(negatives[index])

    return dataset


def run_plain_matching(compiled: re.Pattern[str], dataset: list[str]) -> int:
    match_count = 0
    for text in dataset:
        if compiled.search(text):
            match_count += 1
    return match_count


def run_filtered_matching(
    compiled: re.Pattern[str],
    dataset: list[str],
    trigger_filter: re.Pattern[str] | None,
) -> tuple[int, int]:
    match_count = 0
    skipped_count = 0

    for text in dataset:
        if trigger_filter is not None and not trigger_filter.search(text):
            skipped_count += 1
            continue
        if compiled.search(text):
            match_count += 1

    return match_count, skipped_count


def format_benchmark_results(results: list[BenchmarkResult]) -> str:
    lines = [
        "size      positives negatives matches skipped plain(s)    filtered(s) speedup",
    ]

    for result in results:
        lines.append(
            f"{result.dataset_size:<9}"
            f"{result.positive_count:<10}"
            f"{result.negative_count:<10}"
            f"{result.match_count:<8}"
            f"{result.skipped_count:<8}"
            f"{result.plain_time:<12.6f}"
            f"{result.filtered_time:<12.6f}"
            f"{result.speedup:.2f}x"
        )

    return "\n".join(lines)


def validate_benchmark_inputs(
    dataset_size: int,
    positive_ratio: float,
    rounds: int,
    max_repeat: int,
) -> None:
    if dataset_size <= 0:
        raise ValueError("dataset_size must be positive")
    if rounds <= 0:
        raise ValueError("rounds must be positive")
    if max_repeat < 0:
        raise ValueError("max_repeat cannot be negative")
    if not 0 <= positive_ratio <= 1:
        raise ValueError("positive_ratio must be between 0 and 1")


def choose_target_positive_count(dataset_size: int, positive_ratio: float) -> int:
    target_positive = int(round(dataset_size * positive_ratio))

    if positive_ratio > 0 and target_positive == 0:
        target_positive = 1
    if positive_ratio < 1 and target_positive == dataset_size:
        target_positive = dataset_size - 1

    return max(0, min(dataset_size, target_positive))
