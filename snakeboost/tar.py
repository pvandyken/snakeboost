# noqa: E131
import itertools as it
from typing import Iterable, List, Optional

import attr

from snakeboost.utils import (
    BashWrapper,
    cp_timestamp,
    hash_path,
    rm_if_exists,
    silent_mv,
)


# pylint: disable=too-few-public-methods
@attr.frozen
class Tar:
    """Functions to handle manipulation of .tar files in Snakemake

    Attributes
    ----------
    root : str
        The directory in which to place the open tarfile directories. Intended to be
        a temporary directory
    """

    root: bool

    def __call__(
        self,
        cmd: str,
        inputs: Optional[List[str]] = None,
        outputs: Optional[List[str]] = None,
        modify: Optional[List[str]] = None,
    ):
        """Modify shell script to manipulate .tar files as directories

        Supports the creation of new tarfile outputs, the modification of existing
        tarfiles, and the opening of existing tar files as inputs.

        Can be used on wildcard inputs and outputs using "{input.foo}" or similar, but
        any arbitrary path can be used, e.g. "{params.atlas}".

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
        cmd : str
            Command to run
        inputs : List[str, optional
            List of inputs. Use "{input.foo}" for wildcard paths. By default None
        outputs : List[str], optional
            List of outputs. Use "{output.foo}" for wildcard paths. By default None
        modify : List[str], optional
            List of files to modify. By default None

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
                        for src in inputs
                    )
                )
            )
            if inputs
            else BashWrapper(tuple(), tuple(), tuple())
        )

        output_scripts = (
            BashWrapper(
                *zip(
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
                            ")) && "
                            f"{rm_if_exists(dest)} && "
                            f"{rm_if_exists(tmpdir, True)} && "
                            f"mkdir -p {tmpdir} && "
                            f"ln -s {tmpdir} {dest}",
                            f"{_save_tar(dest, tmpdir)}",
                            "",
                        )
                        for dest in outputs
                        if ((tmpdir := f"{self.root}/{hash_path(dest)}"))
                    )
                )
            )
            if outputs
            else BashWrapper(tuple(), tuple(), tuple())
        )

        modify_scripts = (
            BashWrapper(
                *zip(
                    *(
                        (
                            _open_tar(tar, tmpdir),
                            f"{_save_tar(tar, tmpdir)}",
                            _close_tar(tar),
                        )
                        for tar in modify
                        if ((tmpdir := f"{self.root}/{hash_path(tar)}"))
                    )
                )
            )
            if modify
            else BashWrapper(tuple(), tuple(), tuple())
        )

        before, success, failure = zip(input_scripts, output_scripts, modify_scripts)

        return (
            f"{_join_commands(it.chain(*before))} && "
            f"{cmd} && "
            f"{_join_commands(it.chain(*success))} || "
            f"({_join_commands(it.chain(*failure))} && exit 1)"
        )


def _join_commands(commands: Iterable[str]):
    return " && ".join(filter(None, commands))


def _open_tar(tarfile: str, mount: str):
    stowed = _stowed(tarfile)
    return (
        f"([[ -d {mount} ]] && ( "
        f"[[ -e {stowed} ]] || {silent_mv(tarfile, stowed)}"
        ") || ("
        f"mkdir -p {mount} && "
        f"([[ -e {stowed} ]] && ("
        f"echo \"Found stowed tarfile: '{stowed}''. Extracting...\" && "
        f"tar -xzf {stowed} -C {mount} && "
        f"{rm_if_exists(tarfile)}"
        ") || ("
        f"echo \"Extracting and stowing tarfile: '{tarfile}'\" && "
        f"tar -xzf {tarfile} -C {mount} && "
        f"{silent_mv(tarfile, stowed)} "
        "))"
        ")) && "
        f"ln -s {mount} {tarfile} && {cp_timestamp(stowed, tarfile)}"
    )


def _close_tar(tarfile: str):
    return f"rm {tarfile} && {silent_mv(_stowed(tarfile), tarfile)}"


def _save_tar(tarfile: str, mount: str):
    return (
        f"rm {tarfile} && "
        f'echo "Packing tar file: {tarfile}" && '
        f"tar -czf {tarfile} -C {mount} . && "
        f"{rm_if_exists(_stowed(tarfile))}"
    )


def _stowed(tarfile: str):
    return tarfile + ".__swap"
