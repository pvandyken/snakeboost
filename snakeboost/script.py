from __future__ import absolute_import

import argparse
import re
from collections import UserDict
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, TypeVar, Union

import attr

from snakeboost.pipenv import PipEnv


def _mapping(arg: str, values: Iterable[str]):
    return " ".join([f"{v}={{{arg}.{v}}}" for v in values])


# pylint: disable=missing-class-docstring
class ScriptDict(UserDict):
    def cli_mapping(self, arg: str):
        return _mapping(arg, self.keys())


PyscriptParam = Union[List[str], ScriptDict]


def _get_arg(arg: str, value: Optional[PyscriptParam]):
    if value is None:
        return f"--{arg} {{{arg}}}"
    if isinstance(value, ScriptDict):
        return f"--{arg} {value.cli_mapping(arg)}"
    return f"--{arg} " + _mapping(arg, value)


# pylint: disable=redefined-builtin, missing-class-docstring
# pylint: disable=attribute-defined-outside-init
@attr.define(slots=False)
class Pyscript:
    env: Optional[PipEnv] = None

    def __attrs_post_init__(self):
        self._input = None
        self._output = None
        self._params = None
        self._resources = None
        self._wildcards = None
        self._log = None

    def input(self, **kwargs):
        self._input = ScriptDict(**kwargs)
        return kwargs

    def output(self, **kwargs):
        self._output = ScriptDict(**kwargs)
        return kwargs

    def params(self, **kwargs):
        self._params = ScriptDict(**kwargs)
        return kwargs

    def resources(self, **kwargs):
        self._resources = ScriptDict(**kwargs)
        return kwargs

    def wildcards(self, **kwargs):
        self._wildcards = ScriptDict(**kwargs)
        return kwargs

    def log(self, **kwargs):
        self._log = ScriptDict(**kwargs)
        return kwargs

    # pylint: disable=too-many-arguments
    def __call__(
        self,
        script: str,
        input: PyscriptParam = None,
        output: PyscriptParam = None,
        params: PyscriptParam = None,
        wildcards: PyscriptParam = None,
        resources: PyscriptParam = None,
        log: PyscriptParam = None,
    ):
        if not Path(script).exists():
            raise FileExistsError(
                f"Could not find script: {script}\n"
                "Be sure to define paths relative to the app root, not the workflow "
                "root."
            )
        if self.env is None:
            executable = "python"
        else:
            executable = f"{self.env.get_venv} && {self.env.python_path}"
        args = " ".join(
            [
                _get_arg(arg, value)
                for arg, value in {
                    "input": input if input else self._input,
                    "output": output if output else self._output,
                    "params": params if params else self._params,
                    "wildcards": wildcards if wildcards else self._wildcards,
                    "resources": resources if resources else self._resources,
                    "log": log if log else self._log,
                }.items()
            ]
        )

        return f"{executable} {script} {args} --threads {{threads}}"


class ParseError(Exception):
    pass


T = TypeVar("T")

SnakemakeSequenceArg = Union[List[T], Dict[str, T]]


def _parse_snakemake_arg(
    converter: Callable[[str], T], values: List[str]
) -> SnakemakeSequenceArg[T]:
    matches = [re.match(r"^([^\d\W]\w*)=(?!.*=)(.*)$", value) for value in values]
    if not any(matches):
        return [converter(v) for v in values]
    if all(matches):
        return {str(m.group(1)): converter(m.group(2)) for m in matches}  # type: ignore
    valuelist = "\n\t".join(values)
    raise ParseError(f"Mixture of dict=args and listargs:\n\t{valuelist}")


# pylint: disable=missing-class-docstring, redefined-builtin, too-many-arguments
class SnakemakeArgs:
    def __init__(
        self,
        input: List[str],
        output: List[str],
        params: List[str],
        wildcards: List[str],
        threads: str,
        resources: List[str],
        log: str,
    ):
        self.input = _parse_snakemake_arg(Path, input)
        self.output = _parse_snakemake_arg(Path, output)
        self.params = _parse_snakemake_arg(str, params)
        self.wildcards = _parse_snakemake_arg(str, wildcards)
        self.threads = int(threads)
        self.resources = _parse_snakemake_arg(str, resources)
        self.log: Path = Path(log)

    def __eq__(self, obj: object):
        if not isinstance(obj, SnakemakeArgs):
            return False
        if not all(
            [
                obj.input == self.input,
                obj.output == self.output,
                obj.params == self.params,
                obj.wildcards == self.wildcards,
                self.resources == self.resources,
                self.threads == self.threads,
                obj.log == self.log,
            ]
        ):
            return False
        return True


def snakemake_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", nargs="*", default=[])
    parser.add_argument("--output", nargs="*", default=[])
    parser.add_argument("--params", nargs="*", default=[])
    parser.add_argument("--wildcards", nargs="*", default=[])
    parser.add_argument("--threads", nargs="?", default=0, const=0)
    parser.add_argument("--resources", nargs="*", default=[])
    parser.add_argument("--log", nargs="?", default="", const="")
    return parser


def snakemake_args(
    argv: List[str] = None, parser: argparse.ArgumentParser = snakemake_parser()
):
    args = parser.parse_args(argv)
    return SnakemakeArgs(**args.__dict__)
