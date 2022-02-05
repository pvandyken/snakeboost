# pylint: disable=missing-class-docstring, invalid-name
from __future__ import absolute_import


class ShStatement:
    def to_str(self):
        return str(self)


class ShCmd(ShStatement):
    pass
