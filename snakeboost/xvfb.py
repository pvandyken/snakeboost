from __future__ import absolute_import

import attr

from snakeboost.utils import quote_escape


# pylint: disable=too-few-public-methods
@attr.frozen
class XvfbRun:
    """Functions to enable virtual x11 servers on compute clusters

    xvfb-run is only used if ``$DISPLAY`` is not set
    """

    def __call__(self, cmd: str):
        """Start a virtual x11 server on compute clusters

        Computers without graphic support, such as compute clusters, cannot typically
        run commands requiring and x-server. This function wraps commands with
        `xvfb-run`, which starts a virtual x-server. This command is thread safe

        Parameters:
            cmd (str):
                The command to run

        Returns:
            str: The modified shell script
        """
        return (
            f"echo '{quote_escape(cmd)}' | "
            "$([ -z $DISPLAY ] && echo 'xvfb-run -a ') bash"
        )
