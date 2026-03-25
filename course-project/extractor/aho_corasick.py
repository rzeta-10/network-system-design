from collections import deque
import re


class AhoCorasick:
    """Multi-pattern automaton for O(n + m) streaming trigger search.

    Scans a text in a single left-to-right pass regardless of how many
    trigger patterns are present. This is the correct implementation of the
    "efficiently detectable in input streams" requirement from the assignment.

    Build once, reuse across many texts:

        ac = AhoCorasick.from_triggers(triggers)
        for text in stream:
            if ac.search(text):
                run_regex(text)
    """

    def __init__(self) -> None:
        # goto[state][char] -> next state (trie transitions)
        self._goto: list[dict[str, int]] = [{}]
        # fail[state] -> longest proper suffix state (failure links)
        self._fail: list[int] = [0]
        # output[state] -> patterns that end at this state (including via fail chain)
        self._output: list[list[str]] = [[]]
        # ordered list of inserted patterns (preserved for to_compiled_regex)
        self._patterns: list[str] = []
        self._built = False

    # ------------------------------------------------------------------
    # Building phase
    # ------------------------------------------------------------------

    def add(self, pattern: str) -> None:
        """Insert one trigger pattern into the trie (call before build)."""
        if self._built:
            raise RuntimeError("cannot add patterns after build()")
        if not pattern:
            return
        if pattern not in self._patterns:
            self._patterns.append(pattern)
        state = 0
        for char in pattern:
            if char not in self._goto[state]:
                self._goto[state][char] = len(self._goto)
                self._goto.append({})
                self._fail.append(0)
                self._output.append([])
            state = self._goto[state][char]
        if pattern not in self._output[state]:
            self._output[state].append(pattern)

    def build(self) -> None:
        """Compute failure links via BFS. Must be called once after all add() calls."""
        queue: deque[int] = deque()

        for state in self._goto[0].values():
            self._fail[state] = 0
            queue.append(state)

        while queue:
            r = queue.popleft()
            for char, s in self._goto[r].items():
                queue.append(s)
                # Walk failure links from r's parent to find longest suffix match
                state = self._fail[r]
                while state != 0 and char not in self._goto[state]:
                    state = self._fail[state]
                self._fail[s] = self._goto[state].get(char, 0)
                if self._fail[s] == s:
                    self._fail[s] = 0
                # Merge outputs from the failure state
                for out in self._output[self._fail[s]]:
                    if out not in self._output[s]:
                        self._output[s].append(out)

        self._built = True

    # ------------------------------------------------------------------
    # Search phase
    # ------------------------------------------------------------------

    def search(self, text: str) -> bool:
        """Return True as soon as any trigger pattern is found in text. O(n)."""
        if not self._built:
            raise RuntimeError("call build() before search()")
        state = 0
        for char in text:
            while state != 0 and char not in self._goto[state]:
                state = self._fail[state]
            state = self._goto[state].get(char, 0)
            if self._output[state]:
                return True
        return False

    # ------------------------------------------------------------------
    # Convenience constructor
    # ------------------------------------------------------------------

    def to_compiled_regex(self) -> "re.Pattern[str]":
        """Return a compiled regex equivalent to this automaton.

        Python's re module compiles the alternation into a C-speed automaton,
        giving O(n) search performance equivalent to this Aho-Corasick
        automaton but running at native speed. Use this in performance-critical
        loops; use search() for educational or non-Python environments where
        native compilation is not available.
        """
        if not self._patterns:
            return re.compile(r"(?!)")  # pattern that never matches
        return re.compile("|".join(re.escape(p) for p in self._patterns))

    @classmethod
    def from_triggers(cls, triggers: list[str]) -> "AhoCorasick":
        """Build a ready-to-search automaton from a list of trigger tokens."""
        ac = cls()
        for trigger in triggers:
            ac.add(trigger)
        ac.build()
        return ac
