# noqa: E131
from __future__ import absolute_import

from pathlib import Path
from typing import Callable, Iterable, List, Optional, Tuple

import attr
import more_itertools as itx

from snakeboost.bash import (
    BashWrapper,
    Flock,
    ShBlock,
    ShEntity,
    ShIf,
    ShTry,
    ShVar,
    StringLike,
)
from snakeboost.bash.cmd import cat, echo, find, mkdir
from snakeboost.utils import cp_timestamp, hash_path, rm_if_exists, silent_mv

__all__ = ["Tar"]


@attr.frozen
class Tar:
    """Functions to handle manipulation of .tar files in Snakemake

    Supports the creation of new tarfile outputs, the modification of existing tarfiles,
    and the opening of existing tar files as inputs.

    Attributes:
        root (Path or str):
            The directory in which to place the open tarfile directories. Intended to be
            a temporary directory
    """

    _root: Path = attr.ib(converter=Path)
    inputs: Optional[List[str]] = None
    outputs: Optional[List[str]] = None
    modify: Optional[List[str]] = None
    clear_mounts: Optional[bool] = None

    @property
    def root(self):
        return self._root.resolve() / "__snakemake_tarfiles__"

    @property
    def timestamps(self):
        return self._root.resolve() / "__snakemake_tarfile_timestamps__"

    def using(
        self,
        inputs: Optional[List[str]] = None,
        outputs: Optional[List[str]] = None,
        modify: Optional[List[str]] = None,
        clear_mounts: bool = None,
    ):
        """Set inputs, outputs, and modifies for tarring, and other settings

        **Setting inputs and outputs**

        Use wildcard inputs and outputs using "{input.foo}" or similar, or any arbitrary
        path, e.g. "{params.atlas}".

        - **Inputs**: Extracts tar file inputs into a directory of your choice. The tar
          file is renamed (with a `.swap` suffix) and a symlink of the same name as the
          tarfile is made to the unpacked directory. Upon completion or failure of the
          job, the symlink is automatically closed.

        - **Modify**: Opens the tarfile as with inputs. Upon successful completion of
          the job, the directory is packaged into a new tarfile, and the old tarfile is
          deleted.

        - **Outputs**: Creates a new directory symlinked by the name of the tarfile.
          Upon successful completion of the job, the directory is packaged into a
          tarfile. Previous tarfiles produced by the rule will be overwritten, as is
          usual for Snakemake, however an error will be thrown if any `output.swap` is
          found (e.g. `file.tar.gz.out`)

        All files are g-zipped, so `.tar.gz` should be used as the extension for all
        inputs and outputs affected by the function

        **Clearing mounts**

        Tar typically does not delete any extracted tarfile contents. This way, if
        multiple rules use the same input tarball, the file only needs to be unpackked
        once. A problem occurs, however, when one of those rules modifies the unpacked
        contents. Because the other rules read the same unpacked contents, the
        modifications will be propogated to all following rules, which is likely not
        desired. Thus, when closing an input tar file, Tar will check if the unpacked
        contents have been modified in any way. If modifications are found, the mount
        will be cleared, forcing future rules to unpack a fresh instance of the input
        tarball.

        Checking for modifications may take a considerable amount of time on very large
        directories. In such cases, you may wish to manually set `clear_mounts`. True
        will force the clearing of input tarball mounts, and False will disable
        clearing. Note that you should never disable clearing to purposefully allow
        modifications made by one rule to propogate to another rule, as this can lead to
        inconsistent behaviour. Instead, save any modifications to a new tarball using
        `output` or save your modifications to the existing tarball using `modify`.

        Parameters:
            inputs (List of str):
                List of inputs. Use "{input.foo}" for wildcard paths
            outputs (list of str):
                List of outputs. Use "{output.foo}" for wildcard paths
            modify (list of str):
                List of files to modify
            clear_mounts: (optional bool):
                Force the deletion or preservation of tar directories following rule
                completion

        Returns:
            Tar: A fresh Tar instance with the update inputs, outputs, and modifies
        """
        if self.clear_mounts is not None:
            clear_mounts = self.clear_mounts
        return self.__class__(self._root, inputs, outputs, modify, clear_mounts)

    def __call__(self, cmd: str):
        """Modify shell script to manipulate .tar files as directories

        Parameters:
            cmd (str):
                Command to run

        Returns:
            str: Modified shell script
        """
        input_scripts = _get_bash_wrapper(
            self.inputs,
            lambda src: (
                self._open_tar(src),
                self._close_tar(src),
                self._close_tar(src),
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
                self._open_tar(tar),
                _save_tar(tar, self._get_mount_dir(tar)),
                self._close_tar(tar),
            ),
        )

        before, success, failure = zip(input_scripts, output_scripts, modify_scripts)
        # fmt: off
        lockfile = (
            [*filter(None, [self.inputs, self.outputs, self.modify])][0][0] + ".lock"
        )
        # fmt: on

        return ShBlock(
            Flock(lockfile, wait=0).do(
                ShBlock(*itx.flatten(before)),
                ShTry(cmd)
                .catch(*itx.flatten(failure), "false")
                .els(*itx.flatten(success)),
            ),
            Flock(lockfile, wait=0, abort=True).do(f"rm {lockfile}") + " || :",
        ).to_str()

    def _get_mount_dir(self, dest):
        return Path(self.root, hash_path(dest))

    def _get_timestamp_file(self, dest):
        return Path(self.timestamps, hash_path(dest))

    def _open_tar(self, tarfile: str):
        stowed = _stowed(tarfile)
        fhash = ShVar(hash_path(tarfile))
        mount = Path(self.root, str(fhash))
        timestamp = Path(self.timestamps, str(fhash))

        clear_mounts = (
            (
                mkdir(self.timestamps).p,
                _timestamp_hash(mount).to_str() + f" >| {timestamp}",
            )
            if self.clear_mounts is None
            else ""
        )

        return (
            fhash,
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
            *clear_mounts,
        )

    def _close_tar(self, tarfile: str):
        fhash = ShVar(hash_path(tarfile))
        mount = Path(self.root, str(fhash))
        timestamp = Path(self.timestamps, str(fhash))
        if self.clear_mounts:
            clear_mounts = f"rm -rf {mount}"
        elif self.clear_mounts is None:
            clear_mounts = ShIf(_timestamp_hash(mount)).ne(cat(timestamp)) >> (
                f"rm -rf {mount}"
            )
        else:
            clear_mounts = ""
        return (
            fhash,
            f"rm {tarfile}",
            silent_mv(_stowed(tarfile), tarfile),
            clear_mounts,
        )


def _get_bash_wrapper(
    files: Optional[Iterable[str]],
    factory: Callable[[str], Tuple[ShEntity, ShEntity, ShEntity]],
):
    return (
        BashWrapper(*zip(*(factory(file) for file in files)))
        if files
        else BashWrapper(tuple(), tuple(), tuple())
    )


def _timestamp_hash(directory: Path):
    return find(directory, r"-exec date -r {{}} '+%m%d%Y%H%M%S' \;") | "md5sum"


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


def _save_tar(tarfile: str, mount: Path):
    return (
        f"rm {tarfile}",
        echo(f"Packing tar file: {tarfile}"),
        f"tar -czf {tarfile} -C {mount} .",
        rm_if_exists(_stowed(tarfile)),
    )


def _stowed(tarfile: str):
    return tarfile + ".swp"


if __name__ == "__main__":
    print(
        Tar(Path("/tmp")).using(
            inputs=["{input.data}"], outputs=["{output}"], clear_mounts=False
        )(
            (
                "wm_cluster_remove_outliers.py "
                "-j {threads} "
                "{input.data} {input.atlas} {params.work_folder} && "
                "mv "
                "{params.work_folder}/{params.results_subfolder}_outlier_removed/* "
                "{output}/"
            )
        )
    )
