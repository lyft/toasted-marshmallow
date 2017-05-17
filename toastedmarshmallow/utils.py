import os
from contextlib import contextmanager

if False:  # pylint: disable=using-constant-test
    # pylint: disable=unused-import
    from typing import List, Union


class IndentedString(object):
    """Utility class for printing indented strings via a context manager.

    """
    def __init__(self, content='', indent=4):
        # type: (Union[str, IndentedString], int) -> None
        self.result = []  # type: List[str]
        self._indent = indent
        self.__indents = ['']
        if content:
            self.__iadd__(content)

    @contextmanager
    def indent(self):
        self.__indents.append(self.__indents[-1] + (self._indent * ' '))
        try:
            yield
        finally:
            self.__indents.pop()

    def __iadd__(self, other):
        # type: (Union[str, IndentedString]) -> IndentedString
        if isinstance(other, IndentedString):
            for line in other.result:
                self.result.append(self.__indents[-1] + line)
        else:
            self.result.append(self.__indents[-1] + other)
        return self

    def __str__(self):
        # type: () -> str
        return os.linesep.join(self.result)
