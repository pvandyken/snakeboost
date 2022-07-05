# pylint: disable=missing-class-docstring, invalid-name
from __future__ import absolute_import

import itertools as it
import textwrap
from pathlib import Path
from string import ascii_lowercase
from typing import Iterable, Optional, Tuple, Union

from snakeboost.bash.abstract import ShCmd, ShStatement
from snakeboost.bash.globals import Globals


def _var_names(prefix=""):
    parent_generator = _var_names()
    parent = ""
    for i, l in enumerate(it.chain.from_iterable(it.repeat(ascii_lowercase))):
        if i > 0 and i % len(ascii_lowercase) == 0:
            # pylint: disable=stop-iteration-return
            parent = next(parent_generator)
        yield prefix + parent + l


class ShVar:
    name_generator = _var_names(prefix="__sb_")
    active_names = set()

    def __init__(
        self,
        value: Union["ShEntity", Path, None] = None,
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
        return f"${{{{{self.name}}}}}"

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


def canonicalize(entities: Iterable[ShEntity]):
    for entity in entities:
        if not entity:
            continue
        if isinstance(entity, tuple):
            if any(entity):
                yield ShBlock(*entity)
            continue
        if isinstance(entity, ShVar):
            yield entity.set_statement
            continue
        yield entity


class ShBlock(ShStatement):
    def __init__(self, *args: ShEntity, wrap: bool = True):
        self.statements = list(canonicalize(args))
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
    return str((list(canonicalize(cmd)) or [""])[0])


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
        self.expr = self._eval_expr(expr)

    def __str__(self):
        return f"[[ {self.expr} ]]"

    def then(self, *cmd: ShEntity):
        return ShIfBody(f"if [[ {self.expr} ]]; then", cmd)

    @staticmethod
    def _eval_expr(expr: Union[StringLike, ShCmd, int]):
        if isinstance(expr, ShCmd):
            return f'"{subsh(expr)}"'
        return str(expr)

    def __rshift__(self, cmd: ShEntity):
        if isinstance(cmd, tuple):
            return self.then(*cmd)
        return self.then(cmd)

    def __or__(self, expr: "ShIf"):
        return ShIf(f"{self.expr} || {expr.expr}")

    def __and__(self, expr: "ShIf"):
        return ShIf(f"{self.expr} && {expr.expr}")

    def gt(self, expr: Union[StringLike, int]):
        return self.__class__(f"{self.expr} -gt {expr}")

    def eq(self, expr: Union[StringLike, int, ShCmd]):
        return self.__class__(f"{self.expr} == {self._eval_expr(expr)}")

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
    def n(cls, expr: Union[StringLike, ShCmd]):
        return cls(f"-n {cls._eval_expr(expr)}")

    @classmethod
    def z(cls, expr: Union[StringLike, ShCmd]):
        return cls(f"-z {cls._eval_expr(expr)}")

    @classmethod
    def empty(cls, expr: Union[StringLike, ShCmd]):
        return cls.z(expr)

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
        self._finish = ""

    def els(self, *cmds: ShEntity):
        self._els = cmds
        return self

    def catch(self, *cmds: ShEntity):
        self._catch = cmds
        return self

    def finish(self, *cmds: ShEntity):
        self._finish = cmds
        return self

    def __str__(self):
        ex_code = ShVar("$?") if any(self._catch) or any(self._els) else ""
        catch = ShIf(ex_code).ne(0).then(*self._catch) if any(self._catch) else ""
        els = ShIf(ex_code).eq(0).then(*self._els) if any(self._els) else ""
        finish = self._finish if any(self._finish) else ""
        return ShBlock(
            "[[ $- = *e* ]]; SAVED_OPT_E=$?",
            "set +e",
            self.cmd,
            ex_code,
            "(( $SAVED_OPT_E )) && set +e || set -e",
            finish,
            catch,
            els,
            # wrap=False,
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


class Flock(ShStatement):
    def __init__(
        self,
        file: StringLike,
        wait: int = 900,
        shared: bool = False,
        error: bool = True,
    ):
        self._wait = wait
        self._file = file
        self._shared = shared
        self._do = ""
        self._els: Optional[str] = None if error else ""

    def __str__(self):
        wait = f"-w {self._wait} "
        shared = "-s " if self._shared else ""
        fd = ShVar()
        main = ShBlock(
            ShBlock(
                f"flock {wait}{shared}{fd}",
                self._do,
            ).to_str()
            + f" {{{{{fd.name}}}}}>>{self._file}",
            wrap=False,
        )
        if self._els is not None:
            wrapped = ShTry(main).catch(self._els)
        else:
            wrapped = main
        return ShBlock(
            ShIf.is_dir(self._file)
            >> (f"echo \"flocked file '{self._file}' is a directory\"", "false"),
            wrapped.to_str(),
            wrap=False,
        ).to_str()

    def do(self, *cmds: ShEntity):
        self._do = _block_args(cmds)
        return self

    def els(self, *cmds: ShEntity):
        self._els = _block_args(cmds)
        return self
