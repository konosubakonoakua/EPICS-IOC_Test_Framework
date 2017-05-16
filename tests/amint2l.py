import unittest

from utils.channel_access import ChannelAccess
from utils.testing import get_running_lewis_and_ioc


class Amint2lTests(unittest.TestCase):
    """
    Tests for the AM Int2-L
    """

    def setUp(self):
        self._lewis, self._ioc = get_running_lewis_and_ioc("amint2l")

        self.ca = ChannelAccess()
        self.ca.wait_for("AMINT2L_01:PRESSURE")

    def _set_pressure(self, expected_pressure):
        self._lewis.backdoor_set_on_device("pressure", expected_pressure)
        self._ioc.set_simulated_value("AMINT2L_01:PRESSURE:SIM", expected_pressure)

    def test_GIVEN_pressure_set_WHEN_read_THEN_pressure_is_as_expected(self):
        expected_pressure = 1.23
        self._set_pressure(expected_pressure)

        self.ca.assert_that_pv_is("AMINT2L_01:PRESSURE", expected_pressure)
        self.ca.assert_pv_alarm_is("AMINT2L_01:PRESSURE", ChannelAccess.ALARM_NONE)

    def test_GIVEN_negative_pressure_set_WHEN_read_THEN_pressure_is_as_expected(self):
        expected_pressure = -123.34
        self._set_pressure(expected_pressure)

        self.ca.assert_that_pv_is("AMINT2L_01:PRESSURE", expected_pressure)

    def test_GIVEN_pressure_with_no_decimal_places_set_WHEN_read_THEN_pressure_is_as_expected(self):
        expected_pressure = 7
        self._set_pressure(expected_pressure)

        self.ca.assert_that_pv_is("AMINT2L_01:PRESSURE", expected_pressure)

    def test_GIVEN_pressure_over_range_set_WHEN_read_THEN_error(self):
        expected_pressure = "OR"
        self._set_pressure(expected_pressure)

        self.ca.assert_pv_alarm_is("AMINT2L_01:PRESSURE", ChannelAccess.ALARM_CALC)
        self.ca.assert_that_pv_is("AMINT2L_01:RANGE:ERROR", "Over Range")

    def test_GIVEN_pressure_under_range_set_WHEN_read_THEN_error(self):
        expected_pressure = "UR"
        self._set_pressure(expected_pressure)

        self.ca.assert_pv_alarm_is("AMINT2L_01:PRESSURE", ChannelAccess.ALARM_CALC)
        self.ca.assert_that_pv_is("AMINT2L_01:RANGE:ERROR", "Under Range")

    def test_GIVEN_device_disconnected_WHEN_read_THEN_pv_shows_disconnect(self):
        self._lewis.backdoor_set_on_device("pressure", None)

        self.ca.assert_pv_alarm_is("AMINT2L_01:PRESSURE", ChannelAccess.ALARM_DISCONNECTED)
