import unittest

from parameterized import parameterized

from utils.test_modes import TestModes
from utils.ioc_launcher import get_default_ioc_dir, ProcServLauncher
from common_tests.eurotherm import (EurothermBaseTests, NONE_TXT_CALIBRATION_MIN_TEMPERATURE,
                                    NONE_TXT_CALIBRATION_MAX_TEMPERATURE)
from utils.calibration_utils import use_calibration_file


DEVICE = "EUROTHRM_01"
EMULATOR = "eurotherm"

IOCS = [
    {
        "name": DEVICE,
        "directory": get_default_ioc_dir("EUROTHRM"),
        "ioc_launcher_class": ProcServLauncher,
        "macros": {
            "COMMS_MODE": "eibisynch",
            "ADDR_1": "01",
            "ADDR_2": "02",
            "ADDR_3": "03",
            "ADDR_4": "04",
            "ADDR_5": "05",
            "ADDR_6": "06",
            "ADDR_7": "",
            "ADDR_8": "",
            "ADDR_9": "",
            "ADDR_10": ""
        },
        "emulator": EMULATOR,
    },
]


TEST_MODES = [TestModes.DEVSIM]


class EurothermTests(EurothermBaseTests, unittest.TestCase):
    @parameterized.expand([
        ("over_range_calc_pv_is_over_range", NONE_TXT_CALIBRATION_MAX_TEMPERATURE + 5.0, 1.0),
        ("over_range_calc_pv_is_within_range", NONE_TXT_CALIBRATION_MAX_TEMPERATURE - 200, 0.0),
        ("over_range_calc_pv_is_within_range", NONE_TXT_CALIBRATION_MAX_TEMPERATURE, 0.0)
    ])
    def test_GIVEN_None_txt_calibration_file_WHEN_temperature_is_set_THEN(
            self, _, temperature, expected_value_of_over_range_calc_pv):
        """
        Note: this test can only run on BISYNCH eurotherms, modbus max temperature is 6553.5 but ramp file goes up
        to 10,000 and this test attempts to check this behaviour
        """
        # Arrange

        self._assert_using_mock_table_location()
        with use_calibration_file(self.ca, "None.txt", prefix="A01:"):
            self.ca.assert_that_pv_exists("A01:CAL:RANGE")
            self.ca.assert_that_pv_is("A01:TEMP:RANGE:OVER.B", NONE_TXT_CALIBRATION_MAX_TEMPERATURE)

            # Act:
            self._set_setpoint_and_current_temperature(temperature)

            # Assert
            self.ca.assert_that_pv_is("A01:TEMP:RANGE:OVER.A", temperature)
            self.ca.assert_that_pv_is("A01:TEMP:RANGE:OVER", expected_value_of_over_range_calc_pv)

    def test_GIVEN_None_txt_calibration_file_WHEN_changed_to_C006_txt_calibration_file_THEN_the_calibration_limits_change(
            self):
        """
        Note: this test can only run on BISYNCH eurotherms, modbus max temperature is 6553.5 but ramp file goes up
        to 10,000 and this test attempts to check this behaviour
        """
        C006_CALIBRATION_FILE_MAX = 330.26135292267900000000
        C006_CALIBRATION_FILE_MIN = 1.20927230303971000000

        # Arrange
        self._assert_using_mock_table_location()
        with use_calibration_file(self.ca, "None.txt", prefix="A01:"):
            self.ca.assert_that_pv_exists("A01:CAL:RANGE")
            self.ca.assert_that_pv_is("A01:TEMP:RANGE:OVER.B", NONE_TXT_CALIBRATION_MAX_TEMPERATURE)
            self.ca.assert_that_pv_is("A01:TEMP:RANGE:UNDER.B", NONE_TXT_CALIBRATION_MIN_TEMPERATURE)

        # Act:
        with use_calibration_file(self.ca, "C006.txt", prefix="A01:"):

            # Assert
            self.ca.assert_that_pv_is("A01:TEMP:RANGE:OVER.B", C006_CALIBRATION_FILE_MAX)
            self.ca.assert_that_pv_is("A01:TEMP:RANGE:UNDER.B", C006_CALIBRATION_FILE_MIN)

    def test_GIVEN_simulated_delay_WHEN_temperature_read_from_multiple_sensors_THEN_all_reads_correct(self):
        self._lewis.backdoor_set_on_device("delay_time", 300 / 1000)

        for temp in range(1, 10):
            self._lewis.backdoor_set_on_device("current_temperature", float(temp))
            self.ca.assert_that_pv_is("A01:RBV", float(temp))
            self.ca.assert_that_pv_is("A02:RBV", float(temp))
            self.ca.assert_that_pv_is("A03:RBV", float(temp))
            self.ca.assert_that_pv_is("A04:RBV", float(temp))
            self.ca.assert_that_pv_is("A05:RBV", float(temp))
            self.ca.assert_that_pv_is("A06:RBV", float(temp))

        self._lewis.backdoor_set_on_device("delay_time", None)
