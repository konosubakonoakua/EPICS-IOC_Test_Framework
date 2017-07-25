import unittest
from unittest import skipIf

from utils.channel_access import ChannelAccess
from utils.ioc_launcher import IOCRegister
from utils.testing import get_running_lewis_and_ioc



class OutputMode(object):
    VOLTAGE = "VOLTAGE"
    CURRENT = "CURRENT"

class OutputStatus(object):
    ON = "ON"
    OFF = "OFF"

class UnitFlags(object):
    VOLTAGE = 0
    CURRENT = 1
    ON = 1
    OFF = 0



class KepcoTests(unittest.TestCase):
    """
    Tests for the KEPCO.
    """

    def setUp(self):
        self._lewis, self._ioc = get_running_lewis_and_ioc("kepco")
        self.ca = ChannelAccess(default_timeout=30)
        self.ca.wait_for("KEPCO_01:VOLTAGE", timeout=30)

    def _write_voltage(self, expected_voltage):
        self._lewis.backdoor_set_on_device("voltage", expected_voltage)
        self._ioc.set_simulated_value("KEPCO_01:SIM:VOLTAGE", expected_voltage)

    def _write_current(self, expected_current):
        self._lewis.backdoor_set_on_device("current", expected_current)
        self._ioc.set_simulated_value("KEPCO_01:SIM:CURRENT", expected_current)

    def _set_output_mode(self, expected_output_mode):
        self._lewis.backdoor_set_on_device("output_mode", expected_output_mode)
        self._ioc.set_simulated_value("KEPCO_01:SIM:OUTPUTMODE", expected_output_mode)

    def _set_output_status(self, expected_output_status):
        self._lewis.backdoor_set_on_device("output_status", expected_output_status)

    def test_GIVEN_voltage_set_WHEN_read_THEN_voltage_is_as_expected(self):
        expected_voltage = 1.2
        self._write_voltage(expected_voltage)
        self.ca.assert_that_pv_is("KEPCO_01:VOLTAGE", expected_voltage)

    def test_GIVEN_current_set_WHEN_read_THEN_current_is_as_expected(self):
        expected_current = 1.5
        self._write_current(expected_current)
        self.ca.assert_that_pv_is("KEPCO_01:CURRENT", expected_current)

    def test_GIVEN_setpoint_voltage_set_WHEN_read_THEN_setpoint_voltage_is_as_expected(self):

        # Get current Voltage
        current_voltage = self.ca.get_pv_value("KEPCO_01:VOLTAGE")
        # Set new Voltage via SP
        self.ca.set_pv_value("KEPCO_01:VOLTAGE:SP", current_voltage + 5)
        # Check SP RBV matches new current
        self.ca.assert_that_pv_is("KEPCO_01:VOLTAGE:SP:RBV", current_voltage + 5)

    def test_GIVEN_setpoint_current_set_WHEN_read_THEN_setpoint_current_is_as_expected(self):

        # Get current current
        current_current = self.ca.get_pv_value("KEPCO_01:CURRENT")
        # Set new Current via SP
        self.ca.set_pv_value("KEPCO_01:CURRENT:SP", current_current + 5)
        # Check SP RBV matches new current
        self.ca.assert_that_pv_is("KEPCO_01:CURRENT:SP:RBV", current_current + 5)

    def test_GIVEN_output_mode_set_WHEN_read_THEN_output_mode_is_as_expected(self):
        expected_output_mode_flag = UnitFlags.CURRENT
        expected_output_mode_str =  OutputMode.CURRENT

        self._set_output_mode(expected_output_mode_flag)
        # Check OUTPUT MODE matches new OUTPUT MODE
        self.ca.assert_that_pv_is("KEPCO_01:OUTPUTMODE", expected_output_mode_str)

    def test_GIVEN_output_status_set_WHEN_read_THEN_output_STATUS_is_as_expected(self):
        expected_output_status_flag = UnitFlags.ON
        expected_output_status_str = OutputStatus.ON

        self.ca.set_pv_value("KEPCO_01:OUTPUTSTATUS:SP", expected_output_status_flag)

        self.ca.assert_that_pv_is("KEPCO_01:OUTPUTSTATUS:SP:RBV", expected_output_status_str)






