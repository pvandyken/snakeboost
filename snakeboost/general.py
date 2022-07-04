# pylint: disable=missing-module-docstring
from __future__ import absolute_import

import abc
import itertools as it
import string
from typing import Callable, Dict, Iterable, Optional, Sequence, Set, Tuple, Union

import attr

from snakeboost.bash import ShEntity, ShVar
from snakeboost.bash.statement import ShBlock, ShTry
from snakeboost.utils import get_replacement_field


# pylint: disable=missing-docstring
class Enhancer(abc.ABC):
    # pylint: disable=no-self-use
    def log_format(self, script: str):
        return script


# pylint: disable=missing-class-docstring
@attr.frozen
class BashWrapper:
    comps: Tuple["ScriptComp"] = tuple()
    subs: Dict[str, ShVar] = {}

    @property
    def assignments(self):
        return tuple(
            it.chain.from_iterable(
                comp.assignments
                if isinstance(comp.assignments, Iterable)
                else [comp.assignments]
                for comp in self.comps
            )
        )

    @property
    def before(self):
        return tuple(comp.before for comp in self.comps)

    @property
    def inner_mods(self):
        return [comp.inner_mod for comp in self.comps if comp.inner_mod]

    @property
    def outer_mods(self):
        return [comp.outer_mod for comp in self.comps if comp.outer_mod]

    @property
    def success(self):
        return tuple(comp.success for comp in self.comps)

    @property
    def failure(self):
        return tuple(comp.failure for comp in self.comps)

    @property
    def complete(self):
        return tuple(comp.after for comp in self.comps)

    @classmethod
    def merge(cls, wrappers: Sequence["BashWrapper"]):
        merged_subs = {}
        for wrapper in wrappers:
            merged_subs.update(wrapper.subs)
        return BashWrapper(
            comps=tuple(it.chain.from_iterable(wrapper.comps for wrapper in wrappers)),
            subs=merged_subs,
        )

    def format_script(self, script: str):
        def substitute():
            used: Set[str] = set()
            for literal, f_name, *f_parts in string.Formatter().parse(script):
                escaped = literal.replace("{", "{{").replace("}", "}}")
                if f_name in self.subs:
                    yield f"{escaped}{self.subs[f_name]}"
                    used.add(f_name)
                    continue
                yield f"{escaped}{get_replacement_field(f_name, *f_parts)}"
            if len(used - set(self.subs)):
                raise Exception()

        script = "".join(substitute())
        for mod in filter(None, self.inner_mods):
            script = mod(script)
        block = ShBlock(
            *[var.set_statement for var in self.assignments if var],
            *self.before,
            ShTry(script)
            .catch(*self.failure, "false")
            .els(*self.success)
            .finish(*self.complete),
            wrap=False,
        ).to_str()
        for mod in filter(None, self.outer_mods):
            block = mod(block)
        return block


# pylint: disable=missing-class-docstring
@attr.define
class ScriptComp:
    assignments: Union[ShVar, Iterable[ShVar], None] = None
    before: ShEntity = ""
    inner_mod: Optional[Callable[[str], str]] = None
    outer_mod: Optional[Callable[[str], str]] = None
    success: ShEntity = ""
    failure: ShEntity = ""
    after: ShEntity = ""
