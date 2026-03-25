import unittest

from benchmark.performance import benchmark_pattern
from extractor.aho_corasick import AhoCorasick
from extractor.trigger_extractor import extract_triggers
from parser.regex_parser import (
    AlternateNode,
    CharacterClassNode,
    ConcatNode,
    LiteralNode,
    ParserError,
    RepeatNode,
    parse_regex,
)
from validator.validator import validate_triggers
from visualization.visualizer import visualize_pattern


class ParserTests(unittest.TestCase):
    def test_parser_builds_concat_tree(self) -> None:
        # After literal coalescing, a class + literal produces a real ConcatNode
        node = parse_regex("[ab]c")
        self.assertIsInstance(node, ConcatNode)
        self.assertEqual(node.parts, (CharacterClassNode(("a", "b")), LiteralNode("c")))

    def test_parser_coalesces_adjacent_literals(self) -> None:
        node = parse_regex("abc")
        self.assertIsInstance(node, LiteralNode)
        self.assertEqual(node.value, "abc")

    def test_parser_handles_alternation_and_grouping(self) -> None:
        node = parse_regex("(ab|ac)+")
        self.assertIsInstance(node, RepeatNode)
        self.assertEqual(node.min_count, 1)
        self.assertIsNone(node.max_count)
        self.assertIsInstance(node.node.node, AlternateNode)

    def test_parser_handles_character_class(self) -> None:
        node = parse_regex("[a-c]x")
        self.assertIsInstance(node, ConcatNode)
        self.assertEqual(node.parts[0], CharacterClassNode(("a", "b", "c")))

    def test_parser_reports_errors(self) -> None:
        with self.assertRaises(ParserError):
            parse_regex("(ab")

    def test_parser_rejects_unsupported_tokens(self) -> None:
        for pattern in ["a.b", "a{2}", "^ab", "ab$"]:
            with self.subTest(pattern=pattern):
                with self.assertRaises(ParserError):
                    parse_regex(pattern)

    def test_parser_rejects_unsupported_escape_sequences(self) -> None:
        for pattern in [r"\bword", r"ab\A", r"[\B]x"]:
            with self.subTest(pattern=pattern):
                with self.assertRaises(ParserError):
                    parse_regex(pattern)


class TriggerExtractionTests(unittest.TestCase):
    def test_extracts_literal_trigger(self) -> None:
        self.assertEqual(extract_triggers("ab"), ["ab"])

    def test_extracts_shared_alternation_trigger(self) -> None:
        self.assertEqual(extract_triggers("abc|abd"), ["ab"])

    def test_extracts_finite_character_class_trigger_set(self) -> None:
        self.assertEqual(set(extract_triggers("[ab]")), {"a", "b"})

    def test_extracts_disjunctive_trigger_set_for_alternation(self) -> None:
        self.assertEqual(set(extract_triggers("ab|cd")), {"ab", "cd"})

    def test_handles_optional_and_repetition(self) -> None:
        self.assertEqual(extract_triggers("a?b"), ["b"])
        self.assertEqual(extract_triggers("(ab)+"), ["ab"])

    def test_prefers_small_singleton_trigger_when_available(self) -> None:
        self.assertEqual(extract_triggers("pre(ab|ac)post"), ["post"])

    def test_extracts_trigger_after_character_class(self) -> None:
        # char class has no exact value so suffix chain resets; "cd" must come from fixed literal
        self.assertEqual(extract_triggers("[ab]cd"), ["cd"])

    def test_extracts_all_branches_for_deep_alternation(self) -> None:
        self.assertEqual(set(extract_triggers("a|b|c")), {"a", "b", "c"})

    def test_extracts_shared_literal_not_per_char_for_coalesced_pattern(self) -> None:
        # With literal coalescing "abc" is one node; trigger must be "abc" not just "a"
        self.assertEqual(extract_triggers("abc|abd"), ["ab"])

    def test_extracts_trigger_through_repeated_alternation(self) -> None:
        # Every match of (a|b)+c ends in "c"
        self.assertEqual(extract_triggers("(a|b)+c"), ["c"])

    def test_returns_empty_for_nullable_pattern(self) -> None:
        self.assertEqual(extract_triggers("(ab)?"), [])


class AhoCorasickTests(unittest.TestCase):
    def test_finds_single_pattern(self) -> None:
        ac = AhoCorasick.from_triggers(["ab"])
        self.assertTrue(ac.search("xabx"))
        self.assertFalse(ac.search("xacx"))

    def test_finds_any_of_multiple_patterns(self) -> None:
        ac = AhoCorasick.from_triggers(["ab", "cd"])
        self.assertTrue(ac.search("xxcdxx"))
        self.assertTrue(ac.search("xxabxx"))
        self.assertFalse(ac.search("xxefxx"))

    def test_empty_text_returns_false(self) -> None:
        ac = AhoCorasick.from_triggers(["ab"])
        self.assertFalse(ac.search(""))

    def test_pattern_at_start_and_end(self) -> None:
        ac = AhoCorasick.from_triggers(["ab"])
        self.assertTrue(ac.search("abxyz"))
        self.assertTrue(ac.search("xyzab"))

    def test_overlapping_patterns_both_found(self) -> None:
        ac = AhoCorasick.from_triggers(["ab", "abc"])
        self.assertTrue(ac.search("xabcx"))
        self.assertTrue(ac.search("xabx"))

    def test_no_false_positive_on_prefix_only(self) -> None:
        ac = AhoCorasick.from_triggers(["abcd"])
        self.assertFalse(ac.search("abc"))
        self.assertTrue(ac.search("abcd"))

    def test_to_compiled_regex_matches_same_texts_as_search(self) -> None:
        triggers = ["ab", "cd", "ef"]
        ac = AhoCorasick.from_triggers(triggers)
        compiled = ac.to_compiled_regex()
        for text in ["xabx", "xcdx", "xefx", "xghx", "", "abcdef"]:
            self.assertEqual(bool(compiled.search(text)), ac.search(text), msg=f"mismatch on {text!r}")

    def test_to_compiled_regex_empty_triggers_never_matches(self) -> None:
        ac = AhoCorasick.from_triggers([])
        ac.build()
        self.assertIsNone(ac.to_compiled_regex().search("anything"))


class ExtractionEdgeCaseTests(unittest.TestCase):
    def test_extracts_trigger_from_escape_class_concat(self) -> None:
        # \d is a char class; the fixed literal "x" follows it
        self.assertEqual(extract_triggers(r"\d+x"), ["x"])

    def test_extracts_trigger_after_class_with_literal_suffix(self) -> None:
        # char class breaks suffix chain; "post" must come from the fixed literal
        self.assertEqual(extract_triggers("pre[ab]post"), ["post"])

    def test_extracts_trigger_for_complex_nested_pattern(self) -> None:
        # every match of ((ab|cd)+ef)gh ends in "efgh"; the extractor finds
        # this 4-char cross-boundary token which is more specific than "gh"
        result = extract_triggers("((ab|cd)+ef)gh")
        self.assertEqual(result, ["efgh"])

    def test_extract_and_validate_agree_for_char_class_pattern(self) -> None:
        result = validate_triggers("[a-z]+end")
        self.assertTrue(result.is_valid)
        self.assertEqual(result.triggers, ["end"])


class ValidationTests(unittest.TestCase):
    def test_validation_passes_for_supported_patterns(self) -> None:
        for pattern in ["ab", "abc|abd", "(ab|cb)d", "a+b", "[^ab]x", "(ab)?c"]:
            with self.subTest(pattern=pattern):
                result = validate_triggers(pattern)
                self.assertTrue(result.is_valid)
                self.assertEqual(result.counterexamples, [])

    def test_validation_allows_patterns_with_no_triggers(self) -> None:
        result = validate_triggers("a?")
        self.assertTrue(result.is_valid)
        self.assertEqual(result.triggers, [])

    def test_validation_handles_negated_class_with_large_exclusion_set(self) -> None:
        pattern = r"[^abcXYZ012_\- !]x"
        result = validate_triggers(pattern)
        self.assertTrue(result.is_valid)
        self.assertNotEqual(result.checked_samples, [])


class VisualizerTests(unittest.TestCase):
    def test_visualizer_prints_tree(self) -> None:
        tree = visualize_pattern("(ab)+c?")
        self.assertIn("Concat", tree)
        self.assertIn("Repeat(+)", tree)
        self.assertIn("Literal('c')", tree)

    def test_visualizer_escapes_character_class_labels(self) -> None:
        tree = visualize_pattern(r"[\]]x")
        self.assertIn(r"Class([\]])", tree)

        tree = visualize_pattern(r"[\\-]x")
        self.assertIn(r"Class([\\\-])", tree)


class BenchmarkTests(unittest.TestCase):
    def test_benchmark_keeps_match_counts(self) -> None:
        result = benchmark_pattern("pre(ab|ac)post", dataset_size=100, rounds=3)
        self.assertEqual(result.match_count, result.positive_count)
        self.assertEqual(result.dataset_size, 100)
        self.assertGreaterEqual(result.skipped_count, 0)

    def test_benchmark_handles_nullable_patterns_without_negatives(self) -> None:
        result = benchmark_pattern("a*", dataset_size=20, rounds=1)
        self.assertEqual(result.dataset_size, 20)
        self.assertEqual(result.positive_count, 20)
        self.assertEqual(result.negative_count, 0)

    def test_benchmark_rejects_invalid_rounds(self) -> None:
        with self.assertRaises(ValueError):
            benchmark_pattern("ab", dataset_size=20, rounds=0)


if __name__ == "__main__":
    unittest.main()
