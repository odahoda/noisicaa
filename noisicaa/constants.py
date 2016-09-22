#!/usr/bin/python3

import os.path

# Exit codes of the main app.
EXIT_SUCCESS = 0
EXIT_EXCEPTION = 1
EXIT_RESTART = 17
EXIT_RESTART_CLEAN = 18


DATA_DIR = os.path.abspath(os.path.join(__file__, '..', '..', 'data'))

CACHE_DIR = os.path.abspath(os.path.join(os.path.expanduser('~'), '.cache', 'noisicaä'))

# Cleanup namespace
del os
