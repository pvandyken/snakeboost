import hashlib
import itertools as it
from pathlib import Path
from typing import Iterable, List, Optional, Union

__all__ = ["PipEnv"]


PYTHON_VENV_CREATE_ERR = "[ERROR] (jobid={jobid}): Error creating python environment"
TIMED_OUT_ERR = "[ERROR] (jobid={jobid}): Script timed out when waiting for Python"


def _get_hash(items: Iterable[Iterable[str]]):
    encoded = str(sorted(*it.chain(items))).encode("utf-8")
    return hashlib.md5(encoded).hexdigest()


def _get_file_contents(paths: Iterable[Path]):
    for path in paths:
        with path.open("r", encoding="utf-8") as file:
            yield file.read()


class PipEnv:
    """Functions to handle the creation of pip virtualenvs for Snakemake rules

    Creates a virtualenv in the directory of choice intended for use in Snakemake rules.
    Both packages and requirements.txt files can be specified, and all will be
    installed, first requirements.txt (in the order specified), then packages. The
    virtualenv is stored in a directory under root named according to the hash of the
    package names and the contents of the requirements.txt files. Thus, multiple
    virtualenvs can easily be created, but each venv will not be made more than once.

    Supports thread-safe installation, so multiple jobs depending on the same venv may
    be run simultaneously.

    Parameters
    ----------
    root : Path
        The directory in which to place the virtualenv. Intended to be a temporary
        directory
    flags : str
        Flags to include on every call of `pip install` (e.g. custom wheelhouse paths)
    packages : List[str]
        List of packages to install. Can be any valid pip package identifier (with or
        without version specification)
    requirements : List[str]
        List of paths to requirements.txt files

    Attributes
    ----------
    venv : str
        Path to the venv dir
    bin : str
        Path to the venv bin dir (e.g. venv/bin)
    python_path : str
        Path of the python executable (e.g. venv/bin/python)
    """

    def __init__(
        self,
        root: Union[Path, str],
        flags: str = "",
        packages: Optional[List[str]] = None,
        requirements: Optional[List[str]] = None,
    ):
        requirement_contents: Iterable[str] = (
            _get_file_contents(Path(requirement) for requirement in requirements)
            if requirements
            else []
        )

        self._dir = (
            Path(root)
            / "__snakemake_venvs__"
            / _get_hash(filter(None, [packages, requirement_contents]))
        )
        self.venv = self._dir / "venv"
        self.bin = self.venv / "bin"
        self.python_path = self.venv / "bin" / "python"
        self._flags = flags
        self._packages = " ".join(packages) if packages else ""
        self._requirements = "-r " + " -r ".join(requirements) if requirements else ""

    @property
    def get_venv(self):
        """Script to check for venv, installing if necessary

        This can be embedded at the beginning of a shell script to ensure the existance
        of the venv.

        Typically, this should NOT be used. The class methods provide the same
        functionality and are safer.

        Returns
        -------
        str
            Bash script to look for a venv and create one if necessary
        """
        install_prefix = f"{self.python_path} -m pip install {self._flags}"
        install_cmd = " && ".join(
            filter(
                None,
                [
                    f"{install_prefix} --upgrade pip",
                    f"{install_prefix} {self._requirements}"
                    if self._requirements
                    else "",
                    f"{install_prefix} {self._packages}" if self._packages else "",
                ],
            )
        )
        return (
            f"mkdir -p {self._dir} && ("
            f" echo '[[ -x {self.python_path} ]] ||"
            "("
            f"virtualenv --no-download {self.venv} && "
            f"{install_cmd}"
            ") || ("
            f"echo '\"'\"'{PYTHON_VENV_CREATE_ERR}'\"'\"' 1>&2 && exit 1"
            f")' | flock -w 900 {self._dir} bash "
            ")"
        )

    def python(self, cmd: str):
        """Ensure existance of venv then run python command

        Prepends the path of the python executable to the shell script. This can be used
        to run a python file (with a fully resolved path) or a python module (using the
        `-m` flag).

        When using multiple enhancers, this must ALWAYS be the last one before the
        command.

        Parameters
        ----------
        cmd : str
            Command to run

        Returns
        -------
        str
            Modified shell script
        """
        return f"{self.get_venv} && {self.python_path} {cmd}"

    def script(self, cmd: str):
        """Ensure existance of venv then run python script

        This appends the path of the venv /bin directory to the shell script. The very
        first item in the script should thus be the name of an executable python script
        installed in the /bin dir.

        When using multiple enhancers, this must ALWAYS be the last one before the
        command.

        Parameters
        ----------
        cmd : str
            Command to run

        Returns
        -------
        str
            Modified shell script
        """
        stripped = cmd.strip()
        return self.python(f"{self.venv}/bin/{stripped}")

    def make_venv(self, cmd: str):
        """Ensure of existence of venv and run any arbitrary command

        Parameters
        ----------
        cmd : str
            Command to run

        Returns
        -------
        str
            Modified shell script
        """
        return f"{self.get_venv} && {cmd}"
