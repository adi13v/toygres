from toygres.utils import looks_like_meta
from prompt_toolkit.completion import Completer, Completion
from .utils import looks_like_sql


class HistoryCompleter(Completer):
    def __init__(self, history):
        self.history = history

    def get_completions(self, document, complete_event):
        word = document.text_before_cursor

        for entry in self.history.get_strings():
            if (
                looks_like_sql(entry) or looks_like_meta(entry)
            ) and entry.lower().startswith(word.lower()):
                yield Completion(
                    entry,
                    start_position=-len(word),
                )
