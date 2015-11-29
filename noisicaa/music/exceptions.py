#!/usr/bin/python3


class Error(Exception):
    pass


class FileError(Error):
    pass


class FileOpenError(FileError):
    pass


class UnsupportedFileVersionError(FileError):
    pass


class CorruptedProjectError(FileError):
    pass
