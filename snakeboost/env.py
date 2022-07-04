from __future__ import absolute_import

import itertools as it
from typing import Dict

import attrs

from snakeboost.bash.statement import ShEntity, ShVar
from snakeboost.general import BashWrapper, Enhancer, ScriptComp


# pylint: disable=missing-class-docstring
@attrs.frozen
class Env(Enhancer):
    _tracked: Dict[str, ShEntity] = {}
    _untracked: Dict[str, ShEntity] = {}

    def tracked(self, **items: ShEntity):
        return attrs.evolve(self, tracked=items)

    def untracked(self, **items: ShEntity):
        return attrs.evolve(self, untraced=items)

    def log_format(self, script: str):
        return self(script)

    def __call__(self, script: str):
        envvars = {
            name: ShVar(value=val, name=name)
            for name, val in it.chain(self._tracked.items(), self._untracked.items())
        }

        return BashWrapper(
            (ScriptComp(assignments=envvars.values()),),
            subs={f"sb_env.{name}": var for name, var in envvars.items()},
        ).format_script(script)
