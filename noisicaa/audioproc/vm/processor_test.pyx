from libcpp.memory cimport unique_ptr

import unittest

from noisicaa.core.status cimport *
from .processor cimport *
from .host_data cimport *


class TestProcessor(unittest.TestCase):
    def test_id(self):
        cdef unique_ptr[HostData] host_data
        host_data.reset(new HostData())

        cdef StatusOr[Processor*] stor_processor = Processor.create(
            b'test_node', host_data.get(), b'null')
        check(stor_processor)
        cdef unique_ptr[Processor] processor1
        processor1.reset(stor_processor.result())

        stor_processor = Processor.create(
            b'test_node', host_data.get(), b'null')
        cdef unique_ptr[Processor] processor2
        processor2.reset(stor_processor.result())

        self.assertNotEqual(processor1.get().id(), processor2.get().id())
