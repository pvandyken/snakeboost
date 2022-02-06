# pylint: disable=missing-class-docstring, invalid-name
from __future__ import absolute_import

from collections import UserList
from typing import Union

from snakeboost.bash.abstract import ShCmd
from snakeboost.bash.statement import StringLike


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

    def __init__(self, _from: StringLike, _to: StringLike):
        super().__init__(f"{_from} {_to}")


class cat(ShSingleCmd):
    cmd = "cat"

    def __init__(self, item: StringLike = None):
        super().__init__(item or "")


class ShPipe(UserList, ShCmd):
    def __or__(self, other: Union[ShCmd, str]):
        if isinstance(other, ShPipe):
            return self.__class__([*self.data, *other])
        return self.__class__([*self.data, other])

    def __str__(self):
        return " | ".join(str(data) for data in self.data)
