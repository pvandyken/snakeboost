# pylint: disable=missing-class-docstring
from __future__ import absolute_import

import os
import stat
import string
from pathlib import Path
from typing import Iterable, Optional, Tuple, Union, cast

import attr
import more_itertools as itx

from snakeboost.utils import get_hash, get_replacement_field, within_quotes


def _pipe(*funcs_and_cmd):
    """ Pipe a value through a sequence of functions

    I.e. ``pipe(f, g, h, cmd)`` is equivalent to ``h(g(f(cmd)))``

    We think of the value as progressing through a pipe of several
    transformations, much like pipes in UNIX

    ``$ cat data | f | g | h``

    >>> double = lambda i: 2 * i
    >>> pipe(3, double, str)
    '6'

    Adapted from [pytoolz implementation]\
        (https://toolz.readthedocs.io/en/latest/_modules/toolz/functoolz.html#pipe)
    """
    cmd = funcs_and_cmd[-1]
    for func in funcs_and_cmd[:-1]:
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


@attr.define
class Boost:
    script_root: Path = attr.ib(converter=Path)

    def __call__(self, *funcs_and_cmd):
        """Pipe a value through a sequence of functions"""
        core_cmd = funcs_and_cmd[-1]
        cmd = _pipe(*funcs_and_cmd)
        literals, *field_components = zip(*string.Formatter().parse(cmd))
        fields = [
            get_replacement_field(*field_component)
            for field_component in zip(*field_components)
        ]
        unique_fields = [*filter(None, itx.unique_everseen(fields))]
        field_subs = {field: f"${i + 1}" for i, field in enumerate(unique_fields)}
        script = "#!/bin/bash\n" + "".join(
            _construct_script(
                (literal, field_subs[field] if field in field_subs else None)
                for literal, field in zip(cast(Tuple[str], literals), fields)
            )
        )

        script_root = self.script_root / "__sb_scripts__"
        script_root.mkdir(exist_ok=True, parents=True)
        script_path = script_root / get_hash(script)
        with (script_path).open("w") as f:
            f.write(script)
        _chmod_rwx(script_path)

        quote_wrapped_fields = [f"'{field}'" for field in unique_fields]

        calling_cmd = f"{script_path} " + " ".join(quote_wrapped_fields)
        return f"# Snakeboost enhanced script:\n# > {core_cmd}\n\n{calling_cmd}\n"
