from __future__ import absolute_import

import argparse
import re
from collections import UserDict
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, TypeVar, Union


def _mapping(arg: str, values: Iterable[str]):
    return " ".join([f"{v}={{{arg}.{v}}}" for v in values])


# pylint: disable=missing-class-docstring
class ScriptDict(UserDict):
    def cli_mapping(self, arg: str):
        return _mapping(arg, self.keys())


PyscriptParam = Union[List[str], ScriptDict, Dict[str, str]]


def _get_arg(arg: str, value: Optional[PyscriptParam]):
    if value is None:
        return f"--{arg} {{{arg}}}"
    if isinstance(value, ScriptDict):
        return f"--{arg} {value.cli_mapping(arg)}"
    if isinstance(value, dict):
        return f"--{arg} " + " ".join(f"{key}={v}" for key, v in value.items())
    return f"--{arg} {_mapping(arg, value)}"


# pylint: disable=redefined-builtin, attribute-defined-outside-init
# pylint: disable=too-many-instance-attributes
class Pyscript:
    """Functions to run python scripts

    Runs python scripts similarly to the script directive in Snakemake, but can be used
    with Snakeboost `PipEnv`s. Like the script directive, inputs, outputs, params, and
    any other Snakemake data can be passed to the script.

    Pyscript can be combined with any other snakeboost function. It should take the
    place of the bash script. It can also be combined with Pipenv by wrapping it with
    the Pipenv.script() function.

    Currently, only items serializable as strings can be provided. This includes text,
    numbers, Paths, etc. Complex objects may be supported in the future.

    The data will be provided to the script via SnakemakeArgs.

    Example:
        To preserve named data, such as:

        ```
        input:
            first="/path/to/first",
            second="/path/to/second"
        ```

        annotations must be provided. There are two methods for this. The first is to
        provide the names of data when calling the script. See the __call__() method for
        more details. The second is to annotate each type of data when defining it in
        the rule using the corresponding Pyscript method. For example:

        ```
        pyscript = Pyscript(snakemake_dir)
        rule rule_name:
            input:
                **pyscript.input(
                    first="/path/to/first",
                    second="/path/to/second"
                )
            shell:
                pyscript("scripts/script_to_run.py")
        ```

        Here, the two inputs would be passed to the script under the names "first" and
        "second". Note that the double asterisk (**) is NECESSARY to properly unpack the
        dict returned by the method.

    Parameters:
        snakefile_dir (Path or str):
            Path to the snakemake app directory or Snakefile directory. This, combined
            with the script path provided later, should form a fully resolved path to
            the script, e.g. snakefile_dir/script_path.py

        python_path (Path or str):
            python executable with which to call the script
    """

    def __init__(
        self, snakefile_dir: Union[str, Path], *, python_path: Union[str, Path] = None
    ):
        self.snakefile_dir = Path(snakefile_dir)
        self.python_path = Path(python_path) if python_path else None
        self._input = None
        self._output = None
        self._params = None
        self._resources = None
        self._wildcards = None
        self._log = None

    def input(self, **kwargs):
        """Set named inputs to the pyscript

        Wrap this function around your rule inputs. Be sure to include a double
        asterisk before the function to unpack the dict, e.g. `**pyscript.input(...)`

        Returns:
            Dict: Dict of name, value pairs. This should be unpacked using a double
                asterisk
        """
        self._input = ScriptDict(**kwargs)
        return kwargs

    def output(self, **kwargs):
        """Set named outputs to the pyscript

        Wrap this function around your rule outputs. Be sure to include a double
        asterisk before the function to unpack the dict, e.g. `**pyscript.output(...)`

        Returns:
            Dict: Dict of name, value pairs. This should be unpacked using a double
                asterisk
        """
        self._output = ScriptDict(**kwargs)
        return kwargs

    def params(self, **kwargs):
        """Set named params to the pyscript

        Wrap this function around your rule params. Be sure to include a double
        asterisk before the function to unpack the dict, e.g. `**pyscript.params(...)`

        Returns:
            Dict: Dict of name, value pairs. This should be unpacked using a double
                asterisk
        """
        self._params = ScriptDict(**kwargs)
        return kwargs

    def resources(self, **kwargs):
        """Set named resources to the pyscript

        Wrap this function around your rule resources. Be sure to include a double
        asterisk before the function to unpack the dict, e.g.
        `**pyscript.resources(...)`

        Returns:
            Dict: Dict of name, value pairs. This should be unpacked using a double
            asterisk
        """
        self._resources = ScriptDict(**kwargs)
        return kwargs

    def wildcards(self, **kwargs):
        """Set named wildcards to the pyscript

        Wrap this function around your rule wildcards. Be sure to include a double
        asterisk before the function to unpack the dict, e.g.
        `**pyscript.wildcards(...)`

        Returns:
            Dict: Dict of name, value pairs. This should be unpacked using a double
                asterisk
        """
        self._wildcards = ScriptDict(**kwargs)
        return kwargs

    def log(self, **kwargs):
        """Set named logs to the pyscript

        Wrap this function around your rule logs. Be sure to include a double
        asterisk before the function to unpack the dict, e.g. `**pyscript.log(...)`

        Returns:
            Dict: Dict of name, value pairs. This should be unpacked using a double
                asterisk
        """
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
        """Generate bash command to call python script.

        Any data passed to the function will be passed to the script under the
        appropriate variable names. Data names can also be provided here using the
        parameters. Each parameter takes a list of variable names associated with the
        data type. For example, if there are three params: x, y, and z, the params
        argument here could be set to ["x", "z"]. This would cause x and z to be passed
        to the script. These arguments take precedence over data passed through the
        Pyscript methods.

        Any data types not annotated via Pyscript methods or call parameters will be
        passed to the script as a List.

        Parameters:
            script (str):
                Path of the script to run. This, when combined with the snakemake_dir
                provided to Pyscript, should form a fully resolved path to the script.
            input (List of str)
            output (List of str)
            params (List of str)
            wildcards (List of str)
            resources (List of str)
            log (List of str)

        Returns:
            str: Bash command to be passed to the snakemake shell directive

        Raises:
            FileExistsError: Raised if the specified script does not exist
        """
        resolved_script = (self.snakefile_dir / script).resolve()

        if not Path(resolved_script).exists():
            raise FileExistsError(
                f"Could not find script: {script}\n"
                "Be sure to define paths relative to the app root, not the workflow "
                "root."
            )
        if self.python_path is None:
            executable = "python"
        else:
            executable = self.python_path
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

        return f"{executable} {resolved_script} {args} --threads {{threads}}"


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


# pylint: disable=redefined-builtin, too-many-arguments
class SnakemakeArgs:
    """Class organizing the data passed from snakemake

    This contains all the data, including inputs, outputs, params, etc, passed from
    the Snakemake rule calling the script.

    This class should not be initialized directly, but should be created through the
    snakemake_args function

    Attributes
    ----------
    input: List or Dict of paths
    output: List or Dict of paths
    params: List or Dict of str
    wildcards : List or Dict of str
    threads : int
    resources : List or Dict of str
    log : List or Dict of paths
    """

    def __init__(
        self,
        input: List[str],
        output: List[str],
        params: List[str],
        wildcards: List[str],
        threads: str,
        resources: List[str],
        log: List[str],
    ):
        self.input = _parse_snakemake_arg(Path, input)
        self.output = _parse_snakemake_arg(Path, output)
        self.params = _parse_snakemake_arg(str, params)
        self.wildcards = _parse_snakemake_arg(str, wildcards)
        self.threads = int(threads)
        self.resources = _parse_snakemake_arg(str, resources)
        self.log = _parse_snakemake_arg(Path, log)

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
    """Parser for snakemake args

    Returns
    -------
    Argument Parser
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", nargs="*", default=[])
    parser.add_argument("--output", nargs="*", default=[])
    parser.add_argument("--params", nargs="*", default=[])
    parser.add_argument("--wildcards", nargs="*", default=[])
    parser.add_argument("--threads", nargs="?", default=0, const=0)
    parser.add_argument("--resources", nargs="*", default=[])
    parser.add_argument("--log", nargs="*", default=[])
    return parser


ArgAlias = Union[List[str], Dict[str, str]]


def snakemake_args(
    argv: List[str] = None,
    parser: argparse.ArgumentParser = snakemake_parser(),
    input: ArgAlias = None,
    output: ArgAlias = None,
    params: ArgAlias = None,
    wildcards: ArgAlias = None,
    resources: ArgAlias = None,
    log: ArgAlias = None,
):
    """Snakemake args passed from snakemake rule

    Parses the command line call made by Pyscript and returns an instance of
    SnakemakeArgs for consumption in a python script.

    Parameters
    ----------
    argv : List[str], optional
        List of arguments to parse. Uses sys.argv[1:] by default
    parser : argparse.ArgumentParser, optional
        Argument parser to use. By default, uses the preconstructed snakemake_args
        parser. This should be suitable for most applications.

    Returns
    -------
    SnakemakeArgs
    """
    alias_cats = dict(
        input=input or [],
        output=output or [],
        params=params or [],
        wildcards=wildcards or [],
        resources=resources or [],
        log=log or [],
    )
    for aliases in alias_cats.values():
        _add_arg_aliases(aliases, parser)
    args = parser.parse_args(argv)
    parsed = args.__dict__
    for alias_cat, aliases in alias_cats.items():
        parsed_alias = _parse_arg_alias(args, aliases)
        parsed[alias_cat].extend(parsed_alias)
    parsed = {k: v for k, v in parsed.items() if k in [*alias_cats, "threads"]}
    return SnakemakeArgs(**parsed)


def _add_arg_aliases(aliases: ArgAlias, parser: argparse.ArgumentParser):
    if isinstance(aliases, dict):
        for alias in aliases.values():
            parser.add_argument(alias, nargs="?", default=[])
    if isinstance(aliases, list):
        for alias in aliases:
            parser.add_argument(alias, nargs="?", default=[])


def _parse_arg_alias(namespace: argparse.Namespace, aliases: ArgAlias):
    if isinstance(aliases, dict):
        for name, alias in aliases.items():
            arg = _get_arg_from_namespace(namespace, alias)
            if arg:
                yield f"{name}={arg}"
    if isinstance(aliases, list):
        for alias in aliases:
            yield _get_arg_from_namespace(namespace, alias)


def _get_arg_from_namespace(namespace: argparse.Namespace, arg_name: str):
    attr = re.sub(r"\-", "_", re.sub(r"^(--(?=[^-])|-(?=[^-]))", "", arg_name))
    return getattr(namespace, attr)


if __name__ == "__main__":
    print(
        snakemake_args(
            argv=["--pos-1", "me", "--input", "hello=world"], input={"dodge": "--pos-1"}
        ).input
    )
