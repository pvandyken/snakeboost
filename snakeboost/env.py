from __future__ import absolute_import

import itertools as it
import operator as op
from typing import Dict

import attrs

from snakeboost.bash.statement import ShEntity, ShVar
from snakeboost.general import BashWrapper, ScriptComp
from snakeboost.utils import get_hash


# pylint: disable=missing-class-docstring
@attrs.frozen
class Env:
    _tracked: Dict[str, ShEntity] = {}
    _untracked: Dict[str, ShEntity] = {}
    _export: bool = False

    def export(self, **items: ShEntity):
        return attrs.evolve(self, export=True, untracked=items)

    @property
    def hash(self) -> str:
        if self._tracked:
            sort = sorted(self._tracked.items(), key=op.itemgetter(0))
            return get_hash("".join([key + str(val) for key, val in sort]))
        return ""

    def __call__(self, script: str, *, signature: bool = False, log: bool = False):
        if signature:
            return self.hash
        if log:
            return self(script)

        envvars = {
            name: ShVar(value=val, name=name, export=self._export)
            for name, val in it.chain(self._tracked.items(), self._untracked.items())
        }

        return BashWrapper(
            (ScriptComp(assignments=envvars.values()),),
            subs={f"sb_env.{name}": var for name, var in envvars.items()},
        ).format_script(script)
