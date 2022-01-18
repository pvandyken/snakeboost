# pylint: disable=missing-class-docstring, invalid-name
from __future__ import absolute_import

import random
import string
from collections import UserList
from pathlib import Path
from typing import Union


class ShVar:
    def __init__(self, name: str):
        self.name = (
            name
            if name
            else ("".join(random.choice(string.ascii_letters) for _ in range(8)))
        )

    def __str__(self):
        return f"${self.name}"


StringLike = Union[str, Path, ShVar]


class ShCmd:
    pass


class ShSingleCmd(ShCmd):
    cmd: str

    def __init__(self, expr: str = ""):
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


class ShPipe(UserList[ShCmd], ShCmd):
    def __or__(self, other: ShCmd):
        if isinstance(other, ShPipe):
            return self.__class__([*self.data, *other])
        return self.__class__([*self.data, other])

    def __str__(self):
        return " | ".join(str(data) for data in self.data)
