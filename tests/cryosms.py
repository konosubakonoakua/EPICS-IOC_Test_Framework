import unittest
import time

from parameterized import parameterized
from utils.test_modes import TestModes
from utils.channel_access import ChannelAccess
from utils.ioc_launcher import get_default_ioc_dir, IOCRegister
from utils.testing import get_running_lewis_and_ioc, skip_if_recsim, parameterized_list

DEVICE_PREFIX = "CRYOSMS_01"
EMULATOR_NAME = "cryogenic_sms"

IOCS = [
    {
        "name": DEVICE_PREFIX,
        "directory": get_default_ioc_dir("CRYOSMS"),
        "emulator": EMULATOR_NAME,
        "macros": {
            "MAX_CURR": 135,
            "T_TO_A": 0.037,
            "MAX_VOLT": 9.9,
            "WRITE_UNIT": "AMPS",
            "DISPLAY_UNIT": "GAUSS",
            "RAMP_FILE": r"C:\\Instrument\\Apps\\EPICS\\support\\cryosms\\master\\ramps\\default.txt",
            "MID_TOLERANCE": 0.1,
            "TARGET_TOLERANCE": 0.01,
            "ALLOW_PERSIST": "No",
            "USE_SWITCH": "No",
            "FAST_FILTER_VALUE": 1,
            "FILTER_VALUE": 0.1,
            "NPP": 0.0005,
            "FAST_PERSISTENT_SETTLETIME": 5,
            "PERSISTENT_SETTLETIME": 60,
            "NON_PERSISTENT_SETTLETIME": 30,
            "SWITCH_TEMP_PV": "CRYOSMS_01:SIM:SWITCH:TEMP",
            "SWITCH_HIGH": 3.7,
            "SWITCH_LOW": 3.65,
            "SWITCH_STABLE_NUMBER": 10,
            "SWITCH_TIMEOUT": 300,
            "HEATER_TOLERANCE": 0.2,
            "HEATER_OFF_TEMP": 3.7,
            "HEATER_ON_TEMP": 3.65,
            "HEATER_OUT": "CRYOSMS_01:SIM:TEMP:HEATER",
            "USE_MAGNET_TEMP": "Yes",
            "MAGNET_TEMP_PV": "CRYOSMS_01:SIM:TEMP:MAGNET",
            "MAX_MAGNET_TEMP": 5.5,
            "MIN_MAGNET_TEMP": 1,
            "COMP_OFF_ACT": "Yes",
            "NO_OF_COMP": "2",
            "MIN_NO_OF_COMP": 1,
            "COMP_1_STAT_PV": "CRYOSMS_01:SIM:COMP1STAT",
            "COMP_2_STAT_PV": "CRYOSMS_01:SIM:COMP2STAT",
            "HOLD_TIME_ZERO": 12,
            "HOLD_TIME": 30,
            "VOLT_STABILITY_DURATION": 300,
            "VOLT_TOLERANCE": 0.2,
            "FAST_RATE": 0.5,
            "RESTORE_WRITE_UNIT_TIMEOUT": 10,
            "CRYOMAGNET": "Yes",
        }
    },
]


TEST_MODES = [TestModes.DEVSIM, TestModes.RECSIM]
TEST_RAMPS = [[(0.0, 10000.0), {10000: 1.12}],
              [(5000.0, 25000.0), {10000: 1.12, 20000: 0.547, 25000: 0.038}],
              [(-5000.0, -25000.0), {-10000: 1.12, -20000: 0.547, -25000: 0.038}],
              [(25000.0, 5000.0), {20000: 0.038, 10000: 0.547, 0: 1.12}],
              [(25000.0, -25000.0), {20000: 0.038, 10000: 0.547, -10000: 1.12, -20000: 0.547, -25000: 0.038}],
              [(-25000.0, 25000.0), {-20000: 0.038, -10000: 0.547, 10000: 1.12, 20000: 0.547, 25000: 0.038}],
              [(-25000.0, 0), {-20000: 0.038, -10000: 0.547, 0: 1.12}],
              [(25000.0, 0), {20000: 0.038, 10000: 0.547, 0: 1.12}],
              ]


class CryoSMSTests(unittest.TestCase):
    def setUp(self):
        self._lewis, self._ioc = get_running_lewis_and_ioc(EMULATOR_NAME, DEVICE_PREFIX)
        self.ca = ChannelAccess(device_prefix=DEVICE_PREFIX, default_timeout=10)

        if IOCRegister.uses_rec_sim:
            self.ca.assert_that_pv_exists("DISABLE", timeout=30)
        else:
            self._lewis.backdoor_set_on_device("is_quenched", False)
            self.ca.assert_that_pv_is("INIT", "Startup complete",  timeout=60)
            self.ca.set_pv_value("SIM:TEMP:MAGNET", 3.67)
            self.ca.set_pv_value("SIM:COMP1STAT", 1)
            self.ca.set_pv_value("SIM:COMP2STAT", 1)
            self._lewis.backdoor_set_on_device("mid_target", 0)
            self._lewis.backdoor_set_on_device("output", 0)
            self.ca.set_pv_value("PAUSE:SP", 0)
            self.ca.set_pv_value("ABORT:SP", 1)
            self.ca.assert_that_pv_is("RAMP:STAT", "HOLDING ON TARGET")
            self.ca.assert_that_pv_is("OUTPUT:RAW", 0)

    @skip_if_recsim("Cannot properly simulate device startup in recsim")
    def test_GIVEN_certain_macros_WHEN_IOC_loads_THEN_correct_values_initialised(self):
        expectedValues = {"OUTPUT:SP": 0,
                          "OUTPUT": 0,
                          "OUTPUT:COIL": 0,
                          "OUTPUT:PERSIST": 0,
                          "OUTPUT:VOLT": 0,
                          "RAMP:RATE": 1.12,
                          "READY": 1,
                          "RAMP:RAMPING": 0,
                          "TARGET:TIME": 0,
                          "STAT": "Ready",
                          "HEATER:STAT": "ON",
                          "START:SP.DISP": "0",
                          "PAUSE:SP.DISP": "0",
                          "ABORT:SP.DISP": "0",
                          "OUTPUT:SP.DISP": "0",
                          "MAGNET:MODE.DISP": "1",
                          "RAMP:LEADS.DISP": "1",
                          }
        failedPVs = []
        for PV in expectedValues:
            try:
                self.ca.assert_that_pv_is(PV, expectedValues[PV], timeout=5)
            except Exception as e:
                if hasattr(e, "message"):
                    failedPVs.append(e.message)
                else:
                    failedPVs.append(repr(e))
        if failedPVs:
            self.fail("The following PVs generated errors:\n{}".format("\n".join(failedPVs)))

    def test_GIVEN_outputmode_sp_correct_WHEN_outputmode_sp_written_to_THEN_outputmode_changes(self):
        # For all other tests, alongside normal operation, communication should be in amps
        self.ca.assert_setting_setpoint_sets_readback("TESLA", "OUTPUTMODE", "OUTPUTMODE:SP", timeout=10)
        self.ca.assert_setting_setpoint_sets_readback("AMPS", "OUTPUTMODE", "OUTPUTMODE:SP", timeout=10)

    @parameterized.expand(parameterized_list(TEST_RAMPS))
    @skip_if_recsim("C++ driver can not correctly initialised in recsim")
    def test_GIVEN_psu_at_field_strength_A_WHEN_told_to_ramp_to_B_THEN_correct_rates_used(self, _, ramp_data):
        start_point, end_point = ramp_data[0]
        ramp_rates = ramp_data[1]
        output = None
        # When setting output, convert from Gauss to Amps by dividing by 10000 and T_TO_A, also ensure sign handled
        # correctly
        sign = 1 if start_point >= 0 else -1
        self._lewis.backdoor_run_function_on_device("switch_direction", [sign])
        self._lewis.backdoor_set_on_device("output", abs(start_point)/(0.037 * 10000))
        self.ca.set_pv_value("TARGET:SP", end_point)
        self.ca.set_pv_value("START:SP", 1)
        for mid_point in ramp_rates:
            attempts = 0
            output = self.ca.get_pv_value("OUTPUT")
            while attempts < 20:
                if start_point <= output <= mid_point or start_point >= output >= mid_point:
                    self.ca.assert_that_pv_is("RAMP:RATE", ramp_rates[mid_point])
                    start_point = mid_point
                    break
                else:
                    attempts += 1
                    time.sleep(1)
                    output = self.ca.get_pv_value("OUTPUT")
            else:
                self.fail("Output failed to reach mid-point, was {0}G but expected {1}G".format(output, mid_point))
        self.ca.assert_that_pv_is("RAMP:STAT", "HOLDING ON TARGET", timeout=25)
        self.ca.assert_that_pv_is_within_range("OUTPUT", end_point - 0.01, end_point + 0.01)

    @skip_if_recsim("C++ driver can not correctly initialised in recsim")
    def test_GIVEN_IOC_not_ramping_WHEN_ramp_started_THEN_simulated_ramp_performed(self):
        self.ca.set_pv_value("TARGET:SP", 10000)
        self.ca.set_pv_value("START:SP", 1)
        self.ca.assert_that_pv_is("RAMP:STAT", "RAMPING", msg="Ramping failed to start")
        self.ca.assert_that_pv_is("RAMP:STAT", "HOLDING ON TARGET", timeout=10)

    @skip_if_recsim("C++ driver can not correctly initialised in recsim")
    def test_GIVEN_IOC_ramping_WHEN_paused_and_unpaused_THEN_ramp_is_paused_resumed_and_completes(self):
        # GIVEN ramping
        self.ca.set_pv_value("TARGET:SP", 10000)
        self.ca.set_pv_value("START:SP", 1)
        self.ca.assert_that_pv_is("RAMP:STAT", "RAMPING")
        # Pauses when pause set to true
        self.ca.set_pv_value("PAUSE:SP", 1)
        self.ca.assert_that_pv_is("RAMP:STAT", "HOLDING ON PAUSE", msg="Ramping failed to pause")
        self.ca.assert_that_pv_is_not("RAMP:STAT", "HOLDING ON TARGET", timeout=5,
                                      msg="Ramp completed even though it should have paused")
        # Resumes when pause set to false, completes ramp
        self.ca.set_pv_value("PAUSE:SP", 0)
        self.ca.assert_that_pv_is("RAMP:STAT", "RAMPING", msg="Ramping failed to resume")
        self.ca.assert_that_pv_is("RAMP:STAT", "HOLDING ON TARGET", timeout=10, msg="Ramping failed to complete")

    @skip_if_recsim("C++ driver can not correctly initialised in recsim")
    def test_GIVEN_IOC_ramping_WHEN_aborted_THEN_ramp_aborted(self):
        # Given Ramping
        self.ca.set_pv_value("TARGET:SP", 10000)
        self.ca.set_pv_value("START:SP", 1)
        self.ca.assert_that_pv_is("RAMP:STAT", "RAMPING")
        # Aborts when abort set to true, then hits ready again
        self.ca.set_pv_value("ABORT:SP", 1)
        self.ca.assert_that_pv_is("RAMP:STAT", "HOLDING ON TARGET", timeout=10)

    @skip_if_recsim("C++ driver can not correctly initialised in recsim")
    def test_GIVEN_IOC_paused_WHEN_aborted_THEN_ramp_aborted(self):
        # GIVEN paused
        self.ca.set_pv_value("TARGET:SP", 10000)
        self.ca.set_pv_value("START:SP", 1)
        self.ca.set_pv_value("PAUSE:SP", 1)
        rampTarget = self.ca.get_pv_value("MID")
        self.ca.assert_that_pv_is("RAMP:STAT", "HOLDING ON PAUSE", msg="Ramping failed to pause")
        # Aborts when abort set to true, then hits ready again
        self.ca.set_pv_value("ABORT:SP", 1)
        self.ca.assert_that_pv_is("RAMP:STAT", "HOLDING ON TARGET", timeout=10)
        self.ca.assert_that_pv_is_not("MID", rampTarget)

    @skip_if_recsim("Test is to tell whether data from emulator is correctly received")
    def test_GIVEN_output_nonzero_WHEN_units_changed_THEN_output_raw_adjusts(self):
        # Check that it is currently working correctly in Amps
        self._lewis.backdoor_set_on_device("is_paused", True)
        self._lewis.backdoor_set_on_device("output", 1/0.037)  # 1T (0.037 = T_TO_A)
        self.ca.assert_that_pv_is_number("OUTPUT:RAW", 1/0.037, 0.001)
        self.ca.assert_that_pv_is_number("OUTPUT", 10000, 1)  # OUTPUT should remain in Gauss
        # Set outputmode to tesla
        self.ca.set_pv_value("OUTPUTMODE:SP", "TESLA")
        self.ca.assert_that_pv_is_number("OUTPUT:RAW", 1, 0.001)
        self.ca.assert_that_pv_is_number("OUTPUT", 10000, 1)
        # Confirm functionality returns to normal when going back to Amps
        self.ca.set_pv_value("OUTPUTMODE:SP", "AMPS")
        self.ca.assert_that_pv_is_number("OUTPUT:RAW", 1/0.037, 0.001)
        self.ca.assert_that_pv_is_number("OUTPUT", 10000, 1)

    @skip_if_recsim("C++ driver can not correctly initialised in recsim")
    def test_GIVEN_ramping_WHEN_quenched_THEN_paused_with_correct_message(self):
        self.ca.set_pv_value("TARGET:SP", 10000)
        self.ca.set_pv_value("START:SP", 1)
        self._lewis.backdoor_set_on_device("is_quenched", True)
        self.ca.assert_that_pv_is("PAUSE", "OFF")
        self.ca.assert_that_pv_is("STAT", "Quenched")

    @skip_if_recsim("C++ driver can not correctly initialised in recsim")
    def test_GIVEN_ramping_WHEN_1_comp_off_but_more_than_min_on_THEN_keep_ramping(self):
        self.ca.set_pv_value("TARGET:SP", 10000)
        self.ca.set_pv_value("START:SP", 1)
        self.ca.set_pv_value("SIM:COMP1STAT", 0)
        self.ca.assert_that_pv_is_within_range("OUTPUT", 9999.9, 10000.1)
        self.ca.assert_that_pv_is("RAMP:STAT", "HOLDING ON TARGET")
        self.ca.assert_that_pv_is("STAT", "Ready")

    @skip_if_recsim("C++ driver can not correctly initialised in recsim")
    def test_GIVEN_ramping_WHEN_less_than_min_number_of_comp_on_THEN_pause(self):
        self.ca.set_pv_value("TARGET:SP", 10000)
        self.ca.set_pv_value("START:SP", 1)
        self.ca.set_pv_value("SIM:COMP1STAT", 0)
        self.ca.set_pv_value("SIM:COMP2STAT", 0)
        self.ca.assert_that_pv_is("RAMP:STAT", "HOLDING ON PAUSE")
        self.ca.assert_that_pv_is("STAT", "Paused: not enough compressors on")

    @skip_if_recsim("C++ driver can not correctly initialised in recsim")
    def test_WHEN_write_unit_changed_THEN_changes_back_after_macro_defined_time(self):
        self.ca.set_pv_value("OUTPUTMODE:SP", "TESLA")
        self.ca.assert_that_pv_is("OUTPUTMODE", "TESLA")
        self.ca.assert_that_pv_is("OUTPUTMODE", "AMPS", timeout=15)

    @skip_if_recsim("C++ driver can not correctly initialised in recsim")
    def test_GIVEN_ramping_WHEN_temp_not_in_range_THEN_pauses_and_WHEN_back_in_range_THEN_resumes(self):
        # Start ramp
        self.ca.set_pv_value("TARGET:SP", 10000)
        self.ca.set_pv_value("START:SP", 1)
        # Make sure it's ramping before changing temps else we'll stop it too quickly
        self.ca.assert_that_pv_is("RAMP:STAT", "RAMPING")
        # Set temp to well over max (5.5), check ramp stops and PVs correctly modified
        self.ca.set_pv_value("SIM:TEMP:MAGNET", 10)
        self.ca.assert_that_pv_is("RAMP:STAT", "HOLDING ON PAUSE")
        self.ca.assert_that_pv_is("STAT", "Paused: Magnet temperature out of range")
        self.ca.assert_that_pv_is("MAGNET:TEMP:PAUSE", "Paused")
        self.ca.assert_that_pv_is("MAGNET:TEMP:INRANGE", "No")
        self.ca.assert_that_pv_is("MAGNET:TEMP:TOOHOT", "Too hot")
        # Set temp to under min (1), make sure it doesn't start up again and PVs correctly modified
        self.ca.set_pv_value("SIM:TEMP:MAGNET", 0)
        self.ca.assert_that_pv_is_not("RAMP:STAT", "RAMPING", 5)
        self.ca.assert_that_pv_is("STAT", "Paused: Magnet temperature out of range")
        self.ca.assert_that_pv_is("MAGNET:TEMP:PAUSE", "Paused")
        self.ca.assert_that_pv_is("MAGNET:TEMP:INRANGE", "No")
        # Too cold is more of an indicator of sensor malfunction, hence "Good heat"
        self.ca.assert_that_pv_is("MAGNET:TEMP:TOOHOT", "Good heat")
        # Return temp to original value (3.67), check ramp starts back up, correct PVs are modified and ramp completes
        self.ca.set_pv_value("SIM:TEMP:MAGNET", 3.67)
        self.ca.assert_that_pv_is("RAMP:STAT", "RAMPING")
        self.ca.assert_that_pv_is("MAGNET:TEMP:PAUSE", "Unpaused")
        self.ca.assert_that_pv_is("MAGNET:TEMP:INRANGE", "Yes")
        self.ca.assert_that_pv_is("MAGNET:TEMP:TOOHOT", "Good heat")
        self.ca.assert_that_pv_is_within_range("OUTPUT", 9999.9, 10000.1)
        self.ca.assert_that_pv_is("RAMP:STAT", "HOLDING ON TARGET")
        self.ca.assert_that_pv_is("STAT", "Ready")
