from __future__ import absolute_import

import itertools as it
import operator as op
from typing import Dict

import attrs

from snakeboost.bash.statement import ShEntity, ShVar
from snakeboost.general import BashWrapper, Enhancer, ScriptComp
from snakeboost.utils import get_hash


# pylint: disable=missing-class-docstring
@attrs.frozen
class Env(Enhancer):
    _tracked: Dict[str, ShEntity] = {}
    _untracked: Dict[str, ShEntity] = {}
    _export: bool = False

    def tracked(self, **items: ShEntity):
        return attrs.evolve(self, tracked=items)

    def untracked(self, **items: ShEntity):
        return attrs.evolve(self, untracked=items)

    def log_format(self, script: str):
        return self(script)

    @property
    def export(self):
        return attrs.evolve(self, export=True)

    @property
    def hash(self) -> str:
        if self._tracked:
            sort = sorted(self._tracked.items(), key=op.itemgetter(0))
            return get_hash("".join([key + str(val) for key, val in sort]))
        return ""

    def __call__(self, script: str):
        envvars = {
            name: ShVar(value=val, name=name, export=self._export)
            for name, val in it.chain(self._tracked.items(), self._untracked.items())
        }

        return BashWrapper(
            (ScriptComp(assignments=envvars.values()),),
            subs={f"sb_env.{name}": var for name, var in envvars.items()},
        ).format_script(script)
