import unittest
import os

from utils.channel_access import ChannelAccess
from utils.ioc_launcher import IOCRegister, get_default_ioc_dir
from utils.test_modes import TestModes
from utils.testing import parameterized_list
from parameterized import parameterized
from collections import OrderedDict

MTR_01 = "GALIL_01"

# Tests will fail if JAWS support module is not up to date and built
test_path = os.path.realpath(
    os.path.join(os.getenv("EPICS_KIT_ROOT"), "support", "sampleChanger", "master", "settings", "sans_sample_changer"))

AXES = ["SAMPLECHANGER:X", "SAMPLECHANGER:Y"]

IOCS = [
    {
        "name": MTR_01,
        "directory": get_default_ioc_dir("GALIL"),
        "pv_for_existence": "MTR0101",
        "custom_prefix": "MOT",
        "macros": {
            "MTRCTRL": "01",
            "GALILCONFIGDIR": test_path.replace("\\", "/"),
        },
    },
]

TEST_MODES = [TestModes.DEVSIM]


class SampleChangerTests(unittest.TestCase):
    """
    Base class for jaws tests
    """
    def setUp(self):
        self.ca = ChannelAccess(default_timeout=30)

        self.ca.assert_that_pv_exists("SAMPCHNG:SLOT")
        for axis in AXES:
            self.ca.assert_that_pv_exists("MOT:{}".format(axis))

    @parameterized.expand(parameterized_list([
        {
            "slot_name": "",
            "positions_exist": ["{}CB".format(n) for n in range(1, 14+1)] + ["{}CT".format(n) for n in range(1, 14+1)],
            "positions_not_exist": [],
        },
        {
            "slot_name": "CT",
            "positions_exist": ["{}CT".format(n) for n in range(1, 14+1)],
            "positions_not_exist": ["{}CB".format(n) for n in range(1, 14+1)],
        },
        {
            "slot_name": "CB",
            "positions_exist": ["{}CB".format(n) for n in range(1, 14+1)],
            "positions_not_exist": ["{}CT".format(n) for n in range(1, 14+1)],
        },
    ]))
    def test_WHEN_slot_set_to_empty_string_THEN_all_positions_listed(self, _, settings):

        self.ca.assert_setting_setpoint_sets_readback(readback_pv="SAMPCHNG:SLOT", value=settings["slot_name"])

        for pos in settings["positions_exist"]:
            self.ca.assert_that_pv_value_causes_func_to_return_true("LKUP:SAMPLE:POSITIONS",
                                                                    func=lambda val: pos in val)

        for pos in settings["positions_not_exist"]:
            self.ca.assert_that_pv_value_causes_func_to_return_true("LKUP:SAMPLE:POSITIONS",
                                                                    func=lambda val: pos not in val)
