# Boost function

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
