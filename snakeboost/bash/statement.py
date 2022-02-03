# pylint: disable=missing-class-docstring, invalid-name
from __future__ import absolute_import

import textwrap
from typing import NamedTuple, Tuple, Union

from snakeboost.bash.cmd import (
    DEBUG,
    ShBlock,
    ShCmd,
    ShEntity,
    ShStatement,
    ShVar,
    StringLike,
    canonicalize,
)
from snakeboost.bash.utils import quote_escape

BashWrapper = NamedTuple(
    "BashWrapper",
    [
        ("before", Tuple[ShEntity]),
        ("success", Tuple[ShEntity]),
        ("failure", Tuple[ShEntity]),
    ],
)


def _block_args(cmd: Tuple[ShEntity]):
    if len(cmd) > 1:
        return str(ShBlock(*cmd, wrap=False))
    return str(canonicalize(cmd)[0])


class ShIfBody(ShStatement):
    def __init__(self, preamble: str, cmds: Tuple[ShEntity]):
        body = _block_args(cmds)
        if DEBUG:
            statement = f"\n{textwrap.indent(body, '    ')}"
        else:
            statement = body
        self.expr = f"{preamble} {statement}"

    def __str__(self):
        if DEBUG:
            closer = "\nfi"
        else:
            closer = "; fi"
        return f"{self.expr}{closer}"

    def els(self, *cmd: ShEntity):
        if DEBUG:
            return self.__class__(f"{self.expr}\nelse", cmd)
        return self.__class__(f"{self.expr}; else", cmd)

    def __rshift__(self, cmd: ShEntity):
        if isinstance(cmd, tuple):
            return self.els(*cmd)
        return self.els(cmd)


class ShIf:
    def __init__(self, expr: Union[StringLike, ShCmd] = ""):
        if isinstance(expr, ShCmd):
            self.expr = subsh(expr)
        else:
            self.expr = expr

    def __str__(self):
        return f"[[ {self.expr} ]]"

    def then(self, *cmd: ShEntity):
        return ShIfBody(f"if [[ {self.expr} ]]; then", cmd)

    def __rshift__(self, cmd: ShEntity):
        if isinstance(cmd, tuple):
            return self.then(*cmd)
        return self.then(cmd)

    def gt(self, expr: Union[StringLike, int]):
        return self.__class__(f"{self.expr} -gt {expr}")

    @classmethod
    def isnt(cls):
        return ShIfNot

    @classmethod
    def e(cls, expr: StringLike):
        return cls(f"-e {expr}")

    @classmethod
    def exists(cls, expr: StringLike):
        return cls.e(expr)

    @classmethod
    def d(cls, expr: StringLike):
        return cls(f"-d {expr}")

    @classmethod
    def is_dir(cls, expr: StringLike):
        return cls.d(expr)

    @classmethod
    def h(cls, expr: StringLike):
        return cls(f"-h {expr}")

    @classmethod
    def is_symlink(cls, expr: StringLike):
        return cls.h(expr)

    @classmethod
    def n(cls, expr: StringLike):
        return cls(f"-n {expr}")

    @classmethod
    def x(cls, expr: StringLike):
        return cls(f"-x {expr}")

    @classmethod
    def executable(cls, expr: StringLike):
        return cls.x(expr)

    @classmethod
    def not_empty(cls, expr: StringLike):
        return cls.n(expr)


class ShIfNot(ShIf):
    def __init__(self, expr: Union[StringLike, ShCmd] = ""):
        if isinstance(expr, ShCmd):
            expr = subsh(expr)
        super().__init__(f"! {expr}")


class ShTry(ShStatement):
    def __init__(self, *args: ShEntity):
        self.cmd = ShBlock(*args)
        self._catch = ""
        self._els = ""

    def els(self, *cmds: ShEntity):
        self._els = ShBlock(*cmds)
        return self

    def catch(self, *cmds: ShEntity):
        self._catch = ShBlock(*cmds)
        return self

    def __str__(self):
        catch = f"|| {self._catch}" if self._catch else ""
        els = f"&& {self._els}" if self._els else ""
        return ShBlock(f"{self.cmd} {els} {catch}").to_str()


def subsh(*args: ShEntity):
    cmd = _block_args(args)
    if DEBUG and len(cmd) > 40:
        return f"$(\n{textwrap.indent(cmd, '    ')}\n)"
    return f"$({cmd})"


class ShFor(ShStatement):
    def __init__(self, var: StringLike, _in: StringLike):
        self.var = var
        self._in = _in

    def do(self, *cmds: ShEntity):
        body = _block_args(cmds)
        if DEBUG:
            statement = f"\n{textwrap.indent(body, '    ')}\ndone"
        else:
            statement = f"{body}; done"

        var_name = self.var.name if isinstance(self.var, ShVar) else self.var
        return f"for {var_name} in {self._in}; do {statement}"

    def __rshift__(self, cmd: ShEntity):
        if isinstance(cmd, tuple):
            return self.do(*cmd)
        return self.do(cmd)


class Flock:
    def __init__(self, file: StringLike, wait: int = 900):
        self._wait = wait
        self._file = file

    def do(self, *cmds: ShEntity):
        cmd = quote_escape(_block_args(cmds))
        suffix = f"| flock -w {self._wait} {self._file} /bin/bash"
        if DEBUG:
            return f"echo '\n{textwrap.indent(cmd, '    ')}\n' {suffix}"
        return f"echo '{cmd}' {suffix}"
