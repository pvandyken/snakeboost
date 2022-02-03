# noqa: E131
from __future__ import absolute_import

from pathlib import Path
from typing import Callable, Iterable, List, Optional, Tuple

import attr
import more_itertools as itx

from snakeboost.bash.cmd import ShBlock, ShEntity, StringLike, echo, mkdir
from snakeboost.bash.statement import BashWrapper, ShIf, ShTry
from snakeboost.utils import cp_timestamp, hash_path, rm_if_exists, silent_mv

__all__ = ["Tar"]


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
        input_scripts = _get_bash_wrapper(
            self.inputs,
            lambda src: (
                _open_tar(src, self._get_mount_dir(src)),
                _close_tar(src),
                _close_tar(src),
            ),
        )

        output_scripts = _get_bash_wrapper(
            self.outputs,
            lambda dest: (
                _open_output_tar(dest, self._get_mount_dir(dest)),
                _save_tar(dest, self._get_mount_dir(dest)),
                "",
            ),
        )

        modify_scripts = _get_bash_wrapper(
            self.modify,
            lambda tar: (
                _open_tar(tar, self._get_mount_dir(tar)),
                _save_tar(tar, self._get_mount_dir(tar)),
                _close_tar(tar),
            ),
        )

        before, success, failure = zip(input_scripts, output_scripts, modify_scripts)

        return ShBlock(
            ShBlock(*itx.flatten(before)),
            ShTry(cmd).catch(*itx.flatten(failure), "false").els(*itx.flatten(success)),
        ).to_str()

    def _get_mount_dir(self, dest):
        return Path(self.root, hash_path(dest))


def _get_bash_wrapper(
    files: Optional[Iterable[str]],
    factory: Callable[[str], Tuple[ShEntity, ShEntity, ShEntity]],
):
    return (
        BashWrapper(*zip(*(factory(file) for file in files)))
        if files
        else BashWrapper(tuple(), tuple(), tuple())
    )


def _open_tar(tarfile: str, mount: Path):
    stowed = _stowed(tarfile)
    return ShBlock(
        ShIf.is_dir(mount)
        >> (
            ShIf.exists(stowed)
            >> (rm_if_exists(tarfile))
            >> (silent_mv(tarfile, stowed))
        )
        >> (
            mkdir(mount).p,
            ShIf.exists(stowed)
            >> (
                echo(f"Found stowed tarfile: '{stowed}'. Extracting..."),
                f"tar -xzf {stowed} -C {mount}",
                rm_if_exists(tarfile),
            )
            >> (
                echo(f"Extracting and stowing tarfile: '{tarfile}'"),
                f"tar -xzf {tarfile} -C {mount}",
                silent_mv(tarfile, stowed),
            ),
        ),
        f"ln -s {mount} {tarfile}",
        cp_timestamp(stowed, tarfile),
    )


def _open_output_tar(tarfile: str, mount_dir: StringLike):
    return (
        ShIf.e(_stowed(tarfile))
        >> (
            echo(
                f"Found stashed tar file: '{_stowed(tarfile)}' while "
                f"atempting to generate the output: '{tarfile}'. Please "
                "rename this file, remove it, or manually change its "
                "extension back to .tar.gz. If this file should not "
                "have been processed, you may with to run ``snakemake "
                "--touch`` to enforce correct timestamps for files."
            ),
            "false",
        ),
        rm_if_exists(tarfile),
        rm_if_exists(mount_dir, True),
        mkdir(mount_dir).p,
        f"ln -s {mount_dir} {tarfile}",
    )


def _close_tar(tarfile: str):
    return (f"rm {tarfile}", silent_mv(_stowed(tarfile), tarfile))


def _save_tar(tarfile: str, mount: Path):
    return (
        f"rm {tarfile}",
        echo(f"Packing tar file: {tarfile}"),
        f"tar -czf {tarfile} -C {mount} .",
        rm_if_exists(_stowed(tarfile)),
    )


def _stowed(tarfile: str):
    return tarfile + ".swp"


# if __name__ == "__main__":
#     tar = Tar(Path("/tmp")).using(inputs = ["{input.data}"], outputs = ["{output}"])(
#         (
# "wm_cluster_remove_outliers.py "
# "-j {threads} "
# "{input.data} {input.atlas} {params.work_folder} && "

# "mv "
# "{params.work_folder}/{params.results_subfolder}_outlier_removed/* {output}/"
#         )
#     )
#     print(tar)
