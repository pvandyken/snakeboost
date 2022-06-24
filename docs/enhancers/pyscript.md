# `Pyscript`

```{currentmodule} snakeboost
```

Because Pipenv modifies the shell script, it cannot be used with Snakemake's `script` directive.
{class}`Pyscript` fills this gap, providing similar features to the native `script` directive while remaining compatible with Pipenv.
It can also be combined with any of the other enhancers!

Pyscript works by calling your script as a command line progam, passing inputs, outputs, params, and every other snakemake entity as arguments.
On the Snakefile side, snakeboost provides the {class}`Pyscript` enhancer, which composes the bash to call your python file.
On the script side, snakeboost has the `snakemake_parser()` function, which automatically parses the command line arguments sent by Snakemake and organizes them into the `SnakemakeArgs` class.
This object has the same interface as the `snakemake` object used in ordinary `snakemake` scripts; the only difference is that your script must retrieve it by importing and calling `snakemake_parser()`.
Thus, any scripts called by {class}`Pyscript` must have `snakeboost` as a dependency in their Python environment.

{class}`Pyscript` must be initialized as follows:

```python
from snakeboost import Pyscript
pyscript = Pyscript(workflow.basedir)
```

The `workflow.basedir` argument is necessary to inform {class}`Pyscript` of the path to your `Snakefile`.
This will be used to locate your scripts later.

{class}`Pyscript` will attempt to automatically pass on every entity (including inputs, outputs, params, etc) in your rule on to the script.
This works fantastically for single items or lists:

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
In order to pass them on to {func}`snakemake_args` as dicts, we need to specify the name of each input:

% The first is through inline annotation:

% ```python
% my_script = Pyscript(workflow.basedir)
% rule rule_with_script:
%     input:
%         **my_script.input(
%             input_1="path/1",
%             input_2="path/2"
%         )
%     output: "path/to/output"
%     shell: my_script("scripts/my_script.py")
% ```
%
% Here, we start by defining the script before the rule.
% Notice how `workflow.basedir` is passed into `Pyscript` as an argument.
% This is a variable provided by Snakemake set to the location of the Snakefile.
% We use it here to inform `Pyscript` where the scripts directory will be.
% Second, we wrap named entities using the appropriate method from our `Pyscript` instance (we would use `my_method.params()` for params, etc).
% Notice the double asterisk `**` before the method call.
% This is essential to properly unpack the Dictionary returned by `.input()` so it can be read by Snakemake.
% Finally, we call our `Pyscript` instance with the path of our script relative to the Snakefile (just like in normal Snakemake scripts) and pass it to the **shell** directive.
% Notice how we only need to wrap named entities.
% In the above example, `output` will still be passed on to the script.


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

Finally, {class}`Pyscript` is easily combined with Pipenv. Just call {func}`PipEnv.script` before your {class}`Pyscript`:


```python
rule with_pipenv_script:
    shell:
        boost(
            my_env.script,
            pyscript("scripts/my_script.py")

        )
```

You can also directly pass any Python executable path to pyscript.
This is useful if your {class}`Pyscript` is part of a larger Bash Script.
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
```
