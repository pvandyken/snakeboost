# pylint: disable=missing-class-docstring, invalid-name
from __future__ import absolute_import

import hashlib
import textwrap
from typing import NamedTuple, Tuple, Union

from snakeboost.sh_cmd import (
    DEBUG,
    ShBlock,
    ShCmd,
    ShEntity,
    ShStatement,
    ShVar,
    StringLike,
    canonicalize,
    echo,
)

BashWrapper = NamedTuple(
    "BashWrapper",
    [
        ("before", Tuple[ShEntity]),
        ("success", Tuple[ShEntity]),
        ("failure", Tuple[ShEntity]),
    ],
)


def block_args(cmd: Tuple[ShEntity]):
    if len(cmd) > 1:
        return str(ShBlock(*cmd, wrap=False))
    return str(canonicalize(cmd)[0])


def get_replacement_field(
    field_name: str = None,
    format_spec: str = None,
    conversion: str = None,
):
    if not field_name:
        return ""
    contents = "".join(
        filter(
            None,
            [
                field_name,
                f"!{conversion}" if conversion else None,
                f":{format_spec}" if format_spec else None,
            ],
        )
    )
    return f"{{{contents}}}"


class ShIfBody(ShStatement):
    def __init__(self, preamble: str, cmds: Tuple[ShEntity]):
        body = block_args(cmds)
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
    def not_empty(cls, expr: StringLike):
        return cls.n(expr)


def subsh(*args: ShEntity):
    cmd = block_args(args)
    if DEBUG and len(cmd) > 40:
        return f"$(\n{textwrap.indent(cmd, '    ')}\n)"
    return f"$({cmd})"


class ShFor(ShStatement):
    def __init__(self, var: StringLike, _in: StringLike):
        self.var = var
        self._in = _in

    def do(self, *cmds: ShEntity):
        body = block_args(cmds)
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


def quote_escape(text: str):
    return text.replace("'", "'\"'\"'")


def silent_mv(src: str, dest: str):
    """This was written out of concern for mv affecting the file timestamp, but it
    doesn't seem to. Leaving this here for now, but should eventually be removed if
    we never encounter problems."""
    return (
        # f"timestamp=$(stat -c %y {src}) && "
        f"mv {src} {dest}"
        # f"touch -hd \"$timestamp\" {dest}"
    )


def cp_timestamp(src: str, dest: str):
    return f"timestamp=$(stat -c %y {src}) && " f'touch -hd "$timestamp" {dest}'


def hash_path(name: str):
    return f"$(realpath '{quote_escape(name)}' | md5sum | awk '{{{{print $1}}}}')"


def rm_if_exists(path: str, recursive: bool = False):
    if recursive:
        flag = "-rf"
    else:
        flag = ""
    return f"( [ ! -e {path} ] || rm {flag} {path} )"


def split(text: str):
    return subsh(echo(text))


def resolve(path: StringLike, no_symlinks: bool = False):
    s = "-s" if no_symlinks else ""
    return subsh(f"realpath {s} {path}")


def get_hash(items: str):
    encoded = items.encode("utf-8")
    return hashlib.md5(encoded).hexdigest()


def escaped(text: str, char_pos: int):
    return char_pos > 0 and text[char_pos - 1] == "\\"


# pylint: disable=too-many-branches
def within_quotes(text: str, curr: int = 0) -> int:
    double = text.index('"') if '"' in text else len(text)
    single = text.index("'") if "'" in text else len(text)
    if double == len(text) and single == len(text):
        return curr

    if curr == 0:
        if double < single:
            if escaped(text, double):
                result = 0
            else:
                result = -1
        else:
            if escaped(text, single):
                result = 0
            else:
                result = 1

    elif curr == -1:
        if double < single:
            if escaped(text, double):
                result = -1
            else:
                result = 0

        # Don't worry about escaping single quote within double quote
        else:
            result = -1
    else:
        if double < single:
            result = 1
        # Can't escape single quote within single quotes
        else:
            result = 0

    tail = (double if double < single else single) + 1
    if tail == len(text):
        return result
    return within_quotes(text[tail:], result)
