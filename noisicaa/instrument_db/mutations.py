#!/usr/bin/python3

class Mutation(object):
    pass


class AddInstrumentDescription(Mutation):
    def __init__(self, description):
        self.description = description

    def __str__(self):
        return '<AddInstrumentDescription uri="%s">' % self.description.uri


class RemoveInstrumentDescription(Mutation):
    def __init__(self, uri):
        self.uri = uri

    def __str__(self):
        return '<RemoveInstrumentDescription uri="%s">' % self.uri


