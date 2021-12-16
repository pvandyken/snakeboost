from __future__ import absolute_import
import sys

from colorama import Fore

__submodules__ = ["pipenv", "xvfb", "utils", "script"]

__ignore__ = ["T"]

# <AUTOGEN_INIT>
from snakeboost.pipenv import (
    PipEnv,
)
from snakeboost.xvfb import (
    XvfbRun,
)
from snakeboost.utils import (
    pipe,
)
from snakeboost.script import (
    ParseError,
    Pyscript,
    PyscriptParam,
    ScriptDict,
    SnakemakeArgs,
    SnakemakeSequenceArg,
    snakemake_args,
    snakemake_parser,
)

__all__ = [
    "ParseError",
    "PipEnv",
    "Pyscript",
    "PyscriptParam",
    "ScriptDict",
    "SnakemakeArgs",
    "SnakemakeSequenceArg",
    "XvfbRun",
    "pipe",
    "snakemake_args",
    "snakemake_parser",
]

# </AUTOGEN_INIT>

# The Tar module is dependent on python 3.8, so we restrict this module specifically
if sys.version_info.major >= 3 and sys.version_info.minor >= 8:
    from snakeboost.tar import (  # noqa: F401
        Tar,
    )

    __all__.append("Tar")
else:
    print(
        f"{Fore.YELLOW}[WARNING]: Snakeboost has only limited support for Python 3.7. "
        "In particular, the tar module cannot be used. Please upgrade to python 3.8 or "
        f"higher for full functionality.{Fore.RESET}"
    )
