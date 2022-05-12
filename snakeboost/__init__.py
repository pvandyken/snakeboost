from __future__ import absolute_import
import sys

from colorama import Fore

__submodules__ = ["pipenv", "xvfb", "script", "boost", "tar"]

__ignore__ = ["T"]

# <AUTOGEN_INIT>
from snakeboost.pipenv import (
    PipEnv,
)
from snakeboost.xvfb import (
    XvfbRun,
)
from snakeboost.script import (
    ArgAlias,
    ArgAliasGroup,
    ParseError,
    Pyscript,
    PyscriptParam,
    ScriptDict,
    SnakemakeArgs,
    SnakemakeSequenceArg,
    snakemake_args,
    snakemake_parser,
)
from snakeboost.boost import (
    Boost,
    sh_strict,
)
from snakeboost.tar import (
    Tar,
)

__all__ = [
    "ArgAlias",
    "ArgAliasGroup",
    "Boost",
    "ParseError",
    "PipEnv",
    "Pyscript",
    "PyscriptParam",
    "ScriptDict",
    "SnakemakeArgs",
    "SnakemakeSequenceArg",
    "Tar",
    "XvfbRun",
    "sh_strict",
    "snakemake_args",
    "snakemake_parser",
]

# </AUTOGEN_INIT>

# The Tar module is dependent on python 3.8, so we restrict this module specifically
if sys.version_info.major >= 3 and sys.version_info.minor >= 8:
    from snakeboost.datalad import (  # noqa: F401
        Datalad,
    )

    __all__.append("Datalad")
else:
    print(
        f"{Fore.YELLOW}[WARNING]: Snakeboost has only limited support for Python 3.7. "
        "In particular, the datalad module cannot be used. Please upgrade to python "
        f"3.8 or higher for full functionality.{Fore.RESET}"
    )
