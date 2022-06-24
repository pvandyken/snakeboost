# Snakeboost

Snakeboost provides enhancers and helpers to turbocharge your [snakemake](https://snakemake.readthedocs.io/en/stable/) workflows.
The project is currently in it's alpha stage.

[Full Documentation](https://snakeboost.readthedocs.io)

# Script Enhancers

## Overview

Script enhancer functions wrap around bash scripts given to the `shell` directive in Snakemake Rules.
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

3. Use `boost()` to chain multiple enhancers

Chaining many enhancers together can quickly lead to indentation hell:

```python
rule lint_tarred_scripts:
    inputs: "script_archive.tar.gz"
    shell:
        xvfb-run(
            tar.using(inputs=["{input}"])(
                my_env.script(
                    "flake8 {input}/script.py"
                )
            )
        )
```

The `boost()` function lets you rewrite this as:

```python
from snakeboost import Boost

boost = Boost()

rule lint_tarred_scripts:
    inputs: "script_archive.tar.gz"
    shell:
        boost(
            xvfb_run,
            tar.using(inputs=["{input}"]),
            my_env.script,
            "flake8 {input}/script.py"
        )
```

That makes your rules much cleaner!
However, boost provides a much more important function, as discussed fully in the [docs...](https://snakeboost.readthedocs.io/boost.html)


## Enhancers

Current enhancers include:

* `PipEnv`: Use pip environments in snakemake workflows
* `PyScript`: Use python scripts along with pip envs and other Snakeboost enhancers
* `Tar`: tar up your output files or untar input files before the job
* `Xvfb`: Start a virtual X-server to run headless graphical commands (e.g. rendering) on servers without graphics support.

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
