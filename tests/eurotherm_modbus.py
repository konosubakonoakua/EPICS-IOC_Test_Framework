import unittest

from parameterized import parameterized

from utils.test_modes import TestModes
from utils.ioc_launcher import get_default_ioc_dir, ProcServLauncher
from common_tests.eurotherm import EurothermBaseTests, PID_TEST_VALUES, TEST_VALUES
from utils.testing import skip_if_recsim

from utils.testing import parameterized_list

# Internal Address of device (must be 2 characters)
ADDRESS = "A01"
# Numerical address of the device
ADDR_1 = "01" # Leave this value as 1 when changing the ADDRESS value above - hard coded in LEWIS emulator
DEVICE = "EUROTHRM_01"

EMULATOR_DEVICE = "eurotherm"

IOCS = [
    {
        "name": DEVICE,
        "directory": get_default_ioc_dir("EUROTHRM"),
        "ioc_launcher_class": ProcServLauncher,
        "macros": {
            "COMMS_MODE": "modbus",
            "NEEDLE_VALVE": "yes",
            "ADDR": ADDRESS,
            "ADDR_1": ADDR_1,
            "ADDR_2": "",
            "ADDR_3": "",
            "ADDR_4": "",
            "ADDR_5": "",
            "ADDR_6": "",
            "ADDR_7": "",
            "ADDR_8": "",
            "ADDR_9": "",
            "ADDR_10": "",
            "TEMP_SCALING_1": "0.1",
            "P_SCALING_1": "1",
            "I_SCALING_1": "1",
            "D_SCALING_1": "1",
            "OUTPUT_SCALING_1": "0.1",
        },
        "emulator": EMULATOR_DEVICE,
        "lewis_protocol": "eurotherm_modbus",
    },
]


TEST_MODES = [TestModes.DEVSIM, TestModes.RECSIM]

class EurothermModbusTests(EurothermBaseTests, unittest.TestCase):
    def get_device(self):
        return DEVICE

    def get_emulator_device(self):
        return EMULATOR_DEVICE
    
    def setUp(self):
        super(EurothermModbusTests, self).setUp()

    def test_WHEN_autotune_set_THEN_readback_updates(self):
        for state in [0, 1]:
            self.ca.set_pv_value("AUTOTUNE:SP", state)
            self.ca.assert_that_pv_is("AUTOTUNE", state)

    @parameterized.expand(parameterized_list(PID_TEST_VALUES))
    def test_WHEN_p_set_THEN_p_updates(self, _, val):
        self.ca.assert_setting_setpoint_sets_readback(value=val, readback_pv="P", timeout=15)

    @parameterized.expand(parameterized_list(PID_TEST_VALUES))
    def test_WHEN_i_set_THEN_i_updates(self, _, val):
        self.ca.assert_setting_setpoint_sets_readback(value=val, readback_pv="I", timeout=15)

    @parameterized.expand(parameterized_list(PID_TEST_VALUES))
    def test_WHEN_d_set_THEN_d_updates(self, _, val):
        self.ca.assert_setting_setpoint_sets_readback(value=val, readback_pv="D", timeout=15)

    @parameterized.expand(parameterized_list([0, 0.5, 100]))
    def test_WHEN_max_output_set_THEN_max_output_updates(self, _, val):
        self.ca.assert_setting_setpoint_sets_readback(value=val, readback_pv="MAX_OUTPUT", timeout=15)
    
    @skip_if_recsim("Backdoor not available in recsim")
    def test_WHEN_using_needle_valve_THEN_flow_exists(self):
            self._lewis.backdoor_set_on_device("flow", 5.0)
            self.ca.assert_that_pv_is_number("FLOW", 5.0, tolerance=0.05, timeout=15)
    
    @skip_if_recsim("Backdoor not available in recsim")
    def test_WHEN_using_needle_valve_THEN_valve_dir_exists(self):
        self._lewis.backdoor_set_on_device("valve_direction", 1)
        self.ca.assert_that_pv_is("VALVE_DIR", "OPENING")
    
    def test_WHEN_set_manual_flow_THEN_manual_flow_updates(self):
        self.ca.assert_setting_setpoint_sets_readback(value=8.0, set_point_pv="MANUAL_FLOW:SP", readback_pv="MANUAL_FLOW")
    
    def test_WHEN_using_needle_valve_WHEN_flow_low_lim_set_THEN_is_updated(self):
        self.ca.assert_setting_setpoint_sets_readback(value=2.0, set_point_pv="FLOW_SP_LOWLIM:SP", readback_pv="FLOW_SP_LOWLIM")
    
    def test_WHEN_using_needle_valve_WHEN_flow_sp_mode_set_THEN_is_updated(self):
        self.ca.assert_setting_setpoint_sets_readback(value="AUTO", set_point_pv="FLOW_SP_MODE_SELECT:SP", readback_pv="FLOW_SP_MODE_SELECT")

    def test_WHEN_using_needle_valve_WHEN_needle_valve_stop_set_THEN_is_updated(self):
        self.ca.assert_setting_setpoint_sets_readback(value="STOPPED", set_point_pv="NEEDLE_VALVE_STOP:SP", readback_pv="NEEDLE_VALVE_STOP")
