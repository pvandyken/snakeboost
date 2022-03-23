# pylint: disable=missing-class-docstring, invalid-name
from __future__ import absolute_import

import itertools as it
import textwrap
from pathlib import Path
from string import ascii_lowercase
from typing import Iterable, NamedTuple, Optional, Tuple, Union

from snakeboost.bash.abstract import ShCmd, ShStatement
from snakeboost.bash.globals import Globals
from snakeboost.bash.utils import quote_escape


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

    def __init__(
        self,
        value: Optional["ShEntity"] = None,
        *,
        name: str = None,
        export: bool = False,
    ):
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
        self.export = export

    def __str__(self):
        return f"${self.name}"

    def set(self, value: Union["StringLike", ShCmd]):
        self.value = value
        return self

    @property
    def set_statement(self):
        if self.export:
            export = "export "
        else:
            export = ""
        if self.value is None:
            return f"{self.name}=''"
        if any(
            [
                isinstance(self.value, str),
                isinstance(self.value, ShVar),
                isinstance(self.value, Path),
            ]
        ):
            return f"{export}{self.name}={self.value}"
        return f"{export}{self.name}={subsh(self.value)}"  # type: ignore


StringLike = Union[str, Path, ShVar]  # type: ignore


ShEntity = Union[str, ShStatement, ShVar, "ShBlock", Tuple["ShEntity", ...]]


BashWrapper = NamedTuple(
    "BashWrapper",
    [
        ("before", Tuple[ShEntity]),
        ("success", Tuple[ShEntity]),
        ("failure", Tuple[ShEntity]),
    ],
)


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


def _block_args(cmd: Tuple[ShEntity]):
    if len(cmd) > 1:
        return str(ShBlock(*cmd, wrap=False))
    return str(canonicalize(cmd)[0])


class ShIfBody(ShStatement):
    def __init__(self, preamble: str, cmds: Tuple[ShEntity]):
        body = _block_args(cmds)
        if Globals.DEBUG:
            statement = f"\n{textwrap.indent(body, '    ')}"
        else:
            statement = " " + body
        self.expr = f"{preamble}{statement}"

    def __str__(self):
        if Globals.DEBUG:
            closer = "\nfi"
        else:
            closer = "; fi"
        return f"{self.expr}{closer}"

    def els(self, *cmd: ShEntity):
        if Globals.DEBUG:
            return self.__class__(f"{self.expr}\nelse", cmd)
        return self.__class__(f"{self.expr}; else", cmd)

    def __rshift__(self, cmd: ShEntity):
        if isinstance(cmd, tuple):
            return self.els(*cmd)
        return self.els(cmd)


class ShIf:
    def __init__(self, expr: Union[StringLike, ShCmd] = ""):
        if isinstance(expr, ShCmd):
            self.expr = f'"{subsh(expr)}"'
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

    def __or__(self, expr: "ShIf"):
        return ShIf(f"{self.expr} || {expr.expr}")

    def gt(self, expr: Union[StringLike, int]):
        return self.__class__(f"{self.expr} -gt {expr}")

    def eq(self, expr: Union[StringLike, int, ShCmd]):
        if isinstance(expr, ShCmd):
            expr = f'"{subsh(expr)}"'
        return self.__class__(f"{self.expr} == {expr}")

    def ne(self, expr: Union[StringLike, int, ShCmd]):
        if isinstance(expr, ShCmd):
            expr = f'"{subsh(expr)}"'
        return self.__class__(f"{self.expr} != {expr}")

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
        self.cmd = ShBlock("set -e", *args)
        self._catch = ""
        self._els = ""

    def els(self, *cmds: ShEntity):
        self._els = cmds
        return self

    def catch(self, *cmds: ShEntity):
        self._catch = cmds
        return self

    def __str__(self):
        ex_code = ShVar("$?")
        catch = ShIf(ex_code).ne(0).then(*self._catch) if self._catch else ""
        els = ShIf(ex_code).eq(0).then(*self._els) if self._els else ""
        return ShBlock(
            "[[ $- = *e* ]]; SAVED_OPT_E=$?",
            "set +e",
            self.cmd,
            ex_code,
            "(( $SAVED_OPT_E )) && set +e || set -e",
            catch,
            els,
        ).to_str()


def subsh(*args: ShEntity):
    cmd = _block_args(args)
    if Globals.DEBUG and len(cmd) > 40:
        return f"$(\n{textwrap.indent(cmd, '    ')}\n)"
    return f"$({cmd})"


class ShForBody(ShStatement):
    def __init__(self, var: StringLike, _in: StringLike, do: str):
        self.var = var
        self._in = _in
        self.do = do

    def __str__(self):
        if Globals.DEBUG:
            statement = f"\n{textwrap.indent(self.do, '    ')}\ndone"
        else:
            statement = f"{self.do}; done"

        var_name = self.var.name if isinstance(self.var, ShVar) else self.var
        return f"for {var_name} in {self._in}; do {statement}"


class ShFor:
    def __init__(self, var: StringLike, _in: StringLike):
        self.var = var
        self._in = _in

    def do(self, *cmds: ShEntity):
        return ShForBody(self.var, self._in, _block_args(cmds))

    def __rshift__(self, cmd: ShEntity):
        if isinstance(cmd, tuple):
            return self.do(*cmd)
        return self.do(cmd)


class Flock:
    def __init__(self, file: StringLike, wait: int = 900, abort: bool = False):
        self._wait = wait
        self._file = file
        self._abort = abort

    def do(self, *cmds: ShEntity):
        cmd = quote_escape(_block_args(cmds))
        wait = f"-w {self._wait} " if self._wait else ""
        abort = "-n " if self._abort else ""
        suffix = f"| flock {wait}{abort}{self._file} /bin/bash"
        if Globals.DEBUG:
            return f"echo '\n{textwrap.indent(cmd, '    ')}\n' {suffix}"
        return f"echo '{cmd}' {suffix}"
