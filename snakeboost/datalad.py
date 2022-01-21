# pylint: disable=missing-class-docstring
from __future__ import absolute_import

import functools as ft
import itertools as it
import operator as op
import re
import string
from pathlib import Path
from typing import Iterable, Optional, Tuple

import attr
import more_itertools as itx

from snakeboost.sh_cmd import ShBlock, ShVar, echo, wc
from snakeboost.utils import ShIf, get_replacement_field, resolve, sh_for, split, subsh

__all__ = ["Datalad"]


ParsedFormat = Iterable[Tuple[str, Optional[str], Optional[str], Optional[str]]]


def _filter_input_output_fields(format_parser: ParsedFormat) -> ParsedFormat:
    for literal, field_name, *specifiers in format_parser:
        if field_name and re.match(r"^(input|output)(\..*)?$", field_name):
            yield literal, field_name, *specifiers
            continue
        field_str = get_replacement_field(field_name, *specifiers)
        yield literal + field_str, None, None, None


CLI_FLAGS = {"inputs": "-i", "outputs": "-o"}


@attr.define
class Datalad:
    dataset_root: Path = attr.ib(converter=Path)
    _msg: str = ""

    def using(self, msg: str = None, dataset_root: Path = None):
        """Set message


        Parameters
        ----------
        inputs : List[str], optional
            List of inputs. Use "{input.foo}" for wildcard paths. By default None
        outputs : List[str], optional
            List of outputs. Use "{output.foo}" for wildcard paths. By default None
        modify : List[str], optional
            List of files to modify. By default None

        Returns
        -------
        Tar
            A fresh Tar instance with the update inputs, outputs, and modifies
        """
        return self.__class__(
            **{
                "msg": msg if msg else self._msg,
                "dataset_root": dataset_root if dataset_root else self.dataset_root,
            }
        )

    def msg(self, msg: str):
        return self.using(msg=msg)

    def __call__(self, cmd: str):
        _, field_name, *field_components = zip(
            *_filter_input_output_fields(string.Formatter().parse(cmd))
        )

        io_type = ft.partial(re.sub, r"^(input|output).*$", r"\1s")

        # Sort the field components into inputs and outputs
        sorted_fields = {
            # 6. Remove empty fields and group under "inputs" or "outputs"
            io_type(label): [
                *filter(
                    None,
                    # 5. Remove all duplicates
                    itx.unique_everseen(
                        # 4. Convert field components into {string:form}
                        get_replacement_field(*component)
                        for component in field_component
                    ),
                )
            ]
            for label, field_component in it.groupby(
                sorted(
                    # 1. Remove all empty fields
                    filter(
                        lambda x: x[0] is not None, zip(field_name, *field_components)
                    ),
                    # 2. Sort by field name
                    key=op.itemgetter(0),
                ),
                # 3. Group by field name
                key=op.itemgetter(0),
            )
        }

        file_list = {
            key: " ".join(
                subsh(
                    # Loop through the field in case it evaluates to a list of space
                    # separated paths (e.g. in the case of {input} -> /path/1 /path/2
                    # etc)
                    sh_for(
                        _path := ShVar("path"),
                        _in=split(field),
                        do=(
                            ShIf(
                                f"{resolve(_path)} =~ "
                                f"{resolve(self.dataset_root)}/(.*?/)*?.git/.+"
                            )
                            .then(
                                # For each p within the root directory, echo p preceded
                                # by the appropriate datalad flag (-i or -o)
                                f'echo -n " {resolve(_path)}"'
                            )
                            .fi()
                        ),
                    )
                )
                for field in value
            )
            for key, value in sorted_fields.items()
        }

        # msg = f"-m '{quote_escape(self._msg)}'" if self._msg else ""
        cli_args = f"-d {resolve(self.dataset_root)} -r"

        return ShBlock(
            (
                (inputs := ShVar("inputs")).set(
                    file_list["inputs"] if "inputs" in file_list else '""'
                ),
                (outputs := ShVar("outputs")).set(
                    file_list["outputs"] if "outputs" in file_list else '""'
                ),
                ShIf(echo(inputs).n() | wc().l())
                .gt("0")
                .then(f"datalad get {cli_args} {inputs}")
                .fi(),
                ShIf(echo(outputs).n() | wc().l())
                .gt("0")
                .then(f"datalad unlock {cli_args} {outputs}; ")
                .fi(),
            ),
            cmd,
        )


if __name__ == "__main__":
    print(Datalad(Path("/path/to/root"))("echo {input}"))
