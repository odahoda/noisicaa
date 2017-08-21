from libcpp.memory cimport unique_ptr
from .status cimport *
from .spec cimport *
from .vm cimport *
from .opcodes cimport *

import unittest
import sys

class TestOpCodes(unittest.TestCase):
    def test_opcode_field_matches(self):
        for i in range(<int>NUM_OPCODES):
            self.assertEqual(opspecs[i].opcode, i)
