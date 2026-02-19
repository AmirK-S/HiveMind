from enum import Enum

class OutcomeRequestOutcome(str, Enum):
    DID_NOT_HELP = "did_not_help"
    SOLVED = "solved"

    def __str__(self) -> str:
        return str(self.value)
