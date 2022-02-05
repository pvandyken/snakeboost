# pylint: disable=missing-class-docstring, invalid-name
from __future__ import absolute_import

import textwrap

from snakeboost.bash.cmd import ShSingleCmd
from snakeboost.bash.globals import Globals
from snakeboost.bash.statement import StringLike
from snakeboost.bash.utils import quote_escape


class AwkBlock:
    def __init__(self, *args: str):
        self.statements = args

    def to_str(self):
        return str(self)

    def __str__(self):
        if Globals.DEBUG:
            sep = ";\n"
            wrap = lambda s: f"{{{{\n{textwrap.indent(s, '    ')}\n}}}}"  # noqa: E731
        else:
            sep = "; "
            wrap = lambda s: f"{{{{ {s} }}}}"  # noqa: E731

        body = sep.join(str(statement) for statement in self.statements)
        return f"'{quote_escape(wrap(body))}'"


class awk(ShSingleCmd):
    cmd = "awk"

    def __init__(self, *expr: str):
        super().__init__(AwkBlock(*expr).to_str())

    def v(self, **kwargs: StringLike):
        for name, var in kwargs.items():
            self.args.append(f"-v {name}={var}")
        return self

    def F(self, value: str):
        self.args.append(f"-F'{quote_escape(value)}'")
        return self
