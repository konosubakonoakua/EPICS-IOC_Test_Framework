import unittest

from parameterized import parameterized

from common_tests.tpgx00 import Tpgx00Base
from utils.ioc_launcher import get_default_ioc_dir
from utils.test_modes import TestModes
from utils.testing import skip_if_recsim, parameterized_list
from enum import Enum

from genie_python.genie_cachannel_wrapper import InvalidEnumStringException


DEVICE_PREFIX = "TPG300_01"

IOCS = [
    {
    "name": DEVICE_PREFIX,
    "directory": get_default_ioc_dir("TPG300"),
    "macros": {
        "MODEL": "500"
    },
    "emulator": "tpgx00",
    "lewis_protocol": "tpg500",
    },
]


TEST_MODES = [TestModes.DEVSIM, TestModes.RECSIM]

SWITCHING_FUNCTIONS = ("SEL", "1", "2", "3", "4")

class SFAssignment(Enum):
    OFF         = (0, "Switched off")
    A1          = (1, "A1")
    A2          = (2, "A2")
    B1          = (3, "B1")
    B2          = (4, "B2")
    ON          = (5, "Switched on")
    
    def __new__(cls, value, desc):
        obj = object.__new__(cls)
        obj._value_ = value
        obj.desc = desc
        return obj


class Units(Enum):
    hPascal = 0
    mbar = 1
    Torr = 2
    Pa = 3
    Micron = 4
    Volt = 5
    Ampere = 6


class Tpg500Tests(Tpgx00Base, unittest.TestCase):
    """
    Tests for the TPG500.
    """

    def get_prefix(self):
        return DEVICE_PREFIX
    
    def get_units(self):
        return Units

    def get_sf_assignment(self):
        return SFAssignment
        
    def get_switching_fns(self):
        return SWITCHING_FUNCTIONS
    
    def _check_alarm_status_function_statuses(self, alarm):
        self.ca.assert_that_pv_is("FUNCTION:STATUS:RB", "Unavailable")
        for channel in ("1", "2", "3", "4"):
            self.ca.assert_that_pv_alarm_is("FUNCTION:STATUS:" + channel + ":RB", alarm)

    @parameterized.expand(parameterized_list(['A', 'B']))
    @skip_if_recsim("Requires emulator")
    def test_WHEN_invalid_switching_function_set_THEN_pv_goes_into_alarm(self, _, switching_func):
        with self.assertRaises(InvalidEnumStringException):
            self.ca.set_pv_value("FUNCTION", switching_func)
        self.ca.assert_that_pv_is_not("FUNCTION", switching_func)
        self._lewis.assert_that_emulator_value_is_not("backdoor_get_switching_fn", switching_func)

    # Tests to check the various inconsistencies between the 500 manual & hardware have been handled
    @skip_if_recsim("Requires emulator")
    def test_WHEN_ioc_is_on_THEN_error_status_invalid(self):
        self.ca.assert_that_pv_alarm_is("ERROR", self.ca.Alarms.INVALID)
    
    @parameterized.expand(parameterized_list(["1", "2", "3", "4"]))
    def test_WHEN_ioc_is_on_THEN_each_relay_contact_status_invalid(self, _, channel):
        self.ca.assert_that_pv_alarm_is("FUNCTION:STATUS:" + channel + ":RB", self.ca.Alarms.INVALID)

    @skip_if_recsim("Requires emulator")
    def test_WHEN_device_disconnected_THEN_function_statuses_go_into_alarm(self):
        self._check_alarm_status_function_statuses(self.ca.Alarms.INVALID)
        with self._disconnect_device():
            self._check_alarm_status_function_statuses(self.ca.Alarms.INVALID)
        
        self._check_alarm_status_function_statuses(self.ca.Alarms.INVALID)

    def test_WHEN_ioc_is_on_THEN_status_rb_reports_unavailable(self):
        self.ca.assert_that_pv_is("FUNCTION:STATUS:RB", "Unavailable")
