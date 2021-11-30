# Snakeboost

Snakeboost provides enhancers and helpers to turbocharge your [snakemake](https://snakemake.readthedocs.io/en/stable/) workflows.
The project is currently in it's alpha stage.

# Script Enhancers

## Overview

Script enhancer functions wrap around bash scripts given under the `script` key in Snakemake Rules.
All enhancers have a common interface designed for easy use in your workflow.
To illustrate, we'll take `PipEnv` as an example (it lets you use pip virtual environments!).

1. Initiate the enhancer

Import the enhancer at the top of your `Snakefile` and instantiate it.
Most enhancers take a few arguments defining their global settings.

```python
from snakeboost import PipEnv

my_env = PipEnv(packages=["numpy", "flake8"], root=("/tmp"))
```

2. Use the enhancer in a rule

When instantiated, enhancers can be called using the bash command as an argument.

```python
rule lint_python:
    inputs: "some-script.py"
    shell:
        my_env.script("flake8 {input}")
```

Some enhancers, such as `PipEnv`, provide multiple functions (e.g. `.script`, `.python`, etc) that provide slightly different functionality.
Others, such as `Tar`, have methods that return a modified instance.

```python
rule inspect_tarball:
    inputs: "some_archive.tar.gz"
    shell:
        tar.using(inputs=["{input}"])("ls {input}/")
```

Snakeboost uses this slightly convoluted way of setting arguments to allow easy chaining of multiple enhancers.
This leads us to step 3:

3. Use `pipe()` to chain multiple enhancers

Snakeboost packages a `pipe()` arg very similar to that provided by `PyToolz` (in fact, that's what we adapted it from).
This lets us use a very clean syntax to specify multiple enhancers:

```python
from snakeboost import pipe

rule lint_tarred_scripts:
    inputs: "script_archive.tar.gz"
    shell:
        pipe(
            tar.using(inputs=["{input}"]),
            my_env.script,
            "flake8 {input}/script.py"
        )
```

## Available Enhancers

### `PipEnv`

Snakemake prefers Conda for Python environment management.
Conda, however, is not appropriate for certain environments, such as compute clusters.
PipEnv allows you to create traditional virtual environments on the fly, using `virtualenv` under the hood.
You can create as many environments as you want per workflow, and each environment can be instantiate with a combination of package listings and `requirements.txt` files.
All environments will be saved to the folder you specify under the `root` argument; typically, this would be a temporary directory.
Individual environments will be saved in a folder named with the hash of all package names and `requirements.txt` paths, and will be reused when possible.
Environment creation is threadsafe, so having 32 rules using the same environment causes no issues.

[Source](snakeboost/pipenv.py)

### `Tar`

Sometimes, rules produce a directory full of files as output.
Snakemake can easily handle this using the `directory` function, but for large scale applications, it's easier on the filesystem to immediately package the directory into a tarball.
`Tar` facilitates this exercise, effectively "mounting" tar files as directories in a scratch directory of your choice (e.g. your `tmp` dir).
It supports outputs (creating new tar files), inputs (reading existing tar files), and modification (reading and writing an existing tar file).
In all cases, you can treat the tar file in your script as if it were a regular directory.
`Tar` will manage packing and unpacking.

For example, we could make a virtual env and package it in a tar file as follows:

```python
from snakeboost import Tar

tar = Tar("/tmp/prepdwi_tarfolders")

rule make_pipenv:
    output:
        "venv.tar.gz"
    shell:
        tar.using(outputs = ["{output}"])(
            "virtualenv {output} && cat {output}/pyvenv.cfg",
        )
```

We can then read a file from this pipenv as follows:

```python
rule read_pipenv:
    input:
        pip=rules.make_pipenv.output,
        out=rules.read_gitignore.output
    shell:
        tar.using(inputs=["{input.pip}"])(
            "cat {input.pip}/pyvenv.cfg"
        )
```

We can add a file in a similar way:

```python
rule add_gitignore:
    input:
        rules.make_pipenv.output
    output:
        "gitignore.added"
    shell:
        tar.using(modify=["{input}"])(
            "echo .pyenv >> {input}/.gitignore && touch {output}"
        )
```

Note that we use `gitignore.added` as a marker file to indicate completion of the rule.
This is important, as here `rules.make_pipenv.output` is both the `input` and the `output` (since it's being modified), and this is inherently ambiguous to Snakemake.

When using `"{input}"` or `"{output}"` wildcards, be sure to fully resolve them.
In other words, if you have multiple `inputs:`, use the full dot-syntax to access the precise input to be tarred (e.g. `"{input.pip}"`).
Otherwise, you'll get errors.

A few more features:
* `inputs`, `ouputs`, and `modify` can be mixed and matched in one single rule as much as you please.
* Unpacked tar files are stored in a directory under `root` using the hashed tar file path as the directory name.
  These directories will not be deleted by snakeboost, meaning they will be seamlessly reused over the course of your workflow.

Note that `Tar` is **NOT** necessarily threadsafe at this time, so if two or more jobs try to unpack the exact same file, you may get a strange failure.
If you require this behaviour, please leave an issue so it can be prioritized.

### `XvfbRun`

`xvfb-run` is a linux utility that starts a virtual X-server.
This is useful for performing rendering jobs on headless servers and cluster environments, as an easier alternative to X-11 forwarding with SSH.
The `XvfbRun` enhancer wraps commands with this call.
It's safer than manually prepending `xvfb-run -a` to your command, automatically handling quote escaping and preventing typos.

# Contributing

If you have a small utility function for your Snakemake workflows, it would likely make a great addition to the Snakeboost ecosystem.
Script enhancers should follow the basic interface of the other enhancers: a class initialized with global settings that exposes one or more functions that take a bash script as argument.

Snakebids uses [Poetry](https://python-poetry.org/) for dependency management and [pre-commit](https://pre-commit.com/) for Quality Assurance tests.
If Poetry is not already installed on your system, follow the [instructions](https://python-poetry.org/docs/master/) on their website.
Then clone the repo and initialize by running:

```bash
poetry install
poetry run pre-commit install
```

