"""
Configuration settings for DMB Relink Missing Files
"""

import os
import json
from .log import log

# Application metadata
APP_NAME = "DMB Relink Missing Files"
APP_VERSION = "1.0.0"
AUTHOR = "Daniel Marinho Borel"
CONTACT = "danielmborel@gmail.com"

# Where updates come from (updater.py / install.pyw read these two lines)
GITHUB_REPO = "dborel-hub/dmb-relink-missing-files"
GITHUB_BRANCH = "main"

# Paths
NUKE_DIR = os.path.expanduser("~/.nuke")
# Everything lives in .nuke/DMB Relink Missing Files/
#   code at the root, small per-user settings (window size, last folder
#   used) in data/
APP_ROOT = os.path.dirname(os.path.abspath(__file__))
CONFIG_DIR = os.path.join(APP_ROOT, "data")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

# Node class -> knob that holds the file path. Used by "Scan All Nodes",
# which (unlike "Scan Selected Nodes") has no TCL-only path and must go
# through node.Class()/node.knobs() directly.
RELINK_KNOBS = {
    "Read": "file",
    "Write": "file",
    "DeepRead": "file",
    "DeepWrite": "file",
    "Vectorfield": "vfield_file",
    "ReadGeo2": "file",
    "WriteGeo": "file",
    "Camera2": "file",
    "Camera3": "file",
    "AudioRead": "file",
    "Precomp": "file",
}

# Knobs tried in this order by "Scan Selected Nodes", which only has a node
# NAME from TCL (no node.Class() - reading that would burn the Nuke Indie
# node budget), so it just tries each known path-knob name in turn.
KNOBS_TO_TRY = ("file", "vfield_file")


class ConfigManager:
    """Small per-user settings: window geometry, last search folder."""

    def __init__(self):
        self.config_path = CONFIG_FILE
        self.config = self._load_config()

    def _load_config(self):
        default_config = {
            "last_search_folder": "",
            "window_geometry": "",
        }

        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    loaded_config = json.load(f)
                    default_config.update(loaded_config)
            except Exception as e:
                log.warning(f"Error loading config: {e}")

        return default_config

    def save_config(self):
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            log.warning(f"Error saving config: {e}")

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value
        self.save_config()


def init_directories():
    os.makedirs(CONFIG_DIR, exist_ok=True)


init_directories()
