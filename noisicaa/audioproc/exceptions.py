#!/usr/bin/python3

class Error(Exception):
    pass

class EndOfStreamError(Error):
    pass

class SetupError(Error):
    pass
