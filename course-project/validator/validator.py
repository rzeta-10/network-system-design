from dataclasses import dataclass
import re

from extractor.aho_corasick import AhoCorasick
from extractor.trigger_extractor import extract_triggers
from parser.regex_parser import (
    AlternateNode,
    CharacterClassNode,
    ConcatNode,
    EmptyNode,
    GroupNode,
    LiteralNode,
    RegexNode,
    RepeatNode,
    parse_regex,
)


NEGATED_CLASS_CHOICES = "abcXYZ012_- "
FALLBACK_NEGATED_RANGE = tuple(chr(code) for code in range(32, 127))


@dataclass
class ValidationResult:
    pattern: str
    triggers: list[str]
    generated_samples: list[str]
    checked_samples: list[str]
    rejected_samples: list[str]
    counterexamples: list[str]

    @property
    def is_valid(self) -> bool:
        return not self.rejected_samples and not self.counterexamples


def validate_triggers(
    pattern: str,
    max_repeat: int = 2,
    sample_limit: int = 200,
    class_limit: int = 5,
) -> ValidationResult:
    node = parse_regex(pattern)
    triggers = extract_triggers(pattern)
    generated_samples = generate_samples_from_node(
        node,
        max_repeat=max_repeat,
        sample_limit=sample_limit,
        class_limit=class_limit,
    )

    compiled = re.compile(f"^(?:{pattern})$")
    trigger_matcher = AhoCorasick.from_triggers(triggers) if triggers else None
    checked_samples: list[str] = []
    rejected_samples: list[str] = []
    counterexamples: list[str] = []

    for sample in generated_samples:
        if compiled.fullmatch(sample) is None:
            rejected_samples.append(sample)
            continue

        checked_samples.append(sample)
        if trigger_matcher is not None and not trigger_matcher.search(sample):
            counterexamples.append(sample)

    return ValidationResult(
        pattern=pattern,
        triggers=triggers,
        generated_samples=generated_samples,
        checked_samples=checked_samples,
        rejected_samples=rejected_samples,
        counterexamples=counterexamples,
    )


def generate_samples(
    pattern: str,
    max_repeat: int = 2,
    sample_limit: int = 200,
    class_limit: int = 5,
) -> list[str]:
    node = parse_regex(pattern)
    return generate_samples_from_node(
        node,
        max_repeat=max_repeat,
        sample_limit=sample_limit,
        class_limit=class_limit,
    )


def generate_samples_from_node(
    node: RegexNode,
    max_repeat: int = 2,
    sample_limit: int = 200,
    class_limit: int = 5,
) -> list[str]:
    if isinstance(node, EmptyNode):
        return [""]

    if isinstance(node, LiteralNode):
        return [node.value]

    if isinstance(node, CharacterClassNode):
        if node.negated:
            return sample_negated_characters(node.characters, class_limit)
        return unique_limited(list(node.characters), class_limit)

    if isinstance(node, GroupNode):
        return generate_samples_from_node(
            node.node,
            max_repeat=max_repeat,
            sample_limit=sample_limit,
            class_limit=class_limit,
        )

    if isinstance(node, AlternateNode):
        samples: list[str] = []
        for option in node.options:
            option_samples = generate_samples_from_node(
                option,
                max_repeat=max_repeat,
                sample_limit=sample_limit,
                class_limit=class_limit,
            )
            samples.extend(option_samples)
        return unique_limited(samples, sample_limit)

    if isinstance(node, ConcatNode):
        samples = [""]
        for part in node.parts:
            part_samples = generate_samples_from_node(
                part,
                max_repeat=max_repeat,
                sample_limit=sample_limit,
                class_limit=class_limit,
            )
            samples = combine_samples(samples, part_samples, sample_limit)
        return samples

    if isinstance(node, RepeatNode):
        child_samples = generate_samples_from_node(
            node.node,
            max_repeat=max_repeat,
            sample_limit=sample_limit,
            class_limit=class_limit,
        )
        upper = node.max_count if node.max_count is not None else node.min_count + max_repeat
        samples: list[str] = []

        for count in range(node.min_count, upper + 1):
            repeated = [""]
            for _ in range(count):
                repeated = combine_samples(repeated, child_samples, sample_limit)
            samples.extend(repeated)

        return unique_limited(samples, sample_limit)

    raise TypeError(f"unsupported node type: {type(node).__name__}")


def combine_samples(left: list[str], right: list[str], limit: int) -> list[str]:
    combined: list[str] = []
    seen: set[str] = set()

    for left_value in left:
        for right_value in right:
            value = left_value + right_value
            if value in seen:
                continue
            seen.add(value)
            combined.append(value)
            if len(combined) >= limit:
                return combined

    return combined


def unique_limited(values: list[str], limit: int) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()

    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique.append(value)
        if len(unique) >= limit:
            break

    return unique


def sample_negated_characters(excluded_characters: tuple[str, ...], limit: int) -> list[str]:
    excluded = set(excluded_characters)
    choices: list[str] = []

    for char in NEGATED_CLASS_CHOICES:
        if char in excluded:
            continue
        choices.append(char)

    for char in FALLBACK_NEGATED_RANGE:
        if len(choices) >= limit:
            break
        if char in excluded or char in choices:
            continue
        choices.append(char)

    if not choices:
        codepoint = 128
        while len(choices) < max(1, limit):
            char = chr(codepoint)
            if char not in excluded:
                choices.append(char)
            codepoint += 1

    return unique_limited(choices, limit)


def contains_trigger(text: str, triggers: list[str]) -> bool:
    return any(trigger in text for trigger in triggers)
