from __future__ import absolute_import


def quote_escape(text: str):
    return text.replace("'", "'\"'\"'")
