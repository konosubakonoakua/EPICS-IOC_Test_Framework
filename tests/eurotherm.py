import unittest

import time
from utils.channel_access import ChannelAccess
from utils.test_modes import TestModes
from utils.testing import get_running_lewis_and_ioc, skip_if_recsim
from utils.ioc_launcher import get_default_ioc_dir, IOCRegister

# Internal Address of device (must be 2 characters)
ADDRESS = "A01"
# Numerical address of the device
ADDR_1 = 1
DEVICE = "EUROTHRM_01"
PREFIX = "{}:{}".format(DEVICE, ADDRESS)

# PV names
RBV_PV = "RBV"

IOCS = [
    {
        "name": DEVICE,
        "directory": get_default_ioc_dir("EUROTHRM"),
        "macros": {
            "ADDR": ADDRESS,
            "ADDR_1": ADDR_1
        },
        "emulator": "eurotherm",
    },
]

SENSOR_DISCONNECTED_VALUE = 1529


TEST_MODES = [TestModes.RECSIM, TestModes.DEVSIM]


class EurothermTests(unittest.TestCase):
    """
    Tests for the Eurotherm temperature controller.
    """

    def setUp(self):
        self._setup_lewis_and_channel_access()
        self._reset_device_state()

    def _setup_lewis_and_channel_access(self):
        self._lewis, self._ioc = get_running_lewis_and_ioc("eurotherm", DEVICE)
        self.ca = ChannelAccess(device_prefix=PREFIX)
        self.ca.wait_for(RBV_PV, timeout=30)
        self.ca.wait_for("CAL:SEL", timeout=10)
        self._lewis.backdoor_set_on_device("address", ADDRESS)

    def _reset_device_state(self):
        self.ca.set_pv_value("CAL:SEL", "None.txt")
        self.ca.assert_that_pv_is("CAL:RBV", "None.txt")

        intial_temp = 0.0

        self._set_setpoint_and_current_temperature(intial_temp)

        self._lewis.backdoor_set_on_device("ramping_on", False)
        self._lewis.backdoor_set_on_device("ramp_rate", 1.0)
        self.ca.set_pv_value("RAMPON:SP", 0)

        self._set_setpoint_and_current_temperature(intial_temp)
        self.ca.assert_that_pv_is("TEMP", intial_temp)
        # Ensure the temperature isn't being changed by a ramp any more
        self.ca.assert_pv_value_is_unchanged("TEMP", 5)

    def _set_setpoint_and_current_temperature(self, temperature):
        if IOCRegister.uses_rec_sim:
            self.ca.set_pv_value("SIM:TEMP:SP", temperature)
            self.ca.assert_that_pv_is("SIM:TEMP", temperature)
            self.ca.assert_that_pv_is("SIM:TEMP:SP", temperature)
            self.ca.assert_that_pv_is("SIM:TEMP:SP:RBV", temperature)
        else:
            self._lewis.backdoor_set_on_device("current_temperature", temperature)
            self._lewis.backdoor_set_on_device("ramp_setpoint_temperature", temperature)

    @skip_if_recsim("In rec sim this test fails")
    def test_WHEN_read_rbv_temperature_THEN_rbv_value_is_same_as_backdoor(self):
        expected_temperature = 10.0
        self._set_setpoint_and_current_temperature(expected_temperature)
        self.ca.assert_that_pv_is(RBV_PV, expected_temperature)

    @skip_if_recsim("In rec sim this test fails")
    def test_GIVEN_a_sp_WHEN_sp_read_rbv_temperature_THEN_rbv_value_is_same_as_sp(self):
        expected_temperature = 10.0
        self.ca.assert_setting_setpoint_sets_readback(expected_temperature, "SP:RBV", "SP")

    @skip_if_recsim("In rec sim this test fails")
    def test_WHEN_set_ramp_rate_in_K_per_min_THEN_current_temperature_reaches_set_point_in_expected_time(self):
        start_temperature = 5.0
        ramp_on = 1
        ramp_rate = 60.0
        setpoint_temperature = 25.0

        self._set_setpoint_and_current_temperature(start_temperature)
        self.ca.set_pv_value("TEMP:SP", start_temperature)

        self.ca.set_pv_value("RATE:SP", ramp_rate)
        self.ca.set_pv_value("RAMPON:SP", ramp_on)
        self.ca.set_pv_value("TEMP:SP", setpoint_temperature)

        start = time.time()
        self.ca.assert_that_pv_is_number("TEMP:SP:RBV", setpoint_temperature, timeout=60)
        end = time.time()
        self.assertAlmostEquals(end-start, 20, delta=1)

    @skip_if_recsim("In rec sim this test fails")
    def test_WHEN_sensor_disconnected_THEN_ramp_setting_is_disabled(self):
        self._lewis.backdoor_set_on_device("current_temperature", SENSOR_DISCONNECTED_VALUE)

        self.ca.assert_that_pv_is_number("RAMPON:SP.DISP", 1)

    @skip_if_recsim("In rec sim this test fails")
    def test_GIVEN_sensor_disconnected_WHEN_sensor_reconnected_THEN_ramp_setting_is_enabled(self):
        self._lewis.backdoor_set_on_device("current_temperature", SENSOR_DISCONNECTED_VALUE)

        self._lewis.backdoor_set_on_device("current_temperature", 0)

        self.ca.assert_that_pv_is_number("RAMPON:SP.DISP", 0)

    @skip_if_recsim("In rec sim this test fails")
    def test_GIVEN_ramp_was_off_WHEN_sensor_disconnected_THEN_ramp_is_off_and_cached_ramp_value_is_off(self):
        self.ca.set_pv_value("RAMPON:SP", 0)

        self._lewis.backdoor_set_on_device("current_temperature", SENSOR_DISCONNECTED_VALUE)

        self.ca.assert_that_pv_is("RAMPON", "OFF")
        self.ca.assert_that_pv_is("RAMPON:CACHE", "OFF")

    @skip_if_recsim("In rec sim this test fails")
    def test_GIVEN_ramp_was_on_WHEN_sensor_disconnected_THEN_ramp_is_off_and_cached_ramp_value_is_on(self):
        self.ca.set_pv_value("RAMPON:SP", 1)

        self._lewis.backdoor_set_on_device("current_temperature", SENSOR_DISCONNECTED_VALUE)

        self.ca.assert_that_pv_is("RAMPON", "OFF")
        self.ca.assert_that_pv_is("RAMPON:CACHE", "ON")

    @skip_if_recsim("In rec sim this test fails")
    def test_GIVEN_ramp_was_on_WHEN_sensor_disconnected_and_reconnected_THEN_ramp_is_on(self):
        self.ca.set_pv_value("RAMPON:SP", 1)

        self._lewis.backdoor_set_on_device("current_temperature", SENSOR_DISCONNECTED_VALUE)
        self.ca.assert_that_pv_is("RAMPON", "OFF")
        self._lewis.backdoor_set_on_device("current_temperature", 0)

        self.ca.assert_that_pv_is("RAMPON", "ON")

    def test_GIVEN_temperature_setpoint_followed_by_calibration_change_WHEN_same_setpoint_set_again_THEN_setpoint_readback_updates_to_set_value(self):

        # Arrange
        temperature = 50.0
        rbv_change_timeout = 10
        tolerance = 0.01
        self.ca.set_pv_value("RAMPON:SP", 0)
        self.ca.set_pv_value("CAL:SEL", "None.txt")
        self.ca.assert_that_pv_is("CAL:RBV", "None.txt")
        self.ca.set_pv_value("TEMP:SP", temperature)
        self.ca.assert_that_pv_is_number("TEMP:SP:RBV", temperature, tolerance=tolerance, timeout=rbv_change_timeout)
        self.ca.set_pv_value("CAL:SEL", "C006.txt")
        self.ca.assert_that_pv_is_not_number("TEMP:SP:RBV", temperature, tolerance=tolerance, timeout=rbv_change_timeout)

        # Act
        self.ca.set_pv_value("TEMP:SP", temperature)

        # Assert
        self.ca.assert_that_pv_is_number("TEMP:SP:RBV", temperature, tolerance=tolerance, timeout=rbv_change_timeout)
