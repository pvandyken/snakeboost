# pyright: reportGeneralTypeIssues=false
from __future__ import absolute_import

from pathlib import Path

import pytest

from snakeboost.pipenv import PipEnv
from snakeboost.script import (
    SnakemakeArgs,
    _get_arg,
    _parse_snakemake_arg,
    pyscript,
    snakemake_args,
)


@pytest.mark.parametrize(
    ("arg", "value", "result"),
    (
        ("one", None, "--one {one}"),
        ("test", ["first"], "--test first={test.first}"),
        (
            "foo",
            ["one", "two", "moose"],
            "--foo one={foo.one} two={foo.two} moose={foo.moose}",
        ),
    ),
)
def test_get_arg(arg, value, result):
    assert _get_arg(arg, value) == result


def test_pyscript(tmp_path: Path):
    script = tmp_path / "hello_world.py"
    print(script)
    script.touch()
    assert pyscript(
        str(script),
        input=["one", "two"],
        output=["foo"],
        wildcards=["subject", "verb", "adjective"],
    ) == (
        f"python {script} "
        "--input one={input.one} two={input.two} --output "
        "foo={output.foo} --params {params} --wildcards subject={wildcards.subject} "
        "verb={wildcards.verb} adjective={wildcards.adjective} --resources {resources} "
        "--log {log} --threads {threads}"
    )

    venv = PipEnv("/tmp", packages=["black"])

    assert pyscript(
        str(script),
        venv,
        input=["one", "two"],
        output=["foo"],
        wildcards=["subject", "verb", "adjective"],
    ) == (
        f"{venv.get_venv} && {venv.python_path} {script} "
        "--input one={input.one} two={input.two} --output "
        "foo={output.foo} --params {params} --wildcards subject={wildcards.subject} "
        "verb={wildcards.verb} adjective={wildcards.adjective} --resources {resources} "
        "--log {log} --threads {threads}"
    )


@pytest.mark.parametrize(
    ("converter", "values", "result"),
    (
        (Path, [], []),
        (str, ["one", "two", "three"], ["one", "two", "three"]),
        (Path, ["/tmp/one", "/tmp/two"], [Path("/tmp/one"), Path("/tmp/two")]),
        (str, ["foo=bar", "hello=world"], {"foo": "bar", "hello": "world"}),
        (
            Path,
            ["first=/tmp/first", "second=second/from/top"],
            {"first": Path("/tmp/first"), "second": Path("second/from/top")},
        ),
    ),
)
def test_parse_snakemake_arg(converter, values, result):
    assert _parse_snakemake_arg(converter, values) == result


def test_SnakemakeArgs():
    args = SnakemakeArgs(
        input=["path/to/input"],
        output=["one=path/to/output/one", "two=/path/to/output/two"],
        params=[],
        wildcards=["hello=world", "foo=bar"],
        threads="2",
        resources=[],
        log="",
    )
    assert args.input == [Path("path/to/input")]
    assert args.output == {
        "one": Path("path/to/output/one"),
        "two": Path("/path/to/output/two"),
    }
    assert args.params == []
    assert args.wildcards == {"hello": "world", "foo": "bar"}
    assert args.threads == 2
    assert args.resources == []
    assert args.log == Path()


def test_snakemake_args():
    assert snakemake_args(
        [
            "--input",
            "path/to/input",
            "--output",
            "one=path/to/output/one",
            "two=/path/to/output/two",
            "--threads",
            "2",
            "--wildcards",
            "hello=world",
            "foo=bar",
        ]
    ) == SnakemakeArgs(
        input=["path/to/input"],
        output=["one=path/to/output/one", "two=/path/to/output/two"],
        params=[],
        wildcards=["hello=world", "foo=bar"],
        threads="2",
        resources=[],
        log="",
    )
