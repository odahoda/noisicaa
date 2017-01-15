#!/usr/bin/python3

import os
import os.path
import subprocess

# Exit codes of the main app.
EXIT_SUCCESS = 0
EXIT_EXCEPTION = 1
EXIT_RESTART = 17
EXIT_RESTART_CLEAN = 18


DATA_DIR = os.path.abspath(os.path.join(__file__, '..', '..', 'data'))

CACHE_DIR = os.path.abspath(os.path.join(os.path.expanduser('~'), '.cache', 'noisicaä'))

def __xdg_user_dir(resource):
    try:
        res = subprocess.run(['/usr/bin/xdg-user-dir', resource], stdout=subprocess.PIPE)
        return os.fsdecode(res.stdout.rstrip(b'\n'))
    except:
        return os.path.expanduser('~')

MUSIC_DIR = __xdg_user_dir('MUSIC')
for d in ['noisicaä', 'Noisicaä', 'noisicaa', 'Noisicaa']:
    if os.path.isdir(os.path.join(MUSIC_DIR, d)):
        PROJECT_DIR = os.path.join(MUSIC_DIR, d)
        break
else:
    PROJECT_DIR = MUSIC_DIR

# Cleanup namespace
del os
del subprocess
