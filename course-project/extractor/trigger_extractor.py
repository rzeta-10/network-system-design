"""Trigger extraction for guaranteed regex activation.

Given a regular expression r, this module extracts a trigger set

    T = {t1, t2, ..., tk}

such that every string s accepted by r contains at least one token from T:

    ∀ s ∈ L(r),  ∃ ti ∈ T  such that  ti ⊆ s   (ti is a substring of s)

This guarantee means that any input stream segment which does NOT contain
any token from T can be safely skipped without running the full regex engine.

Soundness invariant (maintained by structural induction on the AST):
  For every NodeAnalysis returned by analyze_node(node):
  1. Every candidate set C ∈ candidates is a sound trigger set:
         ∀ s ∈ L(node), ∃ t ∈ C: t ⊆ s
  2. Every token in summary.tokens appears in every string in L(node).
  3. Every string in summary.prefixes is a prefix of every string in L(node).
  4. Every string in summary.suffixes is a suffix of every string in L(node).
  5. summary.nullable is True iff ε ∈ L(node).
  6. If summary.exact = v then L(node) = {v}.

Time complexity of extraction:
  O(|AST| × MAX_CANDIDATE_SETS × k)  where k = max candidate set size.

Space complexity: O(|AST| × MAX_CANDIDATE_SETS × k).
"""
from dataclasses import dataclass

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


MAX_CANDIDATE_SETS = 128


@dataclass
class TriggerSummary:
    nullable: bool
    exact: str | None
    prefixes: set[str]
    suffixes: set[str]
    tokens: set[str]


@dataclass
class NodeAnalysis:
    summary: TriggerSummary
    candidates: list[frozenset[str]]


def extract_triggers(pattern: str) -> list[str]:
    """Parse pattern and return a sound trigger set (longest tokens first).

    Returns [] when the pattern can match the empty string or when no
    structural guarantee can be derived (e.g. a*).
    """
    node = parse_regex(pattern)
    return extract_triggers_from_node(node)


def extract_triggers_from_node(node: RegexNode) -> list[str]:
    """Return the best ranked sound trigger set for the given AST node.

    Candidates are ranked by (set size, -total token length); the smallest
    set with the longest total token length is preferred because longer tokens
    produce fewer false positives in a streaming filter.
    """
    analysis = analyze_node(node)
    if not analysis.candidates:
        return []

    best = analysis.candidates[0]
    return sorted(best, key=lambda token: (-len(token), token))


def analyze_node(node: RegexNode) -> NodeAnalysis:
    if isinstance(node, EmptyNode):
        return NodeAnalysis(summary=fixed_summary(""), candidates=[])

    if isinstance(node, LiteralNode):
        summary = fixed_summary(node.value)
        return NodeAnalysis(summary=summary, candidates=prune_candidate_sets(singleton_candidates(summary.tokens)))

    if isinstance(node, CharacterClassNode):
        if not node.negated and len(node.characters) == 1:
            summary = fixed_summary(node.characters[0])
            return NodeAnalysis(summary=summary, candidates=prune_candidate_sets(singleton_candidates(summary.tokens)))

        summary = TriggerSummary(
            nullable=False,
            exact=None,
            prefixes=set(),
            suffixes=set(),
            tokens=set(),
        )
        candidates: list[frozenset[str]] = []
        if not node.negated:
            candidates.append(normalize_candidate(node.characters))
        return NodeAnalysis(summary=summary, candidates=prune_candidate_sets(candidates))

    if isinstance(node, GroupNode):
        return analyze_node(node.node)

    if isinstance(node, ConcatNode):
        part_analyses = [analyze_node(part) for part in node.parts]
        summary = fixed_summary("")
        for part in part_analyses:
            summary = combine_concatenation(summary, part.summary)

        candidates = singleton_candidates(summary.tokens)
        for part in part_analyses:
            if not part.summary.nullable:
                candidates.extend(part.candidates)

        return NodeAnalysis(summary=summary, candidates=prune_candidate_sets(candidates))

    if isinstance(node, AlternateNode):
        option_analyses = [analyze_node(option) for option in node.options]
        summary = summarize_alternation(option_analyses)
        candidates = singleton_candidates(summary.tokens)

        if option_analyses and all(option.candidates for option in option_analyses):
            merged = option_analyses[0].candidates
            for option in option_analyses[1:]:
                combinations: list[frozenset[str]] = []
                for left in merged:
                    for right in option.candidates:
                        combinations.append(normalize_candidate(left | right))
                merged = prune_candidate_sets(combinations)
            candidates.extend(merged)

        return NodeAnalysis(summary=summary, candidates=prune_candidate_sets(candidates))

    if isinstance(node, RepeatNode):
        child = analyze_node(node.node)
        summary = summarize_repeat(node, child.summary)
        candidates = singleton_candidates(summary.tokens)

        if node.min_count > 0:
            candidates.extend(child.candidates)

        return NodeAnalysis(summary=summary, candidates=prune_candidate_sets(candidates))

    raise TypeError(f"unsupported node type: {type(node).__name__}")


def summarize_node(node: RegexNode) -> TriggerSummary:
    return analyze_node(node).summary


def summarize_alternation(option_analyses: list[NodeAnalysis]) -> TriggerSummary:
    exact_values = {option.summary.exact for option in option_analyses}
    if len(exact_values) == 1:
        exact = next(iter(exact_values))
        if exact is not None:
            return fixed_summary(exact)

    prefixes = intersect_sets(option.summary.prefixes for option in option_analyses)
    suffixes = intersect_sets(option.summary.suffixes for option in option_analyses)
    tokens = intersect_sets(option.summary.tokens for option in option_analyses)
    return TriggerSummary(
        nullable=any(option.summary.nullable for option in option_analyses),
        exact=None,
        prefixes=prefixes,
        suffixes=suffixes,
        tokens=tokens,
    )


def summarize_repeat(node: RepeatNode, child: TriggerSummary) -> TriggerSummary:
    if node.min_count == 0:
        return fixed_summary("") if child.exact == "" else TriggerSummary(
            nullable=True,
            exact=None,
            prefixes=set(),
            suffixes=set(),
            tokens=set(),
        )

    if node.max_count == node.min_count and child.exact is not None:
        return fixed_summary(child.exact * node.min_count)

    if child.exact == "":
        return fixed_summary("")

    return TriggerSummary(
        nullable=child.nullable,
        exact=None,
        prefixes=set(child.prefixes),
        suffixes=set(child.suffixes),
        tokens=set(child.tokens),
    )


def combine_concatenation(left: TriggerSummary, right: TriggerSummary) -> TriggerSummary:
    if left.exact is not None and right.exact is not None:
        return fixed_summary(left.exact + right.exact)

    prefixes = set(left.prefixes)
    suffixes = set(right.suffixes)
    tokens = set(left.tokens) | set(right.tokens)

    for left_suffix in left.suffixes:
        for right_prefix in right.prefixes:
            tokens.add(left_suffix + right_prefix)

    if left.exact == "":
        prefixes |= right.prefixes
    elif left.exact is not None:
        prefixes |= {left.exact + prefix for prefix in right.prefixes}

    if right.exact == "":
        suffixes |= left.suffixes
    elif right.exact is not None:
        suffixes |= {suffix + right.exact for suffix in left.suffixes}

    return TriggerSummary(
        nullable=left.nullable and right.nullable,
        exact=None,
        prefixes=prefixes,
        suffixes=suffixes,
        tokens=tokens,
    )


def fixed_summary(text: str) -> TriggerSummary:
    return TriggerSummary(
        nullable=(text == ""),
        exact=text,
        prefixes=all_prefixes(text),
        suffixes=all_suffixes(text),
        tokens=all_substrings(text),
    )


def all_prefixes(text: str) -> set[str]:
    return {text[:index] for index in range(1, len(text) + 1)}


def all_suffixes(text: str) -> set[str]:
    return {text[index:] for index in range(len(text))}


def all_substrings(text: str) -> set[str]:
    tokens: set[str] = set()
    for start in range(len(text)):
        for end in range(start + 1, len(text) + 1):
            tokens.add(text[start:end])
    return tokens


def singleton_candidates(tokens: set[str]) -> list[frozenset[str]]:
    return [frozenset({token}) for token in tokens if token]


def normalize_candidate(tokens) -> frozenset[str]:
    ordered = sorted({token for token in tokens if token}, key=lambda token: (len(token), token))
    chosen: list[str] = []

    for token in ordered:
        if any(existing in token for existing in chosen):
            continue
        chosen.append(token)

    return frozenset(chosen)


def prune_candidate_sets(candidates: list[frozenset[str]]) -> list[frozenset[str]]:
    normalized = {normalize_candidate(candidate) for candidate in candidates}
    normalized.discard(frozenset())
    return sorted(normalized, key=candidate_sort_key)[:MAX_CANDIDATE_SETS]


def candidate_sort_key(candidate: frozenset[str]) -> tuple[int, int, tuple[str, ...]]:
    ordered = tuple(sorted(candidate))
    total_length = sum(len(token) for token in candidate)
    return (len(candidate), -total_length, ordered)


def intersect_sets(groups) -> set[str]:
    groups = list(groups)
    if not groups:
        return set()

    shared = set(groups[0])
    for group in groups[1:]:
        shared &= group
    return shared
