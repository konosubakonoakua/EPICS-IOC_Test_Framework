import unittest
import parameterized

from utils.channel_access import ChannelAccess
from utils.ioc_launcher import get_default_ioc_dir
from utils.test_modes import TestModes
from utils.testing import get_running_lewis_and_ioc, skip_if_recsim


DEVICE_PREFIX = "RKNDIO_01"


IOCS = [
    {
        "name": DEVICE_PREFIX,
        "directory": get_default_ioc_dir("RKNDIO"),
        "macros": {},
        "emulator": "rkndio",
    },
]


TEST_MODES = [TestModes.DEVSIM] #, TestModes.RECSIM]


class RkndioVersionTests(unittest.TestCase):
    """
    Tests for the Rkndio IOC.
    """
    def setUp(self):
        self._lewis, self._ioc = get_running_lewis_and_ioc("rkndio", DEVICE_PREFIX)
        self.ca = ChannelAccess(20, device_prefix=DEVICE_PREFIX)
        self._connect_emulator()
        self.ca.assert_that_pv_exists("IDN")

    def _connect_emulator(self):
        self._lewis.backdoor_run_function_on_device("connect")

    def _disconnect_emulator(self):
        self._lewis.backdoor_run_function_on_device("disconnect")

    def test_that_we_can_receive_the_correct_IDN(self):
        # When:
        self.ca.process_pv("IDN")

        # Then:
        self.ca.assert_that_pv_is("IDN", "RIKENFE Prototype v1.0", timeout=100)

    @skip_if_recsim("Recsim is unable to simulate a disconnected device")
    def test_that_GIVEN_a_disconnected_emulator_WHEN_getting_pressure_THEN_INVALID_alarm_shows(self):
        # Given:
        self._disconnect_emulator()

        # When:
        self.ca.process_pv("IDN")

        # Then:
        self.ca.assert_that_pv_alarm_is("IDN", self.ca.Alarms.INVALID)
