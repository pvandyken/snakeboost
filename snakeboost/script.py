from __future__ import absolute_import

import argparse
import re
from pathlib import Path
from typing import Callable, Dict, List, Optional, TypeVar, Union

from snakeboost.pipenv import PipEnv


def _get_arg(arg: str, value: Optional[List[str]]):
    if value is None:
        return f"--{arg} {{{arg}}}"
    return f"--{arg} " + " ".join([f"{v}={{{arg}.{v}}}" for v in value])


# pylint: disable=too-many-arguments, redefined-builtin, missing-class-docstring
def pyscript(
    script: str,
    env: PipEnv = None,
    input: List[str] = None,
    output: List[str] = None,
    params: List[str] = None,
    wildcards: List[str] = None,
    resources: List[str] = None,
    log: List[str] = None,
):
    if not Path(script).exists():
        raise FileExistsError(
            f"Could not find script: {script}\n"
            "Be sure to define paths relative to the app root, not the workflow root."
        )
    if env is None:
        executable = "python"
    else:
        executable = f"{env.get_venv} && {env.python_path}"
    args = " ".join(
        [
            _get_arg(arg, value)
            for arg, value in {
                "input": input,
                "output": output,
                "params": params,
                "wildcards": wildcards,
                "resources": resources,
                "log": log,
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
    parser.add_argument("--threads", nargs="?", default="")
    parser.add_argument("--resources", nargs="*", default=[])
    parser.add_argument("--log", nargs="?", default="")
    return parser


def snakemake_args(
    argv: List[str] = None, parser: argparse.ArgumentParser = snakemake_parser()
):
    args = parser.parse_args(argv)
    return SnakemakeArgs(**args.__dict__)
