# pylint: disable=missing-class-docstring
from __future__ import absolute_import

import os
import stat
import string
from pathlib import Path
from typing import Iterable, Optional, Tuple, Union, cast

import attr
import more_itertools as itx

from snakeboost.bash.globals import Globals
from snakeboost.bash.statement import ShBlock
from snakeboost.utils import get_hash, get_replacement_field, within_quotes


def _pipe(*funcs_and_cmd):
    """ Pipe a value through a sequence of functions

    I.e. ``pipe(f, g, h, cmd)`` is equivalent to ``f(g(h(cmd)))``

    We think of the value as progressing through a pipe of several
    transformations, much like pipes in UNIX

    ``$ cat data | h | g | f``

    >>> double = lambda i: 2 * i
    >>> pipe(3, double, str)
    '6'

    Adapted from [pytoolz implementation]\
        (https://toolz.readthedocs.io/en/latest/_modules/toolz/functoolz.html#pipe)
    """
    cmd = funcs_and_cmd[-1]
    for func in reversed(funcs_and_cmd[:-1]):
        cmd = func(cmd)
    return cmd


def _chmod_rwx(path: Union[Path, str]):
    os.chmod(path, stat.S_IXUSR | stat.S_IRUSR | stat.S_IWUSR)


def _construct_script(components: Iterable[Tuple[str, Optional[str]]]):
    quote_status = 0
    for literal, variable in components:
        quote_status = within_quotes(literal, quote_status)
        if quote_status > 0:
            yield f"{literal}'{variable}'" if variable else literal
            continue
        yield f"{literal}{variable}" if variable else literal


def sh_strict():
    if Globals.DEBUG:
        return "set -euo pipefail\n"
    return "set -euo pipefail; "


def _colorize_cmd(cmd: str):
    literals, *field_components = zip(*string.Formatter().parse(cmd))
    fields = [
        get_replacement_field(*field_component)
        for field_component in zip(*field_components)
    ]
    escaped_literals = [
        literal.replace("{", "{{").replace("}", "}}").replace("\n", "\n\033[0;33m#...\033[0;37m") if literal else None
        for literal in literals
    ]
    return "\033[0m" + "".join(
        [
            f"{literal or ''}" + (f"\033[0;33m'{field}'\033[0;37m" if field else "")
            for literal, field in zip(escaped_literals, fields)
        ]
    )


def _parse_boost_args(args):
    *funcs, core_cmd = args
    if isinstance(core_cmd, str):
        return funcs, ShBlock(core_cmd, wrap=False).to_str()
    return funcs, ShBlock(*core_cmd, wrap=False).to_str()


@attr.define
class Boost:
    script_root: Path = attr.ib(converter=Path)
    debug: bool = False
    disable_script: bool = attr.ib(kw_only=True, default=False)

    # pylint: disable=too-many-locals
    def __call__(self, *funcs_and_cmd):
        """Pipe a value through a sequence of functions"""
        Globals.DEBUG = self.debug
        funcs, core_cmd = _parse_boost_args(funcs_and_cmd)
        cmd = sh_strict() + _pipe(*funcs, core_cmd)

        if self.disable_script:
            return cmd

        literals, *field_components = zip(*string.Formatter().parse(cmd))
        fields = [
            get_replacement_field(*field_component)
            for field_component in zip(*field_components)
        ]
        unique_fields = [*filter(None, itx.unique_everseen(fields))]
        field_subs = {field: f"${{{i + 1}}}" for i, field in enumerate(unique_fields)}
        script = "#!/bin/bash\n" + "".join(
            _construct_script(
                (literal, field_subs[field] if field in field_subs else None)
                for literal, field in zip(cast(Tuple[str], literals), fields)
            )
        )

        script_root = self.script_root / "__sb_scripts__"
        script_root.mkdir(exist_ok=True, parents=True)
        script_path = script_root / get_hash(script)
        if not script_path.exists():
            with (script_path).open("w") as f:
                f.write(script)
            _chmod_rwx(script_path)

        calling_cmd = f"{script_path} " + " ".join(
            [f"'{field}'" for field in unique_fields]
        )

        if self.debug:
            cmd_wrapped = f"\n\n{calling_cmd}"
        else:
            cmd_wrapped = f"\033[?1049h\n\n{calling_cmd}\n#\033[?1049l"

        return (
            f"# Snakeboost enhanced: to view script, set Boost(debug=True)\n# > "
            f"{_colorize_cmd(core_cmd)}"
            f"\033[0m{cmd_wrapped}"
        )
