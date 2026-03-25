from dataclasses import dataclass


SPECIAL_CLASS_MAP = {
    "d": "0123456789",
    "s": " \t\n\r",
    "w": "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_",
}

ESCAPED_LITERAL_MAP = {
    "n": "\n",
    "t": "\t",
    "r": "\r",
}

ESCAPABLE_LITERALS = set(r"\[]()|*+?.{}^$-")

UNSUPPORTED_TOKENS = {
    ".": "dot wildcard is not supported",
    "{": "brace repetition is not supported",
    "}": "brace repetition is not supported",
    "^": "anchors are not supported outside character classes",
    "$": "anchors are not supported",
}


class ParserError(ValueError):
    pass


@dataclass(frozen=True)
class RegexNode:
    pass


@dataclass(frozen=True)
class EmptyNode(RegexNode):
    pass


@dataclass(frozen=True)
class LiteralNode(RegexNode):
    value: str


@dataclass(frozen=True)
class CharacterClassNode(RegexNode):
    characters: tuple[str, ...]
    negated: bool = False


@dataclass(frozen=True)
class ConcatNode(RegexNode):
    parts: tuple[RegexNode, ...]


@dataclass(frozen=True)
class AlternateNode(RegexNode):
    options: tuple[RegexNode, ...]


@dataclass(frozen=True)
class RepeatNode(RegexNode):
    node: RegexNode
    min_count: int
    max_count: int | None


@dataclass(frozen=True)
class GroupNode(RegexNode):
    node: RegexNode


@dataclass
class RegexParser:
    pattern: str
    index: int = 0

    def parse(self) -> RegexNode:
        node = self._parse_alternation()
        if not self._at_end():
            raise self._error(f"unexpected character {self._peek()!r}")
        return node

    def _parse_alternation(self) -> RegexNode:
        options = [self._parse_concatenation()]
        while self._peek() == "|":
            self._advance()
            options.append(self._parse_concatenation())

        if len(options) == 1:
            return options[0]
        return AlternateNode(tuple(options))

    def _parse_concatenation(self) -> RegexNode:
        parts: list[RegexNode] = []

        while not self._at_end() and self._peek() not in "|)":
            parts.append(self._parse_postfix())

        # Merge runs of adjacent LiteralNodes into a single longer literal so
        # the extractor works with whole-word units rather than individual chars.
        coalesced: list[RegexNode] = []
        for part in parts:
            if coalesced and isinstance(coalesced[-1], LiteralNode) and isinstance(part, LiteralNode):
                coalesced[-1] = LiteralNode(coalesced[-1].value + part.value)
            else:
                coalesced.append(part)

        if not coalesced:
            return EmptyNode()
        if len(coalesced) == 1:
            return coalesced[0]
        return ConcatNode(tuple(coalesced))

    def _parse_postfix(self) -> RegexNode:
        node = self._parse_atom()
        token = self._peek()

        if token not in {"*", "+", "?"}:
            return node

        self._advance()
        if token == "*":
            node = RepeatNode(node=node, min_count=0, max_count=None)
        elif token == "+":
            node = RepeatNode(node=node, min_count=1, max_count=None)
        else:
            node = RepeatNode(node=node, min_count=0, max_count=1)

        if self._peek() in {"*", "+", "?"}:
            raise self._error("stacked repetition operators are not supported")

        return node

    def _parse_atom(self) -> RegexNode:
        token = self._peek()
        if token is None:
            raise self._error("expected an atom")

        if token == "(":
            return self._parse_group()
        if token == "[":
            return self._parse_character_class()
        if token == "\\":
            return self._parse_escape()
        if token in UNSUPPORTED_TOKENS:
            raise self._error(UNSUPPORTED_TOKENS[token])
        if token in {"|", ")", "*", "+", "?"}:
            raise self._error(f"unexpected character {token!r}")

        self._advance()
        return LiteralNode(token)

    def _parse_group(self) -> RegexNode:
        self._expect("(")
        node = self._parse_alternation()
        if self._peek() != ")":
            raise self._error("missing closing ')'")
        self._advance()
        return GroupNode(node)

    def _parse_character_class(self) -> RegexNode:
        self._expect("[")
        negated = False
        if self._peek() == "^":
            negated = True
            self._advance()

        characters: list[str] = []
        if self._peek() == "]":
            raise self._error("empty character classes are not allowed")

        while True:
            token = self._peek()
            if token is None:
                raise self._error("missing closing ']'")
            if token == "]":
                self._advance()
                break

            start_chars = self._read_class_unit()
            if self._peek() == "-" and self._peek_next() not in {None, "]"} and len(start_chars) == 1:
                self._advance()
                end_chars = self._read_class_unit()
                if len(end_chars) != 1:
                    raise self._error("range endpoints must be single characters")
                characters.extend(self._expand_range(start_chars[0], end_chars[0]))
                continue

            characters.extend(start_chars)

        ordered = tuple(dict.fromkeys(characters))
        return CharacterClassNode(characters=ordered, negated=negated)

    def _parse_escape(self) -> RegexNode:
        self._expect("\\")
        token = self._peek()
        if token is None:
            raise self._error("dangling escape")

        self._advance()
        if token in SPECIAL_CLASS_MAP:
            chars = tuple(SPECIAL_CLASS_MAP[token])
            return CharacterClassNode(characters=chars)
        if token in ESCAPED_LITERAL_MAP:
            return LiteralNode(ESCAPED_LITERAL_MAP[token])
        if token in ESCAPABLE_LITERALS:
            return LiteralNode(token)
        raise self._error(f"unsupported escape sequence '\\{token}'")

    def _read_class_unit(self) -> list[str]:
        token = self._peek()
        if token is None:
            raise self._error("unexpected end of character class")

        if token == "\\":
            self._advance()
            escaped = self._peek()
            if escaped is None:
                raise self._error("dangling escape in character class")
            self._advance()
            if escaped in SPECIAL_CLASS_MAP:
                return list(SPECIAL_CLASS_MAP[escaped])
            if escaped in ESCAPED_LITERAL_MAP:
                return [ESCAPED_LITERAL_MAP[escaped]]
            if escaped in ESCAPABLE_LITERALS:
                return [escaped]
            raise self._error(f"unsupported escape sequence '\\{escaped}' in character class")

        self._advance()
        return [token]

    def _expand_range(self, start: str, end: str) -> list[str]:
        if ord(start) > ord(end):
            raise self._error(f"invalid range {start}-{end}")
        return [chr(code) for code in range(ord(start), ord(end) + 1)]

    def _expect(self, char: str) -> None:
        if self._peek() != char:
            raise self._error(f"expected {char!r}")
        self._advance()

    def _peek(self) -> str | None:
        if self.index >= len(self.pattern):
            return None
        return self.pattern[self.index]

    def _peek_next(self) -> str | None:
        next_index = self.index + 1
        if next_index >= len(self.pattern):
            return None
        return self.pattern[next_index]

    def _advance(self) -> str | None:
        token = self._peek()
        if token is not None:
            self.index += 1
        return token

    def _at_end(self) -> bool:
        return self.index >= len(self.pattern)

    def _error(self, message: str) -> ParserError:
        pointer = " " * self.index + "^"
        full_message = f"{message} at index {self.index}\n{self.pattern}\n{pointer}"
        return ParserError(full_message)


def parse_regex(pattern: str) -> RegexNode:
    parser = RegexParser(pattern=pattern)
    return parser.parse()
