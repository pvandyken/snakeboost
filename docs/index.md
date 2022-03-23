# Snakeboost

Snakeboost provides enhancers and helpers to turbocharge your [snakemake](https://snakemake.readthedocs.io/en/stable/) workflows.
The project is currently in it's alpha stage.

## Script Enhancers

### Overview

Script enhancer functions wrap around bash scripts given to the `shell` directive in Snakemake Rules.
All enhancers have a common interface designed for easy use in your workflow.
To illustrate, we'll take `PipEnv` as an example (it lets you use pip virtual environments!).

1. Initiate the enhancer

    Import the enhancer at the top of your `Snakefile` and instantiate it.
    Most enhancers take a few arguments defining their global settings.

    ```py
    from snakeboost import PipEnv

    my_env = PipEnv(packages=["numpy", "flake8"], root=("/tmp"))
    ```

1. Use the enhancer in a rule

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
    from snakeboost import Tar

    tar = Tar(root="/tmp")
    rule inspect_tarball:
        inputs: "some_archive.tar.gz"
        shell:
            tar.using(inputs=["{input}"])("ls {input}/")
    ```

    Here, `tar.using()` returns a new instance of `Tar` with modified properties.
    `Tar` itself is callable, taking a string and wrapping it with all the script necessary to unpack your input tar file.
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

### Boost function

Snakeboost enhancers return strings containing bash scripts that Snakemake can run using the shell directive.
While this core idea is simple, the scripts returned can be very complicated, especially when mutiple enhancers are chained together.
This creates a problem when inspecting your code using `snakemake -np`: Snakemake dutifully prints out a massive, unreadable wall of code:

```bash
rule lint_tarred_scripts:
    input: /path/to/my/archive.nii.gz
    jobid: 1

set -euo pipefail; echo '( ( ( if [[ -d /tmp/__snakemake_tarfiles__/$(realpath '"'"'/path/to/my/archive.tar.gz'"'"' | md5sum | awk '"'"'{print $1}'"'"') ]];
then if [[ -e /path/to/my/archive.tar.gz.swp ]]; then ( [ ! -e /path/to/my/archive.tar.gz ] || rm  /path/to/my/archive.tar.gz ); else mv /path/to/my/archive
.tar.gz /path/to/my/archive.tar.gz.swp; fi; else mkdir -p  /tmp/__snakemake_tarfiles__/$(realpath '"'"'/path/to/my/archive.tar.gz'"'"' | md5sum | awk '"'"'
{print $1}'"'"'); if [[ -e /path/to/my/archive.tar.gz.swp ]]; then echo  "Found stowed tarfile: '"'"'/path/to/my/archive.tar.gz.swp'"'"'. Extracting..."; tar
 -xzf /path/to/my/archive.tar.gz.swp -C /tmp/__snakemake_tarfiles__/$(realpath '"'"'/path/to/my/archive.tar.gz'"'"' | md5sum | awk '"'"'{print $1}'"'"'); ( [
! -e /path/to/my/archive.tar.gz ] || rm  /path/to/my/archive.tar.gz ); else echo  "Extracting and stowing tarfile: '"'"'/path/to/my/archive.tar.gz'"'"'";
tar -xzf /path/to/my/archive.tar.gz -C /tmp/__snakemake_tarfiles__/$(realpath '"'"'/path/to/my/archive.tar.gz'"'"' | md5sum | awk '"'"'{print $1}'"'"');
mv /path/to/my/archive.tar.gz /path/to/my/archive.tar.gz.swp; fi; fi; ln -s /tmp/__snakemake_tarfiles__/$(realpath '"'"'/path/to/my/archive.tar.gz'"'"'| md5sum
| awk '"'"'{print $1}'"'"') /path/to/my/archive.tar.gz; timestamp=$(stat -c %y /path/to/my/archive.tar.gz.swp) && touch -hd "$timestamp" /path/to/my/archive.tar.
gz ) ); ( ( ( mkdir -p  /tmp/__snakemake_venvs__/ac209fe369c232011135893704382aa1; echo '"'"'if [[ ! -x /tmp/__snakemake_venvs__/ac209fe369c232011135893704382aa1/
venv/bin/python ]]; then ( ( virtualenv --no-download /tmp/__snakemake_venvs__/ac209fe369c232011135893704382aa1/venv; /tmp/__snakemake_venvs__/
ac209fe369c232011135893704382aa1/venv/bin/python -m pip install  --upgrade pip && /tmp/__snakemake_venvs__/ac209fe369c232011135893704382aa1/venv/bin/python -m
pip install  flake8, pylint, black )  || ( echo  "[ERROR] (jobid=1): Error creating python environment 1>&2"; rm -rf /tmp/__snakemake_venvs__/
ac209fe369c232011135893704382aa1/venv; false ) ); fi'"'"' | flock -w 900 /tmp/__snakemake_venvs__/ac209fe369c232011135893704382aa1 /bin/bash ) && /tmp/
__snakemake_venvs__/ac209fe369c232011135893704382aa1/venv/bin/python /tmp/__snakemake_venvs__/ac209fe369c232011135893704382aa1/venv/bin/flake8 /path/to/my/
archive.tar.gz/script.py ) && ( ( rm /path/to/my/archive.tar.gz; mv /path/to/my/archive.tar.gz.swp /path/to/my/archive.tar.gz ) ) || ( ( rm /path/to/my/archive.
tar.gz; mv /path/to/my/archive.tar.gz.swp /path/to/my/archive.tar.gz ); false ) ) )' | $([ -z $DISPLAY ] && echo 'xvfb-run -a ') bash
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

#### Syntax and Usage

Like other enhancers, `boost()` must first be initialized:

```python
from snakeboost import Boost

boost=Boost(root="/tmpdir")
```

This gives you the opportunity to set a few global settings, such as the root directory for all your scripts (the tmp dir by default), or whether debug is on or off (disabled by default).

When using `boost()`, all its arguments must be enhancer functions except the very last one, which must be a bash command.
This typically will be a string, however, you can also construct complex, muli-line bash programs using a tuple of strings:

```python
rule lint_tarred_scripts:
    inputs: "script_archive.tar.gz"
    shell:
        boost(
            xvfb_run,
            tar.using(inputs=["{input}"]),
            my_env.script,
            (
                "flake8 {input}/script.py",
                "cat {input}/somefile.py",
                "some-command {input}"
            )
        )
```

`boost()` will join all the commands appropriately.
Note that it follows the snakemake default of "Bash Strict Mode", so a failure on any one of the lines will cause the entire script to fail.

### Enhancers

#### `PipEnv`

Snakemake prefers Conda for Python environment management.
Conda, however, is not appropriate for certain environments, such as compute clusters.
PipEnv allows you to create traditional virtual environments on the fly, using `virtualenv` under the hood.

Start by creating a new environment:

```python
from snakeboost import PipEnv

my_env = PipEnv(root="/tmp", packages=[
    "numpy",
    "pandas",
    "scipy==1.8.0",
    "git+https://github.com/nipy/nibabel@7cfaebf",
    "flake8"
])
```

Here, the root tells Snakeboost where to put the environment.
`packages` is a list of valid package specifier.
Version specifiers, git links, local files, anything valid in pip is valid here.
You could also use the `requirements=[...]` parameter, passing a list of `requirements.txt` files to load.

Once created, use the venv in a rule:

```python
rule lint_python:
    inputs: "some-script.py"
    shell:
        my_env.script("flake8 {input}")
```

This will run the `flake8` command installed into your venv.
Other methods include:

- `my_env.python(...)`: Execute a python file (e.g. `script.py`) or run a python module (e.g. `"-m module"`) using the venv python.
- `my_env.make_venv(...)`: Create the venv, then execute any arbitrary command.
  This is helpful if you need access to your venv somewhere in the middle of the script.
  In this case, you could use the `bin` or `python_path` attributes within the script.

Note that the venv is never "activated".
So just having `python <command>` somewhere in your script won't work.
Use one of the `PipEnv` methods or attributes to get access to the exact path.
This allows you to use as many `PipEnv`s as you want in one workflow, or even one rule!

Individual environments will be saved in a folder named with the hash of all package names and `requirements.txt` paths, and will be reused when possible.
Environment creation is threadsafe, so having 32 rules using the same environment causes no issues.

[See the full docs here][snakeboost.pipenv.PipEnv]

#### `Pyscript`

Because Pipenv modifies the shell script, it cannot be used with Snakemake's `script` directive.
`Pyscript` fills this gap, providing similar features to the native `script` directive while remaining compatible with Pipenv.
It can also be combined with any of the other enhancers!

Pyscript works by calling your script as a command line progam, passing inputs, outputs, params, and every other snakemake entity as arguments.
On the Snakefile side, snakeboost provides the `Pyscript` enhancer, which composes the bash to call your python file.
On the script side, snakeboost has the `snakemake_parser()` function, which automatically parses the command line arguments sent by Snakemake and organizes them into the `SnakemakeArgs` class.
This object has the same interface as the `snakemake` object used in ordinary `snakemake` scripts; the only difference is that your script must retrieve it by importing and calling `snakemake_parser()`.
Thus, any scripts called by `Pyscript` must have `snakeboost` as a dependency in their Python environment.

`Pyscript` must be initialized as follows:

```python
from snakeboost import Pyscript
pyscript = Pyscript(workflow.basedir)
```

The `workflow.basedir` argument is necessary to inform `Pyscript` of the path to your `Snakefile`.
This will be used to locate your scripts later.

`Pyscript` will attempt to automatically pass on every entity (including inputs, outputs, params, etc) in your rule on to the script.
This works fantasticly for single items or lists:

```python
rule some_rule:
    input: "path/to/input"

rule rule_with_list_input:
    input:
        "/path/1",
        "/path/2",
        "/path/3"

    shell:
        pyscript("scripts/myscript.py")
```

These will be received in your script as:

```python

from snakeboost import snakemake_parser

snakemake = snakemake_parser()

# some_rule
assert snakemake.input == Path("path/to/input")

# rule_with_list_input
assert snakemake.input == [
    Path("/path/1"),
    Path("/path/2"),
    Path("/path/3")
]
```

Unfortunately, it is unable to infer the names of named entities:

```python
rule named_inputs:
    input:
        input_1="/path/1",
        input_2="/path2"
```

By default, these will be treated as lists.
In order to pass them on to `snakemake_parser()` as dicts, we need to specify the name of each input:

<!-- The first is through inline annotation:

```python
my_script = Pyscript(workflow.basedir)
rule rule_with_script:
    input:
        **my_script.input(
            input_1="path/1",
            input_2="path/2"
        )
    output: "path/to/output"
    shell: my_script("scripts/my_script.py")
```

Here, we start by defining the script before the rule.
Notice how `workflow.basedir` is passed into `Pyscript` as an argument.
This is a variable provided by Snakemake set to the location of the Snakefile.
We use it here to inform `Pyscript` where the scripts directory will be.
Second, we wrap named entities using the appropriate method from our `Pyscript` instance (we would use `my_method.params()` for params, etc).
Notice the double asterisk `**` before the method call.
This is essential to properly unpack the Dictionary returned by `.input()` so it can be read by Snakemake.
Finally, we call our `Pyscript` instance with the path of our script relative to the Snakefile (just like in normal Snakemake scripts) and pass it to the **shell** directive.
Notice how we only need to wrap named entities.
In the above example, `output` will still be passed on to the script. -->


```python
from snakeboost import Pyscript
pyscript = Pyscript(workflow.basedir)
rule rule_with_script:
    input:
        input_1="path/1",
        input_2="path/2",
        input_3="path/3"
    output: "path/to/output"
    shell:
        pyscript(
            "scripts/my_script.py",
            input=["input_1", "input_2"]
        )
```

In the above example, `input_1` and `input_2` would be passed to the script, but not `input_3`.
Note that other entity types, such as output in the above example, would be passed as normal.

Named entities can be consumed in your script as follows:

```python

from snakeboost import snakemake_parser

snakemake = snakemake_parser()

assert snakemake.input == {
    "input_1": Path("path/1")
    "input_2": Path("path/2")
}
```

Finally, `Pyscript` is easily combined with Pipenv. Just call `pipenv.script()` with your `Pyscript`:


```python
rule with_pipenv_script:
    shell:
        boost(
            my_env.script,
            pyscript("scripts/my_script.py")

        )
```

You can also directly pass any Python executable path to pyscript.
This is useful if your Pyscript is part of a larger Bash Script.
Just remember that this will not automatically create your environment, so be sure to initialize the environment before the command begins!

```python
rule with_python_path:
    shell:
        boost(
            my_env.make_venv,
            (
                "some bash command",
                "some other bash command",
                pyscript(
                    "scripts/my_script.py",
                    python_path=my_env.python_path
                )
            )
        )
        my_env.python(
            Pyscript(workflow.basedir)("scripts/my_script.py")
        )
```

#### `Tar`

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

#### `XvfbRun`

`xvfb-run` is a linux utility that starts a virtual X-server.
This is useful for performing rendering jobs on headless servers and cluster environments, as an easier alternative to X-11 forwarding with SSH.
The `XvfbRun` enhancer wraps commands with this call.
It's safer than manually prepending `xvfb-run -a` to your command, automatically handling quote escaping and preventing typos.
It also checks the `$DISPLAY` variable to see if `xvfb-run` is necessary, so it's safe to use on any system.
