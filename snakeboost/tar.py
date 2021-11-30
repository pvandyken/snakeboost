# noqa: E131
import itertools as it
from pathlib import Path
from typing import Iterable, List, Optional

import attr

from snakeboost.utils import (
    BashWrapper,
    cp_timestamp,
    hash_path,
    rm_if_exists,
    silent_mv,
)

__all__ = ["Tar"]

DEBUG = False

if DEBUG:
    AND = "&&\n"
    OR = "||\n"
else:
    AND = "&&"
    OR = "||"


@attr.frozen
class Tar:
    """Functions to handle manipulation of .tar files in Snakemake

    Supports the creation of new tarfile outputs, the modification of existing tarfiles,
    and the opening of existing tar files as inputs.

    Attributes
    ----------
    root : str
        The directory in which to place the open tarfile directories. Intended to be
        a temporary directory
    """

    _root: Path = attr.ib(converter=Path)
    inputs: Optional[List[str]] = None
    outputs: Optional[List[str]] = None
    modify: Optional[List[str]] = None

    @property
    def root(self):
        return self._root / "__snakemake_tarfiles__"

    def using(
        self,
        inputs: Optional[List[str]] = None,
        outputs: Optional[List[str]] = None,
        modify: Optional[List[str]] = None,
    ):
        """Set inputs, outputs, and modifies for tarring

        Use wildcard inputs and outputs using "{input.foo}" or similar, or any arbitrary
        path, e.g. "{params.atlas}".

        Inputs: Extracts tar file inputs into a directory of your choice. The tar file
        is renamed (with a `.swap` suffix) and a symlink of the same name as the tarfile
        is made to the unpacked directory. Upon completion or failure of the job, the
        symlink is automatically closed.

        Modify: Opens the tarfile as with inputs. Upon successful completion of the job,
        the directory is packaged into a new tarfile, and the old tarfile is deleted.

        Outputs: Creates a new directory symlinked by the name of the tarfile. Upon
        successful completion of the job, the directory is packaged into a tarfile.
        Previous tarfiles produced by the rule will be overwritten, as is usual for
        Snakemake, however an error will be thrown if any `output.swap` is found (e.g.
        `file.tar.gz.out`)

        All files are g-zipped, so `.tar.gz` should be used as the extension for all
        inputs and outputs affected by the function

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
        return self.__class__(self._root, inputs, outputs, modify)

    def __call__(self, cmd: str):
        """Modify shell script to manipulate .tar files as directories

        Parameters
        ----------
        cmd : str
            Command to run

        Returns
        -------
        str
            Modified shell script
        """
        input_scripts = (
            BashWrapper(
                *zip(
                    *(
                        (
                            _open_tar(src, f"{self.root}/{hash_path(src)}"),
                            _close_tar(src),
                            "",
                        )
                        for src in self.inputs  # pylint: disable=not-an-iterable
                    )
                )
            )
            if self.inputs
            else BashWrapper(tuple(), tuple(), tuple())
        )

        # fmt: off
        output_scripts = (BashWrapper(*zip(
            *(
                (
                    f"( [[ ! -e {_stowed(dest)} ]] || ("
                        "echo "
                            '"Found stashed tar file: '
                            f"'{_stowed(dest)}' "
                            "while atempting to generate the output: "
                            f"'{dest}' "
                            "Please rename this file, remove it, or manually change "
                            "its extension back to .tar.gz. If this file should not "
                            "have been processed, you may with to run `snakemake "
                            '--touch` to enforce correct timestamps for files" && '
                        "false"
                    f")) {AND}"
                    f"{rm_if_exists(dest)} {AND} "
                    f"{rm_if_exists(tmpdir, True)} {AND} "
                    f"mkdir -p {tmpdir} {AND} "
                    f"ln -s {tmpdir} {dest}",
                    f"{_save_tar(dest, tmpdir)}",
                    "",
                )
                for dest in self.outputs  # pylint: disable=not-an-iterable
                if ((tmpdir := f"{self.root}/{hash_path(dest)}"))
            )))
            if self.outputs
            else BashWrapper(tuple(), tuple(), tuple())
        )
        # fmt: on

        modify_scripts = (
            BashWrapper(
                *zip(
                    *(
                        (
                            _open_tar(tar, tmpdir),
                            f"{_save_tar(tar, tmpdir)}",
                            _close_tar(tar),
                        )
                        for tar in self.modify  # pylint: disable=not-an-iterable
                        if ((tmpdir := f"{self.root}/{hash_path(tar)}"))
                    )
                )
            )
            if self.modify
            else BashWrapper(tuple(), tuple(), tuple())
        )

        before, success, failure = zip(input_scripts, output_scripts, modify_scripts)

        # pylint: disable=used-before-assignment
        return "".join(
            [
                f"{_join_commands(it.chain(*before))} {AND} ",
                cmd,
                f" {AND} {s} " if (s := _join_commands(it.chain(*success))) else "",
                f" {OR} ({s} && exit 1)"
                if (s := _join_commands(it.chain(*failure)))
                else "",
            ]
        )


def _join_commands(commands: Iterable[str]):
    return f" {AND} ".join(filter(None, commands))


def _open_tar(tarfile: str, mount: str):
    stowed = _stowed(tarfile)

    # fmt: off
    return (
        f"([[ -d {mount} ]] {AND} ("
            f"[[ -e {stowed} ]] || {silent_mv(tarfile, stowed)}"
        f") {OR} ("
            f"mkdir -p {mount} {AND} "
            f"([[ -e {stowed} ]] {AND} ("
                f"echo \"Found stowed tarfile: '{stowed}''. Extracting...\" {AND} "
                f"tar -xzf {stowed} -C {mount} {AND} "
                f"{rm_if_exists(tarfile)}"
            f") {OR} ("
            f"echo \"Extracting and stowing tarfile: '{tarfile}'\" {AND} "
            f"tar -xzf {tarfile} -C {mount} {AND} "
            f"{silent_mv(tarfile, stowed)} "
            "))"
        f")) {AND} "
        f"ln -s {mount} {tarfile} {AND} {cp_timestamp(stowed, tarfile)}"
    )
    # fmt: on


def _close_tar(tarfile: str):
    return f"rm {tarfile} {AND} {silent_mv(_stowed(tarfile), tarfile)}"


def _save_tar(tarfile: str, mount: str):
    return (
        f"rm {tarfile} {AND} "
        f'echo "Packing tar file: {tarfile}" {AND} '
        f"tar -czf {tarfile} -C {mount} . {AND} "
        f"{rm_if_exists(_stowed(tarfile))}"
    )


def _stowed(tarfile: str):
    return tarfile + ".__swap"
