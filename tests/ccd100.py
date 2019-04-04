import unittest
from time import sleep

from utils.test_modes import TestModes
from utils.channel_access import ChannelAccess
from utils.ioc_launcher import get_default_ioc_dir
from utils.testing import get_running_lewis_and_ioc, assert_log_messages, skip_if_recsim
from parameterized import parameterized

# Device prefix
DEVICE_A_PREFIX = "CCD100_01"
DEVICE_E_PREFIX = "CCD100_02"

EMULATOR_DEVICE = "CCD100"

IOCS = [
    {
        "name": DEVICE_A_PREFIX,
        "directory": get_default_ioc_dir("CCD100"),
        "emulator": EMULATOR_DEVICE,
        "emulator_id": DEVICE_A_PREFIX
    },

    {
        "name": DEVICE_E_PREFIX,
        "directory": get_default_ioc_dir("CCD100", iocnum=2),
        "emulator": EMULATOR_DEVICE,
        "emulator_id": DEVICE_E_PREFIX,
        "macros": {"ADDRESS": "e"}
    },
]


TEST_MODES = [TestModes.RECSIM, TestModes.DEVSIM]


def set_up_connections(device):
    _lewis, _ioc = get_running_lewis_and_ioc(EMULATOR_DEVICE, device)

    _lewis.backdoor_set_on_device('connected', True)
    _lewis.backdoor_set_on_device("is_giving_errors", False)

    return _lewis, _ioc, ChannelAccess(device_prefix=device)


class CCD100Tests(unittest.TestCase):
    """
    General tests for the CCD100.
    """
    def setUp(self):
        self._lewis, self._ioc, self.ca = set_up_connections(DEVICE_A_PREFIX)

    @parameterized.expand([("0", 0), ("1.23", 1.23), ("10", 10)])
    def test_GIVEN_setpoint_set_WHEN_readback_THEN_readback_is_same_as_setpoint(self, _, point):
        self.ca.set_pv_value("READING:SP", point)
        self.ca.assert_that_pv_is("READING:SP:RBV", point)

    @skip_if_recsim("Can not test disconnection in rec sim")
    def test_GIVEN_device_not_connected_WHEN_get_status_THEN_alarm(self):
        self._lewis.backdoor_set_on_device('connected', False)
        self.ca.assert_that_pv_alarm_is('READING', ChannelAccess.Alarms.INVALID)


class CCD100SecondDeviceTests(CCD100Tests):
    """
    Tests for the second CCD100 device.
    """
    def setUp(self):
        self._lewis, self._ioc, self.ca = set_up_connections(DEVICE_E_PREFIX)
        self._lewis.backdoor_set_on_device("address", "e")


class CCD100LogTests(unittest.TestCase):
    """
    Tests for the log messages produced by CCD100.
    """
    NUM_OF_PVS = 3

    def setUp(self):
        self._lewis, self._ioc, self.ca = set_up_connections(DEVICE_A_PREFIX)

    def _set_error_state(self, state):
        self._lewis.backdoor_set_on_device("is_giving_errors", state)
        sleep(2)  # Wait for previous errors to get logged

    @skip_if_recsim("Cannot check log messages in rec sim")
    def test_GIVEN_not_in_error_WHEN_put_in_error_THEN_three_log_messages_per_pv_logged_in_five_secs(self):
        self._set_error_state(False) # Should already be out of error state but doing this again to ingest logs
        with assert_log_messages(self._ioc, self.NUM_OF_PVS*3, 5) as log:
            self._set_error_state(True)

    @skip_if_recsim("Cannot check log messages in rec sim")
    def test_GIVEN_in_error_WHEN_error_cleared_THEN_one_log_message_per_pv_logged(self):
        self._set_error_state(True)
        with assert_log_messages(self._ioc, self.NUM_OF_PVS*1):
            self._set_error_state(False)

    @skip_if_recsim("Cannot check log messages in rec sim")
    def test_GIVEN_in_error_WHEN_error_string_changed_THEN_three_log_message_per_pv_logged_in_five_secs(self):
        self._lewis.backdoor_set_on_device("out_error", "OLD_ERROR")
        self._set_error_state(True)

        new_error = "A_NEW_ERROR"
        with assert_log_messages(self._ioc, self.NUM_OF_PVS*3, 5) as log:
            self._lewis.backdoor_set_on_device("out_error", new_error)

        self.assertTrue(new_error in log.messages[-1])
