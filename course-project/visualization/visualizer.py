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


def visualize_pattern(pattern: str) -> str:
    node = parse_regex(pattern)
    return visualize_node(node)


def visualize_node(node: RegexNode) -> str:
    lines = [node_label(node)]
    children = list(node_children(node))

    for index, child in enumerate(children):
        is_last = index == len(children) - 1
        lines.extend(render_child(child, prefix="", is_last=is_last))

    return "\n".join(lines)


def render_child(node: RegexNode, prefix: str, is_last: bool) -> list[str]:
    branch = "└── " if is_last else "├── "
    lines = [f"{prefix}{branch}{node_label(node)}"]
    child_prefix = f"{prefix}{'    ' if is_last else '│   '}"
    children = list(node_children(node))

    for index, child in enumerate(children):
        child_is_last = index == len(children) - 1
        lines.extend(render_child(child, child_prefix, child_is_last))

    return lines


def node_label(node: RegexNode) -> str:
    if isinstance(node, EmptyNode):
        return "Empty"

    if isinstance(node, LiteralNode):
        return f"Literal({node.value!r})"

    if isinstance(node, CharacterClassNode):
        prefix = "^" if node.negated else ""
        return f"Class([{prefix}{format_class_characters(node.characters)}])"

    if isinstance(node, ConcatNode):
        return "Concat"

    if isinstance(node, AlternateNode):
        return "Alternate"

    if isinstance(node, GroupNode):
        return "Group"

    if isinstance(node, RepeatNode):
        return f"Repeat({repeat_label(node.min_count, node.max_count)})"

    raise TypeError(f"unsupported node type: {type(node).__name__}")


def node_children(node: RegexNode) -> tuple[RegexNode, ...]:
    if isinstance(node, ConcatNode):
        return node.parts

    if isinstance(node, AlternateNode):
        return node.options

    if isinstance(node, GroupNode):
        return (node.node,)

    if isinstance(node, RepeatNode):
        return (node.node,)

    return ()


def repeat_label(min_count: int, max_count: int | None) -> str:
    if min_count == 0 and max_count is None:
        return "*"
    if min_count == 1 and max_count is None:
        return "+"
    if min_count == 0 and max_count == 1:
        return "?"
    if max_count is None:
        return f"{{{min_count},}}"
    if min_count == max_count:
        return f"{{{min_count}}}"
    return f"{{{min_count},{max_count}}}"


def format_class_characters(characters: tuple[str, ...], limit: int = 8) -> str:
    pieces = [escape_character(char) for char in characters[:limit]]
    if len(characters) > limit:
        pieces.append("...")
    return "".join(pieces)


def escape_character(char: str) -> str:
    if char == "\\":
        return r"\\"
    if char == "]":
        return r"\]"
    if char == "[":
        return r"\["
    if char == "-":
        return r"\-"
    if char == "^":
        return r"\^"
    if char == "\n":
        return r"\n"
    if char == "\t":
        return r"\t"
    if char == "\r":
        return r"\r"
    return char
