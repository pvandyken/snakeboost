# `PipEnv`

```{currentmodule} snakeboost
```

Snakemake prefers Conda for Python environment management.
Conda, however, is not appropriate for certain environments, such as compute clusters.
{class}`PipEnv` allows you to create traditional virtual environments on the fly, using `virtualenv` under the hood.

Start by creating a new environment:

```python
from snakeboost import PipEnv

my_env = PipEnv(
  root="/tmp",
  packages=[
    "numpy",
    "pandas",
    "scipy==1.8.0",
    "git+https://github.com/nipy/nibabel@7cfaebf",
    "flake8"
  ]
)
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
Use one of the {class}`PipEnv` methods or attributes to get access to the exact path.
This allows you to use as many {class}`PipEnv`s as you want in one workflow, or even one rule!

Individual environments will be saved in a folder named with the hash of all package names and `requirements.txt` paths, and will be reused when possible.
Environment creation is threadsafe, so having 32 rules using the same environment causes no issues.

[See the full docs here](PipEnv)
