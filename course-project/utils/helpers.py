def make_heading(title: str) -> str:
    underline = "-" * len(title)
    return f"{title}\n{underline}"


def format_triggers(triggers: list[str]) -> str:
    if not triggers:
        return "No guaranteed trigger tokens found."
    return ", ".join(repr(trigger) for trigger in triggers)


def preview_list(values: list[str], limit: int = 5) -> str:
    if not values:
        return "[]"

    preview = ", ".join(repr(value) for value in values[:limit])
    if len(values) > limit:
        preview += ", ..."
    return f"[{preview}]"
