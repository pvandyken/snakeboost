# pylint: disable=missing-class-docstring
from __future__ import absolute_import

import os
import stat
import string
from pathlib import Path
from typing import Any, Iterable, Optional, Tuple, Union, cast

import attr
import more_itertools as itx
import pygments as pyg
from colorama import Fore
from pygments.formatters.terminal import TerminalFormatter
from pygments.formatters.terminal256 import (
    Terminal256Formatter,
    TerminalTrueColorFormatter,
)
from pygments.lexers.shell import BashLexer

import snakeboost.bash as sh
from snakeboost.bash.globals import Globals
from snakeboost.bash.statement import ShBlock
from snakeboost.env import Env
from snakeboost.general import Enhancer
from snakeboost.script import Pyscript
from snakeboost.tar import Tar
from snakeboost.utils import get_hash, get_replacement_field, within_quotes


class _TestLogger:
    class Handler:
        nocolor = False

    stream_handler = Handler()


# pylint: disable=invalid-name
@attr.frozen
class _ANSI:
    colorize: bool = True

    def _f(self, arg: str):
        return arg if self.colorize else ""

    @property
    def WHITE(self):
        return self._f(Fore.WHITE)

    @property
    def YELLOW(self):
        return self._f(Fore.YELLOW)

    @property
    def RESET(self):
        return self._f(Fore.RESET)

    @property
    def ALT_BUFF(self):
        return self._f("\033[?1049h")

    @property
    def MAIN_BUFF(self):
        return self._f("\033[?1049l")

    @property
    def _formatter(self):
        if os.environ.get("COLORTERM", "") in ("truecolor", "24bit"):
            return TerminalTrueColorFormatter(style="material")
        if "256" in os.environ.get("TERM", ""):
            return Terminal256Formatter(style="material")
        return TerminalFormatter()

    def _highlight(self, text: str):
        if self.colorize:
            return pyg.highlight(text, BashLexer(), self._formatter)
        return text

    def colorize_cmd(self, cmd: str):
        literals, *field_components = zip(*string.Formatter().parse(cmd))
        fields = [
            get_replacement_field(*field_component)
            for field_component in zip(*field_components)
        ]
        escaped_literals = [
            literal.replace("{", "{{").replace("}", "}}") if literal else ""
            for literal in literals
        ]
        merged = "".join(_quote_variables(zip(escaped_literals, fields), context=[0]))
        return (
            self._highlight(merged)
            .strip()
            .replace("\n", f"{self.YELLOW}\n#... {self.RESET}")
        )


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


# pylint: disable=dangerous-default-value
def _quote_variables(
    components: Iterable[Tuple[Optional[str], Optional[str]]], context=[1]
):
    quote_status = 0
    for literal, variable in components:
        lit = literal or ""
        quote_status = within_quotes(lit, quote_status)
        if quote_status in context:
            yield f"{lit}'{variable}'" if variable else lit
            continue
        yield f"{lit}{variable}" if variable else lit


def sh_strict():
    if Globals.DEBUG:
        return "set -euo pipefail\n"
    return "set -euo pipefail; "


def _parse_boost_args(args):
    if all(isinstance(arg, str) for arg in args):
        return tuple(), ShBlock(*args, wrap=False).to_str()
    *funcs, core_cmd = args
    if isinstance(core_cmd, str):
        return funcs, ShBlock(core_cmd, wrap=False).to_str()
    return funcs, ShBlock(*core_cmd, wrap=False).to_str()


def _enhancer_hashes(funcs: Iterable[Enhancer]):
    return get_hash("".join(sorted([func.hash for func in funcs])))


@attr.define
class Boost:
    script_root: Path = attr.ib(converter=Path)
    logger: Any
    debug: bool = False
    disable_script: bool = attr.ib(kw_only=True, default=False)

    # pylint: disable=too-many-locals
    def __call__(self, *funcs_and_cmd):
        """Pipe a value through a sequence of functions"""
        Globals.DEBUG = self.debug

        ansi = _ANSI(colorize=not getattr(self.logger.stream_handler, "nocolor", False))
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
            _quote_variables(
                (literal, field_subs[field] if field in field_subs else None)
                for literal, field in zip(cast(Tuple[str], literals), fields)
            )
        )

        script_root = self.script_root / "__sb_scripts__"
        script_root.mkdir(exist_ok=True, parents=True)
        script_path = script_root / get_hash(_enhancer_hashes(funcs) + core_cmd)
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
            cmd_wrapped = f"{ansi.ALT_BUFF}\n\n{calling_cmd}\n#{ansi.MAIN_BUFF}"

        for func in funcs:
            core_cmd = func.log_format(core_cmd)
        return (
            f"# Snakeboost enhanced: to view script, set Boost(debug=True)\n## > "
            f"{ansi.colorize_cmd(core_cmd)}"
            f"{cmd_wrapped}"
        )


if __name__ == "__main__":
    rename_awk_expr = (
        "number=substr($(NF), match($(NF), /[0-9]{{5}}/), 5)",
        "split($(NF), parts, number)",
        'printf "%s "output"/%s%05d%s\\n", $0, parts[1], number+offset, parts[2]',
    )
    env = Env()
    print(
        Boost(Path("/tmp"), _TestLogger, debug=True)(
            Tar(Path("/tmp")).using(
                inputs=["{input.data}", "input.atlas"],
                outputs=["{output}"],
            ),
            env.tracked(
                tmpdir="{resources.tmpdir}/reformat_clusters/{wildcards.subject}"
            ),
            env.untracked(
                foo="bar",
            ),
            (
                vtp_dir := sh.ShVar("{sb_env.tmpdir}/vtp-tracts"),
                sh.ShTry(
                    sh.mkdir(vtp_dir).p,
                    sh.mv("{input}/tracts_left_hemisphere/*", vtp_dir),
                    sh.find("{input}/tracts_right_hemisphere/ -type f")
                    | sh.awk(*rename_awk_expr).F("/").v(offset="800", output=vtp_dir)
                    | "xargs -L 1 mv",
                    sh.find("{input}/tracts_commissural/ -type f")
                    | sh.awk(*rename_awk_expr).F("/").v(offset="1600", output=vtp_dir)
                    | "xargs -L 1 mv",
                    Pyscript(".")(
                        input={"input": vtp_dir},
                        output={"output": "{sb_env.tmpdir}/vtk-tracts"},
                        script="snakeboost/boost.py",
                    ),
                    sh.find("{sb_env.tmpdir}/vtk-tracts -type f")
                    | sh.awk('print $0 " {output}/"$(NF-1)".tck"').F("[./]")
                    | "xargs -L 1 tckconvert",
                )
                .catch("rm {sb_env.tmpdir} -rf", "false")
                .els("rm {sb_env.tmpdir} -rf"),
            ),
        )
    )
