import unittest
from unittest import skipIf

from utils.channel_access import ChannelAccess
from utils.ioc_launcher import IOCRegister
from utils.testing import get_running_lewis_and_ioc

import math


class FermichopperTests(unittest.TestCase):
    """
    Tests for the Fermi Chopper IOC.
    """

    valid_commands = ["0001", "0002", "0003", "0006", "0007"]

    def setUp(self):
        self._lewis, self._ioc = get_running_lewis_and_ioc("fermichopper")

        self.ca = ChannelAccess(15)
        self.ca.wait_for("FERMCHOP_01:DISABLE", timeout=30)

    def test_WHEN_ioc_is_started_THEN_ioc_is_not_disabled(self):
        self.ca.assert_that_pv_is("FERMCHOP_01:DISABLE", "COMMS ENABLED")

    @skipIf(IOCRegister.uses_rec_sim, "In rec sim this test fails")
    def test_WHEN_last_command_is_set_via_backdoor_THEN_pv_updates(self):
        for value in self.valid_commands:
            self._lewis.backdoor_command(["device", "last_command", "'" + value + "'"])
            self.ca.assert_that_pv_is("FERMCHOP_01:LASTCOMMAND", value)

    @skipIf(IOCRegister.uses_rec_sim, "In rec sim this test fails")
    def test_WHEN_last_command_is_set_THEN_readback_updates(self):
        for value in self.valid_commands:
            self.ca.set_pv_value("FERMCHOP_01:COMMAND:SP", value)
            self.ca.assert_that_pv_is("FERMCHOP_01:LASTCOMMAND", value)
