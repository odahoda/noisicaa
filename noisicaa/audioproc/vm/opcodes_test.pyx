from libcpp.memory cimport unique_ptr

import unittest
import sys

from noisicaa.core.status cimport *
from .spec cimport *
from .vm cimport *
from .opcodes cimport *

class TestOpCodes(unittest.TestCase):
    def test_opcode_field_matches(self):
        for i in range(<int>NUM_OPCODES):
            self.assertEqual(opspecs[i].opcode, i)
