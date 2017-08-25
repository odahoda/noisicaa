from libcpp.memory cimport unique_ptr
from .status cimport *
from .processor cimport *

import unittest


class TestProcessor(unittest.TestCase):
    def test_id(self):
        cdef unique_ptr[Processor] processor1
        processor1.reset(Processor.create(b'null'))
        self.assertTrue(processor1.get() != NULL)

        cdef unique_ptr[Processor] processor2
        processor2.reset(Processor.create(b'null'))
        self.assertTrue(processor2.get() != NULL)

        self.assertNotEqual(processor1.get().id(), processor2.get().id())
