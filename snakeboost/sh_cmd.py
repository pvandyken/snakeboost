# pylint: disable=missing-class-docstring, invalid-name
from __future__ import absolute_import

import random
import string
import textwrap
from collections import UserList
from pathlib import Path
from typing import Tuple, Union

DEBUG = False


class ShVar:
    def __init__(self, name: str):
        self.name = (
            name
            if name
            else ("".join(random.choice(string.ascii_letters) for _ in range(8)))
        )

    def __str__(self):
        return f"${self.name}"

    def set(self, value: "StringLike"):
        return ShSetVariable(self.name, value)


StringLike = Union[str, Path, ShVar]


class ShStatement:
    pass


class ShSetVariable(ShStatement):
    def __init__(self, name: str, value: StringLike):
        self.name = name
        self.value = value

    def __str__(self):
        return f"{self.name}={self.value}"


class ShCmd(ShStatement):
    pass


class ShSingleCmd(ShCmd):
    cmd: str

    def __init__(self, expr: StringLike = ""):
        self.expr = expr

    def __or__(self, other: ShCmd):
        if isinstance(other, ShPipe):
            return ShPipe([self, *other])
        return ShPipe([self, other])

    def __str__(self):
        return f"{self.cmd} {self.expr}"


class find(ShSingleCmd):
    def __init__(self, root: StringLike, expr: str = ""):
        self.root = root
        super().__init__(expr)

    def __str__(self):
        return f"find {self.root} {self.expr}"

    def path(self, path: StringLike):
        return self.__class__(root=self.root, expr=f"{self.expr} -path {path}")


class wc(ShSingleCmd):
    cmd = "wc"

    def l(self):  # noqa: E741, E743
        return wc(f"{self.expr} -l")


class echo(ShSingleCmd):
    cmd = "echo"

    def n(self):
        return echo(f"{self.expr} -n")


class ShPipe(UserList, ShCmd):
    def __or__(self, other: ShCmd):
        if isinstance(other, ShPipe):
            return self.__class__([*self.data, *other])
        return self.__class__([*self.data, other])

    def __str__(self):
        return " | ".join(str(data) for data in self.data)


BlockLines = Union[str, ShStatement, "ShBlock", Tuple["BlockLines", ...]]


class ShBlock:
    def __init__(self, *args: BlockLines):
        self.statements = [
            ShBlock(*statement) if isinstance(statement, tuple) else statement
            for statement in args
        ]

    def __str__(self):
        if DEBUG:
            sep = "\n"
            wrap = lambda s: f"(\n{textwrap.indent(s, '    ')}\n)"  # noqa: E731
        else:
            sep = "; "
            wrap = lambda s: f"( {s} )"  # noqa: E731
        return wrap(sep.join(str(statement) for statement in self.statements))
