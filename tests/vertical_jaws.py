import unittest

from utils.channel_access import ChannelAccess
from utils.ioc_launcher import IOCRegister, get_default_ioc_dir
from utils.test_modes import TestModes
from utils.testing import parameterized_list
from parameterized import parameterized

DEVICE_PREFIX = "GALIL_01"

# PV names for motors
MOTOR_N = "MOT:JAWS1:JN"
MOTOR_S = "MOT:JAWS1:JS"
MOTOR_N_SP = MOTOR_N + ":SP"
MOTOR_S_SP = MOTOR_S + ":SP"

# PV names for GALIL motors
UNDERLYING_MTR_NORTH = "MOT:MTR0101"
UNDERLYING_MTR_SOUTH = "MOT:MTR0102"

all_motors = [MOTOR_N, MOTOR_S,
              UNDERLYING_MTR_NORTH, UNDERLYING_MTR_SOUTH]

TEST_POSITIONS = [-5, 0, 10, 10e-1]

IOCS = [
    {
        "name": DEVICE_PREFIX,
        "directory": get_default_ioc_dir("GALIL"),
        "macros": {
            "MTRCTRL": "01",
        },
    },
]


TEST_MODES = [TestModes.RECSIM]


class VerticalJawsTests(unittest.TestCase):
    """
    Tests for vertical jaws
    """
    def setUp(self):
        self._ioc = IOCRegister.get_running("vertical_jaws")
        self.ca = ChannelAccess(default_timeout=30)

        [self.ca.assert_that_pv_exists(mot) for mot in all_motors]

    @parameterized.expand(parameterized_list(TEST_POSITIONS))
    def test_WHEN_south_jaw_setpoint_changed_THEN_south_jaw_moves(self, _, value):
        self.ca.assert_setting_setpoint_sets_readback(value, MOTOR_S, MOTOR_S_SP)

    @parameterized.expand(parameterized_list(TEST_POSITIONS))
    def test_WHEN_north_jaw_setpoint_changed_THEN_north_jaw_moves(self, _, value):
        self.ca.assert_setting_setpoint_sets_readback(value, MOTOR_N, MOTOR_N_SP)

    def test_GIVEN_jaws_closed_at_centre_WHEN_gap_opened_THEN_north_and_south_jaws_move(self):
        # GIVEN
        self.ca.assert_that_pv_is("MOT:JAWS1:VGAP", 0)
        self.ca.assert_that_pv_is("MOT:JAWS1:VCENT", 0)
        # WHEN
        self.ca.set_pv_value("MOT:JAWS1:VGAP:SP", 10)
        # THEN
        self.ca.assert_that_pv_is(MOTOR_S, -5)
        self.ca.assert_that_pv_is(MOTOR_N, 5)

    def test_GIVEN_jaws_open_WHEN_jaws_closed_THEN_jaws_close(self):
        # GIVEN
        self.ca.set_pv_value("MOT:JAWS1:VGAP:SP", 10)
        # WHEN
        self.ca.set_pv_value("MOT:JAWS1:VGAP:SP", 0)
        # THEN
        self.ca.assert_that_pv_is("MOT:JAWS1:VGAP", 0)
