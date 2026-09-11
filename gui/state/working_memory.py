"""
Working Memory for the active user session.

Temporary state maintained by the GUI layer.
Never written to the Persistent Memory (wiki/).
Discarded when the application closes.
"""

from dataclasses import dataclass, field


@dataclass
class WorkingMemory:
    focus: str = ""
    current_entities: list = field(default_factory=list)
    last_question: str = ""
    last_answer: str = ""

    def clear(self):
        self.focus = ""
        self.current_entities = []
        self.last_question = ""
        self.last_answer = ""

    def is_empty(self) -> bool:
        return not any([
            self.focus,
            self.current_entities,
            self.last_question,
            self.last_answer,
        ])

    def to_display(self) -> dict[str, str]:
        return {
            "Focus": self.focus or "—",
            "Last Question": "Available" if self.last_question else "—",
            "Last Answer": "Available" if self.last_answer else "—",
            "Entities": str(len(self.current_entities)) if self.current_entities else "0",
        }

    def to_context(self) -> str:
        """
        Return session state for the Query Agent.

        Structured as operational facts, not conversation history, so the
        agent treats resolved entities as given rather than re-deriving them.
        """

        if self.is_empty():
            return ""

        lines = ["SESSION STATE", ""]

        if self.focus:
            lines.append(f"Current Subject: {self.focus}")
            lines.append("")

        if self.current_entities:
            lines.append("Resolved Entities:")
            for entity in self.current_entities:
                lines.append(f"- {entity}")
            lines.append("")
            lines.append(
                "These entities are already identified for this session.\n"
                "Use them directly.\n"
                "Do not search the index again unless the question introduces a new topic."
            )
            lines.append("")

        lines.append(
            "This is conversational context only.\n"
            "It is NOT evidence. Evidence must always come from the wiki."
        )

        return "\n".join(lines)