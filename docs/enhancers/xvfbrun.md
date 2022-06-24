# `XvfbRun`

`xvfb-run` is a linux utility that starts a virtual X-server.
This is useful for performing rendering jobs on headless servers and cluster environments, as an easier alternative to X-11 forwarding with SSH.
The {class}`XvfbRun <snakeboost.XvfbRun>` enhancer wraps commands with this call.
It's safer than manually prepending `xvfb-run -a` to your command, automatically handling quote escaping and preventing typos.
It also checks the `$DISPLAY` variable to see if `xvfb-run` is necessary, so it's safe to use on any system.
