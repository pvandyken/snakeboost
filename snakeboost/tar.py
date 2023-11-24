# noqa: E131
from __future__ import absolute_import
import os

from pathlib import Path
from typing import Callable, Iterable, List, Optional, Union

import attr

from snakeboost.bash import Flock, ShBlock, ShIf, ShVar
from snakeboost.bash.cmd import echo, ls, mkdir
from snakeboost.bash.statement import subsh
from snakeboost.general import BashWrapper, ScriptComp
from snakeboost.utils import get_hash, hash_path, lockfile, rm_if_exists

__all__ = ["Tar"]


def _strip_braces(items: Optional[List[str]]):
    if items is not None:
        return [item.strip(" {}\t\n") for item in items]
    return items


def _get_tar_wrapper(
    files: Optional[Iterable[str]],
    factory: Callable[[str, ShVar], ScriptComp],
    mount: Callable[[str], Union[Path, str]],
):
    mounts = {path: ShVar(mount(f"{{{path}}}")) for path in files or []}

    return BashWrapper(
        comps=tuple(
            attr.evolve(
                factory(f"{{{file}}}", mount),
                assignments=mount,
            )
            for file, mount in mounts.items()
        ),
        subs=mounts,
    )


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
    inputs: Optional[List[str]] = attr.field(default=None, converter=_strip_braces)
    mut_inputs: Optional[List[str]] = attr.field(default=None, converter=_strip_braces)
    outputs: Optional[List[str]] = attr.field(default=None, converter=_strip_braces)
    modify: Optional[List[str]] = attr.field(default=None, converter=_strip_braces)
    dereference: bool = False

    @property
    def hash(self) -> str:
        return get_hash(
            "".join(
                [
                    self._hash_list(self.inputs or []),
                    self._hash_list(self.mut_inputs or []),
                    self._hash_list(self.outputs or []),
                    self._hash_list(self.modify or []),
                ]
            )
        )

    @staticmethod
    def _hash_list(_list: List[str]):
        return get_hash(str(sorted(_list)))

    @property
    def root(self):
        return self._root.resolve() / "__snakemake_tarfiles__"

    @property
    def timestamps(self):
        return self._root.resolve() / "__snakemake_tarfile_timestamps__"

    # pylint: disable=too-many-arguments
    def using(
        self,
        inputs: Optional[List[str]] = None,
        mut_inputs: Optional[List[str]] = None,
        outputs: Optional[List[str]] = None,
        modify: Optional[List[str]] = None,
        dereference: Optional[bool] = None,
    ):
        """Set inputs, outputs, and modifies for tarring, and other settings

        **Setting inputs and outputs**

        Use wildcard inputs and outputs using "{input.foo}" or similar, or any arbitrary
        path, e.g. "{params.atlas}".

        - **Inputs**: Extracts tar file inputs into a directory of your choice. The tar
          file is renamed (with a `.swap` suffix) and a symlink of the same name as the
          tarfile is made to the unpacked directory. Upon completion or failure of the
          job, the symlink is automatically closed. Contents should not be modified; to
          facilitate this, the file permissions within are changed to readonly. The
          untarred folder is cached for future use, so modifications could propogate to
          future work

        - **Mutable Inputs**: Like inputs, but allow modification of the contents. The
          tar file will be deleted upon completetion.

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

        Parameters:
            inputs (List of str):
                List of inputs. Use "{input.foo}" for wildcard paths
            mut_inputs (List of str):
                List of mutable inputs. Use "{input.foo}" for wildcard paths
            outputs (list of str):
                List of outputs. Use "{output.foo}" for wildcard paths
            modify (list of str):
                List of files to modify
            dereference: (optional bool):
                Use the -h flag when saving tar files to dereference all symlinks

        Returns:
            Tar: A fresh Tar instance with the update inputs, outputs, and modifies
        """
        if dereference is None:
            dereference = self.dereference
        return self.__class__(
            self._root, inputs, mut_inputs, outputs, modify, dereference
        )

    def __call__(self, cmd: str, *, signature: bool = False):
        """Modify shell script to manipulate .tar files as directories

        Parameters:
            cmd (str):
                Command to run

        Returns:
            str: Modified shell script
        """
        if signature:
            return self.hash
        return BashWrapper.merge(
            [
                _get_tar_wrapper(
                    files=self.inputs,
                    factory=lambda src, mount: ScriptComp(
                        before=Flock(lockfile(src, self.root), wait=0, error=False).do(
                            _mount_tar(src, mount)
                        ),
                        inner_mod=lambda s: Flock(lockfile(src, self.root), shared=True)
                        .do(f"chmod -R a-w {mount}", s)
                        .to_str(),
                        after=Flock(lockfile(src, self.root), wait=0, error=False).do(
                            f"chmod -R a+w {mount}"
                        ),
                    ),
                    mount=self._public_mount,
                ),
                _get_tar_wrapper(
                    files=self.mut_inputs,
                    factory=lambda src, mount: ScriptComp(
                        before=_mount_tar(src, mount),
                        after=_rm_mount(mount),
                    ),
                    mount=self._private_mount,
                ),
                _get_tar_wrapper(
                    files=self.outputs,
                    factory=lambda dest, mount: ScriptComp(
                        outer_mod=lambda s: self._modification_lock(dest, s),
                        before=_tar_output(mount),
                        success=_save_tar(dest, mount, self.dereference),
                        failure=_rm_mount(mount),
                    ),
                    mount=self._public_mount,
                ),
                _get_tar_wrapper(
                    files=self.modify,
                    factory=lambda tar, mount: ScriptComp(
                        before=_mount_tar(tar, mount),
                        outer_mod=lambda s: self._modification_lock(tar, s),
                        success=_save_tar(tar, mount, self.dereference),
                        failure=_rm_mount(mount),
                    ),
                    mount=self._public_mount,
                ),
            ]
        ).format_script(cmd)

    def _public_mount(self, file: str):
        return (
            os.path.join(self.root, hash_path(file))
            + os.path.sep
            + str(subsh(rf"basename {file} | sed -E 's/\.tar\.gz$//'"))
        )

    def _private_mount(self, file: str):
        filename = subsh(rf"basename {file} | sed -E 's/\.tar\.gz$//'")
        return subsh(
            mkdir(self.root).p,
            f'printf \'%s/%s\' "$(mktemp -d --tmpdir={self.root})" "{filename}"',
        )

    def _modification_lock(self, tarfile: str, script: str):
        return (
            Flock(lockfile(tarfile, self.root), wait=0)
            .do(script)
            .els(
                echo(
                    f"Unable to obtain lock on {tarfile}. Another process must be "
                    "reading or writing from it."
                ),
                "false",
            )
            .to_str()
        )


def _tar_output(mount: ShVar):
    return (
        (ShIf.is_dir(mount) & ShIf.n(ls(mount).A)) >> (f"rm -rf {mount}/*"),
        mkdir(mount).p,
    )


def _save_tar(tarfile: str, mount: ShVar, dereference: bool):
    flags = "-hczf" if dereference else "-czf"
    return (
        echo(f"Packing tar file: {tarfile}"),
        f"tar {flags} {mount}.tar.gz -C {mount} .",
        f"mv {mount}.tar.gz {tarfile}.tmp",
        rm_if_exists(tarfile),
        f"mv {tarfile}.tmp {tarfile}",
    )


def _rm_mount(mount: ShVar):
    return f"rm -rf {mount}"


def _mount_tar(tarfile: str, mount: ShVar):
    cmd = (ShIf.isnt().is_dir(mount) | ShIf.empty(ls(mount).A)).then(
        mkdir(mount).p,
        echo(f"Extracting and stowing tarfile: '{tarfile}'"),
        f"tar -xzf {tarfile} -C {mount}",
    )
    return cmd


if __name__ == "__main__":
    print(
        Tar(Path("/tmp")).using(
            inputs=["{input.data}", "input.atlas"],
            outputs=["{output}"],
        )(
            ShBlock(
                "wm_cluster_remove_outliers.py "
                "-j {threads} "
                "{input.data} {input.atlas} {params.work_folder}",
                "mv "
                "{params.work_folder}/{params.results_subfolder}_outlier_removed/* "
                "{output}/",
            ).to_str()
        )
    )
