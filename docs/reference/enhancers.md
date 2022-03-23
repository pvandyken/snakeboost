# Enhancers

::: snakeboost.pipenv

::: snakeboost.script
    selection:
        members:
            - Pyscript

::: snakeboost.tar
    selection:
        filters:
            - "!^_"
            - "__call__"

::: snakeboost.xvfb
    selection:
        filters:
            - "!^_"
            - "__call__"
