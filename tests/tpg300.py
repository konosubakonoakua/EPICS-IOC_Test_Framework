import unittest
import contextlib

from parameterized import parameterized

from utils.channel_access import ChannelAccess
from utils.ioc_launcher import get_default_ioc_dir
from utils.test_modes import TestModes
from utils.testing import get_running_lewis_and_ioc, skip_if_recsim
from enum import Enum
from itertools import product

DEVICE_PREFIX = "TPG300_01"

IOCS = [
    {
        "name": DEVICE_PREFIX,
        "directory": get_default_ioc_dir("TPG300"),
        "macros": {},
        "emulator": "tpg300",
    },
]

TEST_MODES = [TestModes.DEVSIM, TestModes.RECSIM]


class Units(Enum):
    mbar = 1
    Torr = 2
    Pa = 3


CHANNELS = "A1", "A2", "B1", "B2"
TEST_PRESSURES = 1.23, -10.23, 8, 1e-6, 1e+6


class Tpg300Tests(unittest.TestCase):
    """
    Tests for the TPG300.
    """

    def setUp(self):
        self._lewis, self._ioc = get_running_lewis_and_ioc("tpg300", DEVICE_PREFIX)
        self.ca = ChannelAccess(20, device_prefix=DEVICE_PREFIX, default_wait_time=0.0)

    def tearDown(self):
        self._connect_emulator()

    def _set_pressure(self, expected_pressure, channel):
        prop = "pressure_{}".format(channel.lower())
        pv = "SIM:PRESSURE"
        self._lewis.backdoor_set_on_device(prop, expected_pressure)
        self._ioc.set_simulated_value(pv, expected_pressure)

    def _connect_emulator(self):
        self._lewis.backdoor_run_function_on_device("connect")

    def _disconnect_emulator(self):
        self._lewis.backdoor_run_function_on_device("disconnect")

    def test_that_GIVEN_a_connected_emulator_WHEN_ioc_started_THEN_ioc_is_not_disabled(self):
        self.ca.assert_that_pv_is("DISABLE", "COMMS ENABLED")

    @skip_if_recsim("Requires emulator")
    def test_that_GIVEN_a_connected_emulator_WHEN_units_are_set_THEN_unit_is_the_same_as_backdoor(self):
        for unit in Units:
            expected_unit = unit.name
            self.ca.set_pv_value("UNITS:SP", expected_unit)
            self._lewis.assert_that_emulator_value_is("backdoor_get_unit", str(unit.value))
            self.ca.assert_that_pv_is("UNITS:SP", expected_unit)
            self.ca.assert_that_pv_is("UNITS", expected_unit)

    def test_that_GIVEN_a_connected_emulator_and_pressure_value_WHEN_set_pressure_is_set_THEN_the_ioc_is_updated(self):
        for expected_pressure, channel in product(TEST_PRESSURES, CHANNELS):
            pv = "PRESSURE_{}".format(channel)
            self._set_pressure(expected_pressure, channel)
            self.ca.assert_that_pv_is(pv, expected_pressure)

    @skip_if_recsim("Recsim is unable to simulate a disconnected device")
    def test_that_GIVEN_a_disconnected_emulator_WHEN_getting_pressure_THEN_INVALID_alarm_shows(self):
        self._disconnect_emulator()

        for channel in CHANNELS:
            pv = "PRESSURE_{}".format(channel)
            self.ca.assert_that_pv_alarm_is(pv, self.ca.Alarms.INVALID)

    def set_switching_function(self, function):
        self.ca.set_pv_value("FUNCTION", function)

    def set_switching_function_thresholds(self, threshold_low, threshold_high, circuit_assignment):
        self.ca.set_pv_value("FUNCTION:LOW:SP", threshold_low)
        self.ca.set_pv_value("FUNCTION:HIGH:SP", threshold_high)
        self.ca.set_pv_value("FUNCTION:ASSIGN:SP", circuit_assignment)
        self.ca.process_pv("FUNCTION:ASSIGN:SP:OUT")

    def check_switching_function_thresholds(self, function, thresholds, check_pv_is=True):
        assignments = ("No assignment", "A1", "A2", "B1", "B1", "A1 self-monitor", "A2 self-monitor", "B1 self-monitor", "B1 self-monitor")
        if check_pv_is:
            assignment = assignments[thresholds[2]]
            self.ca.assert_that_pv_is_number("FUNCTION:" + function + ":LOW:SP:RBV", thresholds[0], 0.001)
            self.ca.assert_that_pv_is_number("FUNCTION:" + function + ":HIGH:SP:RBV", thresholds[1], 0.001)
            self.ca.assert_that_pv_is("FUNCTION:" + function + ":ASSIGN:SP:RBV", assignment)

    @parameterized.expand([
        (('2', 0.5E2, 1.7E-5, 2), (0.5E2, 1.7E-5, 2)),
        (('A', 0.5534E55, 1.25E-5, 6), (5.5E54, 1.25E-5, 6)),
        (('B', 12E-215, 0.0, 3), (9.9E-99, 0.0, 3))
    ])
    @skip_if_recsim("Requires emulator")
    def test_GIVEN_function_thresholds_set_THEN_thresholds_readback_correct(self, function_set, function_read):
        self.set_switching_function("1")
        self.set_switching_function_thresholds(0.0, 0.0, 1)
        self.set_switching_function(function_set[0])
        self.set_switching_function_thresholds(function_set[1], function_set[2], function_set[3])
        self.check_switching_function_thresholds(str(function_set[0]), function_read)
        self.set_switching_function("1")
        self.check_switching_function_thresholds("1", (0.0, 0.0, 1))

    def check_switching_function_statuses(self, expected_statuses):
        self.ca.assert_that_pv_is("FUNCTION:STATUS:1:RB", str(expected_statuses[0]))
        self.ca.assert_that_pv_is("FUNCTION:STATUS:2:RB", str(expected_statuses[1]))
        self.ca.assert_that_pv_is("FUNCTION:STATUS:3:RB", str(expected_statuses[2]))
        self.ca.assert_that_pv_is("FUNCTION:STATUS:4:RB", str(expected_statuses[3]))

    @skip_if_recsim("Requires emulator")
    def test_GIVEN_function_status_set_THEN_readback_correct(self):
        function_statuses = [0, 0, 1, 1, 0, 1]
        self._lewis.backdoor_run_function_on_device("backdoor_set_switching_function_status", [function_statuses])
        self.check_switching_function_statuses(function_statuses)

    @skip_if_recsim("Requires emulator")
    def test_GIVEN_thresholds_settings_and_pressure_above_THEN_check_if_violation_detected(self):
        self._set_pressure(0, "A2")
        self.set_switching_function("3")
        self.set_switching_function_thresholds(5E2, 7.5E4, 2)
        self.ca.assert_that_pv_is("FUNCTION:3:THRESHOLD:BELOW", 1)
        self._set_pressure(6.43, "A2")
        self.ca.assert_that_pv_is("FUNCTION:3:THRESHOLD:BELOW", 1)
        self._set_pressure(501.0, "A2")
        self.ca.assert_that_pv_is("FUNCTION:3:THRESHOLD:BELOW", 0)

    @contextlib.contextmanager
    def _disconnect_device(self):
        self._disconnect_emulator()
        try:
            yield
        finally:
            self._connect_emulator()

    def check_alarm_status_rbvs(self, alarm):
        for channel in ("SEL", "1", "2", "3", "4", "A", "B"):
            self.ca.assert_that_pv_alarm_is("FUNCTION:" + channel + ":RB", alarm)
            self.ca.assert_that_pv_alarm_is("FUNCTION:" + channel + ":LOW:SP:RBV", alarm)
            self.ca.assert_that_pv_alarm_is("FUNCTION:" + channel + ":HIGH:SP:RBV", alarm)
            self.ca.assert_that_pv_alarm_is("FUNCTION:" + channel + ":ASSIGN:SP:RBV", alarm)

    def check_alarm_status_function_statuses(self, alarm):
        self.ca.assert_that_pv_alarm_is("FUNCTION:STATUS:RB", alarm)
        for channel in ("1", "2", "3", "4"):
            self.ca.assert_that_pv_alarm_is("FUNCTION:STATUS:" + channel + ":RB", alarm)


    @skip_if_recsim("Requires emulator")
    def test_WHEN_device_disconnected_THEN_rbv_values_go_into_alarm(self):
        self.check_alarm_status_rbvs(self.ca.Alarms.NONE)
        with self._disconnect_device():
            self.check_alarm_status_rbvs(self.ca.Alarms.INVALID)

        self.check_alarm_status_rbvs(self.ca.Alarms.NONE)

    @skip_if_recsim("Requires emulator")
    def test_WHEN_device_disconnected_THEN_function_statuses_go_into_alarm(self):
        self.check_alarm_status_function_statuses(self.ca.Alarms.NONE)
        with self._disconnect_device():
            self.check_alarm_status_function_statuses(self.ca.Alarms.INVALID)

        self.check_alarm_status_function_statuses(self.ca.Alarms.NONE)