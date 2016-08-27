#!/usr/bin/python3

class Mutation(object):
    pass


class AddNodeDescription(Mutation):
    def __init__(self, uri, description):
        self.uri = uri
        self.description = description

    def __str__(self):
        return '<AddNodeDescription uri="%s">' % self.uri


class RemoveNodeDescription(Mutation):
    def __init__(self, uri):
        self.uri = uri

    def __str__(self):
        return '<RemoveNodeDescription uri="%s">' % self.uri


