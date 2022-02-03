# pylint: disable=missing-class-docstring, invalid-name
from __future__ import absolute_import

import random
import string
import textwrap
from collections import UserList
from pathlib import Path
from typing import Iterable, Tuple, Union

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

    def __init__(self, expr: StringLike):
        super().__init__(expr)
        self.flags = []

    def n(self):
        self.flags.append("n")
        return self

    def __str__(self):
        flags = f"-{''.join(self.flags)}" if self.flags else ""
        return f'{self.cmd} {flags} "{self.expr}"'


class mkdir(ShSingleCmd):
    cmd = "mkdir"

    @property
    def p(self):
        return mkdir(f"{self.expr} -p")


class ShPipe(UserList, ShCmd):
    def __or__(self, other: ShCmd):
        if isinstance(other, ShPipe):
            return self.__class__([*self.data, *other])
        return self.__class__([*self.data, other])

    def __str__(self):
        return " | ".join(str(data) for data in self.data)


ShEntity = Union[str, ShStatement, "ShBlock", Tuple["ShEntity", ...]]


def canonicalize(entities: Iterable[ShEntity]):
    return [
        ShBlock(*entity) if isinstance(entity, tuple) else entity
        for entity in entities
        if entity
    ]


class ShBlock:
    def __init__(self, *args: ShEntity, wrap: bool = True):
        self.statements = canonicalize(args)
        self.wrap = wrap

    def to_str(self):
        return str(self)

    def __str__(self):
        if DEBUG:
            sep = "\n"
            wrap = lambda s: f"(\n{textwrap.indent(s, '    ')}\n)"  # noqa: E731
        else:
            sep = "; "
            wrap = lambda s: f"( {s} )"  # noqa: E731

        body = sep.join(str(statement) for statement in self.statements)
        if self.wrap:
            return wrap(body)
        return body
