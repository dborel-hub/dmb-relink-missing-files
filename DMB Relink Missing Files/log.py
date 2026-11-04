"""
Logging for DMB Relink Missing Files.

Quiet by default: only warnings and errors reach Nuke's Script Editor.
For troubleshooting, set the environment variable DMB_RELINK_DEBUG=1
before launching Nuke to see everything.
"""

import os
import sys
import logging

log = logging.getLogger("DMBRelinkMissingFiles")

if not log.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter("[DMB Relink Missing Files] %(message)s"))
    log.addHandler(_handler)
    log.propagate = False

log.setLevel(logging.DEBUG if os.environ.get("DMB_RELINK_DEBUG") else logging.WARNING)
