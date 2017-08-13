#!/usr/bin/python3

import contextlib
import cProfile
import os.path
import tempfile

from noisicaa import constants

def profile(file_base, func):
    profiler = cProfile.Profile()
    profiler.runcall(func)
    profile_path = os.path.join(
        tempfile.gettempdir(), file_base + '.prof')
    profiler.dump_stats(profile_path)
    print('Profile written to %s' % profile_path)


def profile_method(func):
    if constants.TEST_OPTS.ENABLE_PROFILER:
        def _wrapped(self):
            profile(self.id(), lambda: func(self))

        return _wrapped

    else:
        return func

