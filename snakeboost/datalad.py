# pylint: disable=missing-class-docstring
from __future__ import absolute_import

import functools as ft
import itertools as it
import re
import string
from pathlib import Path
from typing import Iterable, Optional, Tuple

import attr
import more_itertools as itx

from snakeboost.bash.cmd import echo
from snakeboost.bash.statement import Flock, ShBlock, ShFor, ShIf, ShVar, subsh
from snakeboost.utils import get_replacement_field, resolve, split

__all__ = ["Datalad"]


ParsedFormat = Tuple[str, Optional[str], Optional[str], Optional[str]]


def _filter_input_output_fields(
    format_parser: Iterable[ParsedFormat],
) -> Iterable[ParsedFormat]:
    for literal, field_name, *specifiers in format_parser:
        if field_name and re.match(r"^(input|output)(\..*)?$", field_name):
            yield literal, field_name, *specifiers
            continue
        field_str = get_replacement_field(field_name, *specifiers)
        yield literal + field_str, None, None, None


def _get_field_category(field: Tuple[str, Optional[str], Optional[str]]) -> str:
    assert (category := re.search(r"^(input|output)", field[0]))
    return category[1]


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
                    key=_get_field_category,
                ),
                # 3. Group by field name
                key=_get_field_category,
            )
        }

        file_list = {
            key: (
                # Loop through the field in case it evaluates to a list of space
                # separated paths (e.g. in the case of {input} -> /path/1 /path/2
                # etc)
                ShFor(
                    _path := ShVar(),
                    _in=split(" ".join(field for field in value)),
                )
                >> (
                    ShIf(
                        subsh(f"readlink -m {_path} || echo -n ''")
                        + f" =~ {resolve(self.dataset_root)}/(.*?/)*?.git/.+"
                    )
                    >> (
                        # For each p within the root directory, echo p preceded
                        # by the appropriate datalad flag (-i or -o)
                        echo(f" {resolve(_path, True)}").n()
                    ),
                )
            )
            for key, value in sorted_fields.items()
        }

        # msg = f"-m '{quote_escape(self._msg)}'" if self._msg else ""
        cli_args = f"-d {resolve(self.dataset_root)} -r"

        # fmt: off
        return ShBlock(
            (
                inputs := ShVar(
                    file_list["inputs"] if "inputs" in file_list else '""',
                    export=True
                ),
                outputs := ShVar(
                    file_list["outputs"] if "outputs" in file_list else '""',
                    export=True
                ),
                Flock(self.dataset_root, wait=900).do(
                    ShIf.not_empty(inputs) >> (
                        f"git -C {resolve(self.dataset_root)} annex get {inputs}"
                    ),
                    ShIf.not_empty(outputs) >> f"datalad unlock {cli_args} {outputs}",
                ),
            ),
            cmd,
        ).to_str()
        # fmt: on


if __name__ == "__main__":
    pass
