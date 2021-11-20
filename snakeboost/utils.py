from typing import NamedTuple, Tuple

BashWrapper = NamedTuple(
    "BashWrapper",
    [("before", Tuple[str]), ("success", Tuple[str]), ("failure", Tuple[str])],
)


def quote_escape(text: str):
    return text.replace("'", "'\"'\"'")


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
    return f"$(realpath '{quote_escape(name)}' | md5sum | awk '{{{{print $1}}}}')"


def rm_if_exists(path: str, recursive: bool = False):
    if recursive:
        flag = "-rf"
    else:
        flag = ""
    return f"( [[ ! -e {path} ]] || rm {flag} {path} )"
