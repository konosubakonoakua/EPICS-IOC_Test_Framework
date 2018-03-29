import unittest

from utils.channel_access import ChannelAccess
from utils.ioc_launcher import get_default_ioc_dir, IOCRegister, EPICS_TOP
from utils.test_modes import TestModes
from utils.testing import get_running_lewis_and_ioc, skip_if_recsim
import os


IOC_PREFIX = "INHIBITR_01"

SIMPLE_VALUE_ONE = "TE:NDW1801:SIMPLE:VALUE1:SP"
SIMPLE_VALUE_TWO = "TE:NDW1801:SIMPLE:VALUE2:SP"

IOCS = [
    {
        "name": IOC_PREFIX,
        "directory": get_default_ioc_dir("INHIBITR"),
        "macros": {
            "PVONE": SIMPLE_VALUE_ONE,
            "PVTWO": SIMPLE_VALUE_TWO,
            "PVONE_DISP": "{}.DISP".format(SIMPLE_VALUE_ONE),
            "PVTWO_DISP": "{}.DISP".format(SIMPLE_VALUE_TWO),
        },
    },
    {
        "name": "SIMPLE",
        "directory": os.path.join(EPICS_TOP, "ISIS", "SimpleIoc", "master", "iocBoot", "iocsimple"),
        "macros": {},
    },
]


TEST_MODES = [TestModes.RECSIM]


class InhibitrTests(unittest.TestCase):
    """
    Tests for the Inhibitr IOC.
    """

    def setUp(self):
        self._ioc = IOCRegister.get_running(IOC_PREFIX)
        self.ca = ChannelAccess(20)
        self.values = ["SIMPLE:VALUE1:SP", "SIMPLE:VALUE2:SP"]

    def reset_values_to_zero(self):
        for val in self.values:
            self.ca.set_pv_value(val, 0)

    def test_GIVEN_both_inputs_are_zero_WHEN_setting_either_input_THEN_this_is_allowed(self):
        self.reset_values_to_zero()
        for val in self.values:
            self.ca.assert_that_pv_is("{}.DISP".format(val), "0")

    def test_GIVEN_one_input_is_one_WHEN_setting_other_value_to_one_THEN_this_is_not_allowed(self):
        self.reset_values_to_zero()
        self.ca.set_pv_value("SIMPLE:VALUE1:SP", 1)
        # When value1 is set to zero, the disallowed value of value2 should be 1
        # i.e 'Not allowed to set this value to 1'
        self.ca.assert_that_pv_is("SIMPLE:VALUE2:SP.DISP", "1")
