# `Tar`

```{currentmodule} snakeboost
```

Sometimes, rules produce a directory full of files as output.
Snakemake can easily handle this using the `directory` function, but for large scale applications, it's easier on the filesystem to immediately package the directory into a tarball.
{class}`Tar` facilitates this exercise, effectively "mounting" tar files as directories in a scratch directory of your choice (e.g. your `tmp` dir).
It supports outputs (creating new tar files), inputs (reading existing tar files), and modification (reading and writing an existing tar file).
In all cases, you can treat the tar file in your script as if it were a regular directory.
{class}`Tar` will manage packing and unpacking.

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
        touch("gitignore.added")
    shell:
        tar.using(modify=["{input}"])(
            "echo .pyenv >> {input}/.gitignore"
        )
```

Note that we use `gitignore.added` with the snakemake built-in command `touch()` to indicate completion of the rule.

When using `"{input}"` or `"{output}"` wildcards, be sure to fully resolve them.
In other words, if you have multiple `inputs:`, use the full dot-syntax to access the precise input to be tarred (e.g. `"{input.pip}"`).
Otherwise, you'll get errors.

A few more features:

* `inputs`, `ouputs`, and `modify` can be mixed and matched in one single rule as much as you please.
* Unpacked tar files are stored in a directory under `root` using the hashed tar file path as the directory name.
  These directories are typically not deleted by snakeboost, meaning they will be seamlessly reused over the course of your workflow.
* When using input tar files, snakeboost will check if the unpacked contents were modified over the course of the script.
  If so, it will automatically delete the mounted directory so changes are not passed on to future rules that may use the tar file.

Note that `Tar` is **NOT** necessarily threadsafe at this time, so if two or more jobs try to unpack the exact same file, you may get a strange failure.
If you require this behaviour, please leave an issue so it can be prioritized.
