from __future__ import division

import os
import unittest
import shutil
import time
from contextlib import contextmanager

from genie_python import genie as g

from utils.channel_access import ChannelAccess
from utils.ioc_launcher import get_default_ioc_dir

from utils.test_modes import TestModes
from utils.ioc_launcher import IOCRegister

AUTOSAVE_DIR = os.path.join("C:/", "Instrument", "var", "autosave", "CAENV895_01_DEVSIM")

DEVICE_PREFIX = "CAENV895_01"

IOCS = [
    {
        "name": DEVICE_PREFIX,
        "directory": get_default_ioc_dir("CAENV895"),
        "pv_for_existence": "CR0:BOARD_ID",
        "macros": {
            "DEFAULTCFG": "ioctestdefaults",
        },
        "environment_vars": {
            "DEFAULTCFG": "ioctestdefaults",
        },

    },
]

DEFAULTS_FILENAME = "vmeconfig_ioctestdefaults.cfg"
TEST_DEFAULTS_FILE = f"test_data/caenv895/{DEFAULTS_FILENAME}"
AUTOSAVE_DEFAULTS_FILE = os.path.join(AUTOSAVE_DIR, DEFAULTS_FILENAME)


# copy a configmenu configuration "ioctestdefaults" ready for use by ioc
def pre_ioc_launch_hook():
    """
    A hook that happens before launching the ioc. Write a defaults config file for autosave to use.
    """
    os.makedirs(AUTOSAVE_DIR, exist_ok=True)
    defaults_contents: str = get_defaults_file_as_string()
    defaults_contents_with_pv_prefix = defaults_contents.replace("{pv_prefix}", g.my_pv_prefix)
    write_defaults_to_autosave_configuration(defaults_contents_with_pv_prefix)


def get_defaults_file_as_string() -> str:
    """
    Gets a contents of a file as a string.
    :return: Te string contents of the file.
    """
    with open(TEST_DEFAULTS_FILE, "r") as defaults_file:
        return defaults_file.read()


def write_defaults_to_autosave_configuration(defaults_contents: str):
    """
    Write the defaults_contents to the autosave defaults file.
    :param defaults_contents: The contents to write to file.
    """
    with open(AUTOSAVE_DEFAULTS_FILE, "w+") as defaults_file:
        defaults_file.write(defaults_contents)


TEST_MODES = [TestModes.DEVSIM]


class CAENv895Tests(unittest.TestCase):
    """
    Tests for CAENv895
    """

    def setUp(self):
        self.ca = ChannelAccess(default_timeout=30, device_prefix=DEVICE_PREFIX)
        self.ca_np = ChannelAccess(default_timeout=30) # no device name prefix in PV
        self._ioc = IOCRegister.get_running(DEVICE_PREFIX)
        self.ca.assert_that_pv_exists("CR0:BOARD_ID")

    def test_GIVEN_ioc_WHEN_startup_complete_THEN_defaults_loaded(self):
        self.ca.assert_that_pv_is("CR0:CRATE", 0)
        self.ca.assert_that_pv_is("CR0:BOARD_ID", 0)
        # check values from configmenu config "ioctestdefaults" file loaded in pre_ioc_launch_hook()
        self.ca.assert_that_pv_is("CR0:C0:CH3:THOLD:SP", 75)
        self.ca.assert_that_pv_is("CR0:C1:CH0:ENABLE:SP", "YES")
        self.ca_np.assert_that_pv_is("AS:{}:vmeconfigMenu:currName".format(DEVICE_PREFIX), "ioctestdefaults")
        self.ca_np.assert_that_pv_is("AS:{}:vmeconfigMenu:status".format(DEVICE_PREFIX), "Success")
        self.ca_np.assert_that_pv_is("AS:{}:vmeconfigMenu:busy".format(DEVICE_PREFIX), "Done")

    def test_GIVEN_output_widths_WHEN_output_widths_set_THEN_width_read_back(self):
        # GIVEN
        width_0_to_7 = 10
        width_8_to_15 = 13
        # WHEN
        self.ca.set_pv_value("CR0:C0:OUT:WIDTH:0_TO_7:SP", width_0_to_7)
        self.ca.set_pv_value("CR0:C0:OUT:WIDTH:8_TO_15:SP", width_8_to_15)
        # THEN
        self.ca.assert_that_pv_is("SIM:CR0:C0:OUT:WIDTH:0_TO_7", width_0_to_7)
        self.ca.assert_that_pv_is("SIM:CR0:C0:OUT:WIDTH:8_TO_15", width_8_to_15)
