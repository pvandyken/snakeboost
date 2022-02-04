# pylint: disable=missing-class-docstring, invalid-name
from __future__ import absolute_import

import itertools as it
import textwrap
from collections import UserList
from pathlib import Path
from string import ascii_lowercase
from typing import Iterable, Optional, Tuple, Union

from snakeboost.bash.globals import Globals


def _var_names():
    prefix_generator = _var_names()
    prefix = ""
    for i, l in enumerate(it.chain.from_iterable(it.repeat(ascii_lowercase))):
        if i > 0 and i % len(ascii_lowercase) == 0:
            # pylint: disable=stop-iteration-return
            prefix = next(prefix_generator)
        yield prefix + l


class ShVar:
    name_generator = _var_names()
    active_names = set()

    def __init__(self, value: Optional["StringLike"] = None, *, name: str = None):
        if name in self.active_names:
            raise ValueError(f"{name} has already been defined, perhaps automatically")
        if name:
            self.name = name
        else:
            candidate = next(self.name_generator)
            while candidate in self.active_names:
                candidate = next(self.name_generator)
            self.name = candidate
        self.value = value

    def __str__(self):
        return f"${self.name}"

    def set(self, value: "StringLike"):
        self.value = value
        return self

    @property
    def set_statement(self):
        if self.value is None:
            return f"{self.name}=''"
        return f"{self.name}={self.value}"


StringLike = Union[str, Path, ShVar]  # type: ignore


class ShStatement:
    def to_str(self):
        return str(self)


class ShCmd(ShStatement):
    pass


class ShSingleCmd(ShCmd):
    cmd: str

    def __init__(self, expr: StringLike = ""):
        self.expr = expr
        self.flags = []
        self.args = []

    def __or__(self, other: Union[ShCmd, str]):
        if isinstance(other, ShPipe):
            return ShPipe([self, *other])
        return ShPipe([self, other])

    def __str__(self):
        flags = f"-{''.join(self.flags)}" if self.flags else ""
        args = " ".join(self.args) if self.args else ""
        return f"{self.cmd} {flags} {args} {self.expr}"


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
        self.flags.append("l")
        return self


class echo(ShSingleCmd):
    cmd = "echo"

    def __init__(self, expr: StringLike):
        super().__init__(expr)

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
        self.flags.append("p")
        return self


class mv(ShSingleCmd):
    cmd = "mv"

    def __init__(self, _from: StringLike, _to: StringLike, /):
        super().__init__(f"{_from} {_to}")


class ShPipe(UserList, ShCmd):
    def __or__(self, other: Union[ShCmd, str]):
        if isinstance(other, ShPipe):
            return self.__class__([*self.data, *other])
        return self.__class__([*self.data, other])

    def __str__(self):
        return " | ".join(str(data) for data in self.data)


ShEntity = Union[str, ShStatement, ShVar, "ShBlock", Tuple["ShEntity", ...]]


def canonicalize(entities: Iterable[ShEntity]):
    return [
        ShBlock(*entity)
        if isinstance(entity, tuple)
        else entity.set_statement
        if isinstance(entity, ShVar)
        else entity
        for entity in entities
        if entity
    ]


class ShBlock(ShStatement):
    def __init__(self, *args: ShEntity, wrap: bool = True):
        self.statements = canonicalize(args)
        self.wrap = wrap

    def __str__(self):
        if Globals.DEBUG:
            sep = "\n"
            wrap = lambda s: f"(\n{textwrap.indent(s, '    ')}\n)"  # noqa: E731
        else:
            sep = "; "
            wrap = lambda s: f"( {s} )"  # noqa: E731

        body = sep.join(str(statement) for statement in self.statements)
        if self.wrap:
            return wrap(body)
        return body
