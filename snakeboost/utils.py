# pylint: disable=missing-class-docstring, invalid-name
from __future__ import absolute_import

import hashlib

from snakeboost.bash.cmd import StringLike, echo
from snakeboost.bash.statement import ShIf, subsh
from snakeboost.bash.utils import quote_escape


def get_replacement_field(
    field_name: str = None,
    format_spec: str = None,
    conversion: str = None,
):
    if not field_name:
        return ""
    contents = "".join(
        filter(
            None,
            [
                field_name,
                f"!{conversion}" if conversion else None,
                f":{format_spec}" if format_spec else None,
            ],
        )
    )
    return f"{{{contents}}}"


def silent_mv(src: str, dest: str):
    """This was written out of concern for mv affecting the file timestamp, but it
    doesn't seem to. Leaving this here for now, but should eventually be removed if
    we never encounter problems."""
    return (
        # f"timestamp=$(stat -c %y {src}) && "
        f"mv {src} {dest}"
        # f"touch -hd \"$timestamp\" {dest}"
    )


def cp_timestamp(src: str, dest: str):
    return f"timestamp=$(stat -c %y {src}) && " f'touch -hd "$timestamp" {dest}'


def hash_path(name: str):
    return f"$(realpath -s '{quote_escape(name)}' | md5sum | awk '{{{{print $1}}}}')"


def rm_if_exists(path: StringLike, recursive: bool = False):
    if recursive:
        flag = "-rf"
    else:
        flag = ""
    return (ShIf.exists(path) | ShIf.is_symlink(path)) >> f"rm {flag} {path}"


def split(text: str):
    return subsh(echo(text))


def resolve(path: StringLike, no_symlinks: bool = False):
    s = "-s" if no_symlinks else ""
    return subsh(f"realpath {s} {path}")


def get_hash(items: str):
    encoded = items.encode("utf-8")
    return hashlib.md5(encoded).hexdigest()


def escaped(text: str, char_pos: int):
    return char_pos > 0 and text[char_pos - 1] == "\\"


# pylint: disable=too-many-branches
def within_quotes(text: str, curr: int = 0) -> int:
    double = text.index('"') if '"' in text else len(text)
    single = text.index("'") if "'" in text else len(text)
    if double == len(text) and single == len(text):
        return curr

    if curr == 0:
        if double < single:
            if escaped(text, double):
                result = 0
            else:
                result = -1
        else:
            if escaped(text, single):
                result = 0
            else:
                result = 1

    elif curr == -1:
        if double < single:
            if escaped(text, double):
                result = -1
            else:
                result = 0

        # Don't worry about escaping single quote within double quote
        else:
            result = -1
    else:
        if double < single:
            result = 1
        # Can't escape single quote within single quotes
        else:
            result = 0

    tail = (double if double < single else single) + 1
    if tail == len(text):
        return result
    return within_quotes(text[tail:], result)
