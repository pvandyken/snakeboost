# Snakeboost

Snakeboost provides enhancers and helpers to turbocharge your [snakemake](https://snakemake.readthedocs.io/en/stable/) workflows.
The project is currently in it's alpha stage.

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
However, boost provides a much more important function, as discussed in the next section.

## Boost function

Snakeboost enhancers return strings containing bash scripts that Snakemake can run using the shell directive.
While this core idea is simple, the scripts returned can be very complicated, especially when mutiple enhancers are chained together.
This creates a problem when inspecting your code using `snakemake -np`: Snakemake dutifully prints out a massive, unreadable wall of code:

```bash
rule lint_tarred_scripts:
    input: /path/to/my/archive.nii.gz
    jobid: 1

set -euo pipefail; echo '( ( ( if [[ -d /tmp/__snakemake_tarfiles__/$(realpath '"'"'/path/to/my/archive.tar.gz'"'"' | md5sum | awk '"'"'{print $1}'"'"') ]]; then if [[ -e /path/to/my/archive.tar.gz.swp ]]; then ( [ ! -e /path/to/my/archive.tar.gz ] || rm  /path/to/my/archive.tar.gz ); else mv /path/to/my/archive.tar.gz /path/to/my/archive.tar.gz.swp; fi; else mkdir -p  /tmp/__snakemake_tarfiles__/$(realpath '"'"'/path/to/my/archive.tar.gz'"'"' | md5sum | awk '"'"'{print $1}'"'"'); if [[ -e /path/to/my/archive.tar.gz.swp ]]; then echo  "Found stowed tarfile: '"'"'/path/to/my/archive.tar.gz.swp'"'"'. Extracting..."; tar -xzf /path/to/my/archive.tar.gz.swp -C /tmp/__snakemake_tarfiles__/$(realpath '"'"'/path/to/my/archive.tar.gz'"'"' | md5sum | awk '"'"'{print $1}'"'"'); ( [ ! -e /path/to/my/archive.tar.gz ] || rm  /path/to/my/archive.tar.gz ); else echo  "Extracting and stowing tarfile: '"'"'/path/to/my/archive.tar.gz'"'"'"; tar -xzf /path/to/my/archive.tar.gz -C /tmp/__snakemake_tarfiles__/$(realpath '"'"'/path/to/my/archive.tar.gz'"'"' | md5sum | awk '"'"'{print $1}'"'"'); mv /path/to/my/archive.tar.gz /path/to/my/archive.tar.gz.swp; fi; fi; ln -s /tmp/__snakemake_tarfiles__/$(realpath '"'"'/path/to/my/archive.tar.gz'"'"' | md5sum | awk '"'"'{print $1}'"'"') /path/to/my/archive.tar.gz; timestamp=$(stat -c %y /path/to/my/archive.tar.gz.swp) && touch -hd "$timestamp" /path/to/my/archive.tar.gz ) ); ( ( ( mkdir -p  /tmp/__snakemake_venvs__/ac209fe369c232011135893704382aa1; echo '"'"'if [[ ! -x /tmp/__snakemake_venvs__/ac209fe369c232011135893704382aa1/venv/bin/python ]]; then ( ( virtualenv --no-download /tmp/__snakemake_venvs__/ac209fe369c232011135893704382aa1/venv; /tmp/__snakemake_venvs__/ac209fe369c232011135893704382aa1/venv/bin/python -m pip install  --upgrade pip && /tmp/__snakemake_venvs__/ac209fe369c232011135893704382aa1/venv/bin/python -m pip install  flake8, pylint, black )  || ( echo  "[ERROR] (jobid=1): Error creating python environment 1>&2"; rm -rf /tmp/__snakemake_venvs__/ac209fe369c232011135893704382aa1/venv; false ) ); fi'"'"' | flock -w 900 /tmp/__snakemake_venvs__/ac209fe369c232011135893704382aa1 /bin/bash ) && /tmp/__snakemake_venvs__/ac209fe369c232011135893704382aa1/venv/bin/python /tmp/__snakemake_venvs__/ac209fe369c232011135893704382aa1/venv/bin/flake8 /path/to/my/archive.tar.gz/script.py ) && ( ( rm /path/to/my/archive.tar.gz; mv /path/to/my/archive.tar.gz.swp /path/to/my/archive.tar.gz ) ) || ( ( rm /path/to/my/archive.tar.gz; mv /path/to/my/archive.tar.gz.swp /path/to/my/archive.tar.gz ); false ) ) )' | $([ -z $DISPLAY ] && echo 'xvfb-run -a ') bash
```

Not nice! But fear not, the `boost()` function provides the solution.
It trims and cuts the above bash monstrosity into the command you actually care about:

```bash
rule lint_tarred_scripts:
    input: /path/to/my/archive.nii.gz
    jobid: 1

# Snakeboost enhanced: to view script, set Boost(debug=True):
> flake8 '/path/to/my/archive.tar.gz'/script.py
```

Beautiful! But what happened to the code?
`boost()` takes the wall of bash and packages it inside a script file, saving it to a directory of your choice.
So instead of passing the code directly to Snakemake, it passes a script call along with all the relevant arguments.
By default, it uses some bash magic to hide the script call from display, to keep it from cluttering your terminal.
If you'd like to view the script call for more advanced debugging, however, simply set debug to True when initializing Boost.
Then you'll get something like this:

```bash
rule lint_tarred_scripts:
    input: /path/to/my/archive.nii.gz
    jobid: 1

# Snakeboost enhanced (debug mode)
# > flake8 '/path/to/my/archive.tar.gz'/script.py

/tmp/__sb_scripts__/132e37fa2481a8515fbdd8c280677183 '/path/to/my/archive.tar.gz' '1'
```

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
