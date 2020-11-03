import unittest

from utils.test_modes import TestModes
from utils.ioc_launcher import EPICS_TOP
from utils.emulator_launcher import DAQMxEmulatorLauncher
from common_tests.DAQmx import DAQmxTests, DEVICE_PREFIX

import os

IOCS = [
    {
        "name": DEVICE_PREFIX,
        "directory": os.path.join(EPICS_TOP, "support", "DAQmxBase", "master", "iocBoot",  "iocDAQmx"),
        "emulator": DEVICE_PREFIX,
        "emulator_launcher_class": DAQMxEmulatorLauncher,
        "pv_for_existence": "ACQUIRE",
        "macros": {
            "DAQPOSTIOCINITCMD": "DAQmxStart('myport1')",
            "DAQMODE": "MONSTER TerminalDiff N=1 F=1000"
        },
        "started_text": "DAQmxStart",
    },
]


TEST_MODES = [TestModes.DEVSIM]


class DAQmxMonsterTests(DAQmxTests, unittest.TestCase):
    """
    Test all DAQMx tests using monster mode.
    """
    pass


