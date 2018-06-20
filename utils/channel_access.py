import os
import time
import operator
import ctypes
from contextlib import contextmanager
from genie_python.genie_cachannel_wrapper import CaChannelWrapper, UnableToConnectToPVException

from functools import partial

try:
    # Python 3
    from functools import partialmethod
except ImportError:
    # Workaround for Python 2
    class partialmethod(partial):
        def __get__(self, instance, owner):
            return partial(self.func, instance, *(self.args or ()), **(self.keywords or {}))


class ChannelAccess(object):
    """
    Provides the required channel access commands.
    """

    class Alarms(object):
        """
        Possible alarm states that a PV can be in.
        """
        NONE = "NO_ALARM"  # Alarm value if there is no alarm
        MAJOR = "MAJOR"  # Alarm value if the record is in major alarm
        MINOR = "MINOR"  # Alarm value if the record is in minor alarm
        INVALID = "INVALID"  # Alarm value if the record has a calc alarm

    def __init__(self, default_timeout=5, device_prefix=None):
        """
        Constructor.

        :param device_prefix: the device prefix which will be added to the start of all pvs
        :param default_timeout: the default time out to wait for
        """
        self.ca = CaChannelWrapper()

        # Silence CA errors
        CaChannelWrapper.errorLogFunc = lambda *a, **kw: None
        try:
            hcom = ctypes.cdll.LoadLibrary("COM.DLL")
            hcom.eltc(ctypes.c_int(0))
        except Exception as e:
            print("Unable to disable CA errors: ", e)

        self.prefix = os.environ["testing_prefix"]
        self._default_timeout = default_timeout
        if not self.prefix.endswith(':'):
            self.prefix += ':'
        if device_prefix is not None:
            self.prefix += "{0}:".format(device_prefix)

    def set_pv_value(self, pv, value):
        """
        Sets the specified PV to the supplied value.

        :param pv: the EPICS PV name
        :param value: the value to set
        """
        # Wait for the PV to exist before writing to it. If this is not here sometimes the tests try to jump the gun
        # and attempt to write to a PV that doesn't exist yet
        self.wait_for(pv)

        # Don't use wait=True because it will cause an infinite wait if the value never gets set successfully
        # In that case the test should fail (because the correct value is not set)
        # but it should not hold up all the other tests
        self.ca.set_pv_value(self._create_pv_with_prefix(pv), value, timeout=self._default_timeout)
        # Need to give Lewis time to process
        time.sleep(1)

    def get_pv_value(self, pv):
        """
        Gets the current value for the specified PV.

        :param pv: the EPICS PV name
        :return: the current value
        """
        return self.ca.get_pv_value(self._create_pv_with_prefix(pv))

    def process_pv(self, pv):
        """
        Makes the pv process once.

        :param pv: the EPICS PV name
        :return: None
        """
        pv_proc = "{}.PROC".format(self._create_pv_with_prefix(pv))
        return self.ca.set_pv_value(pv_proc, 1)

    def _format_value(self, value):
        return "'{}' (type: '{}')".format(value, value.__class__.__name__)

    def assert_that_pv_is(self, pv, expected_value, timeout=None, msg=None):
        """
        Assert that the pv has the expected value or that it becomes the expected value within the timeout.

        :param pv: pv name
        :param expected_value: expected value
        :param timeout: if it hasn't changed within this time raise assertion error
        :param msg: Extra message to print
        :raises AssertionError: if value does not become requested value
        :raises UnableToConnectToPVException: if pv does not exist within timeout
        """

        if msg is None:
            msg = "Expected PV to have value {}.".format(self._format_value(expected_value))

        return self.assert_pv_value_causes_func_to_return_true(
            pv, lambda val: val == expected_value, timeout=timeout, message=msg)

    def assert_that_pv_is_not(self, pv, restricted_value, timeout=None, msg=""):
        """
        Assert that the pv does not have a particular value and optionally it does not become that value within the
        timeout.

        :param pv: pv name
        :param restricted_value: value the PV shouldn't become
        :param timeout: if it becomes the value within this time, raise an assertion error
        :param msg: Extra message to print
        :raises AssertionError: if value has the restricted value
        :raises UnableToConnectToPVException: if pv does not exist within timeout
        """

        if msg is None:
            msg = "Expected PV to not have value {}.".format(self._format_value(restricted_value))

        return self.assert_pv_value_causes_func_to_return_true(
            pv, lambda val: val != restricted_value, timeout, message=msg)

    def assert_that_pv_is_number(self, pv, expected_value, tolerance=0, timeout=None):
        """
        Assert that the pv has the expected value or that it becomes the expected value within the timeout
        :param pv: pv name
        :param expected_value: expected value
        :param tolerance: the allowable deviation from the expected value
        :param timeout: if it hasn't changed within this time raise assertion error
        :raises AssertionError: if value does not become requested value
        :raises UnableToConnectToPVException: if pv does not exist within timeout
        """
        def condition(val):
            try:
                val = float(val)
            except (ValueError, TypeError):
                return False
            return abs(val - expected_value) <= tolerance

        message = "Expected PV value to be equal to {} (tolerance: {})"\
            .format(self._format_value(expected_value), self._format_value(tolerance))

        return self.assert_pv_value_causes_func_to_return_true(pv, condition, timeout, message=message)

    def assert_that_pv_is_not_number(self, pv, restricted_value, tolerance=0, timeout=None):
        """
        Assert that the pv is at least tolerance from the restricted value within the timeout
        :param pv: pv name
        :param restricted_value: the value we don't want the PV to have
        :param tolerance: the minimal deviation from the expected value
        :param timeout: if it hasn't changed within this time raise assertion error
        :raises AssertionError: if value does not enter the desired range
        :raises UnableToConnectToPVException: if pv does not exist within timeout
        """
        def condition(val):
            try:
                val = float(val)
            except (ValueError, TypeError):
                return False
            return abs(val - restricted_value) >= tolerance

        message = "Expected PV value to be not equal to {} (tolerance: {})"\
            .format(self._format_value(restricted_value), self._format_value(tolerance))

        return self.assert_pv_value_causes_func_to_return_true(pv, condition, timeout=timeout, message=message)

    def assert_that_pv_is_one_of(self, pv, expected_values, timeout=None):
        """
        Assert that the pv has one of the expected values or that it becomes one of the expected value within the
        timeout.

        :param pv: pv name
        :param expected_values: expected values
        :param timeout: if it hasn't changed within this time raise assertion error
        :return:
        :raises AssertionError: if value does not become requested value
        :raises UnableToConnectToPVException: if pv does not exist within timeout
        """
        def condition(val):
            return val in expected_values

        message = "Expected PV value to be in {}".format(expected_values)

        return self.assert_pv_value_causes_func_to_return_true(pv, condition, timeout, message)

    def assert_that_pv_is_an_integer_between(self, pv, min_value, max_value, timeout=None):
        """
        Assert that the pv has one of the expected values or that it becomes one of the expected value within the
        timeout

        :param pv: pv name
        :param min_value: minimum value (inclusive)
        :param max_value: maximum value (inclusive)
        :param timeout: if it hasn't changed within this time raise assertion error
        :return:
        :raises AssertionError: if value does not become requested value
        :raises UnableToConnectToPVException: if pv does not exist within timeout
        """
        def condition(val):
            try:
                int_pv_value = int(val)
            except ValueError:
                return False

            return min_value <= int_pv_value <= max_value

        message = "Expected PV value to be an integer between {} and {}".format(min_value, max_value)

        return self.assert_pv_value_causes_func_to_return_true(pv, condition, timeout, message)

    def wait_for(self, pv, timeout=None):
        """
        Wait for pv to be available or timeout and throw UnableToConnectToPVException.

        :param pv: pv to wait for
        :param timeout: time to wait for
        :return:
        :raises UnableToConnectToPVException: if pv can not be connected to after given time
        """
        if timeout is None:
            timeout = self._default_timeout

        if not self.ca.pv_exists(self._create_pv_with_prefix(pv), timeout=timeout):
            raise AssertionError("PV {pv} does not exist".format(pv=self._create_pv_with_prefix(pv)))

    def assert_pv_does_not_exist(self, pv, timeout=2):
        """
        Asserts that a pv does not exist.

        :param pv: pv to wait for
        :param timeout: amount of time to wait for
        :return:
        :raises AssertionError: if pv exists
        """

        pv_name = self._create_pv_with_prefix(pv)
        if self.ca.pv_exists(pv_name, timeout):
            raise AssertionError("PV {pv} exists".format(pv=self._create_pv_with_prefix(pv)))

    def _create_pv_with_prefix(self, pv):
        """
        Create the full pv name with instrument prefix.

        :param pv: pv name without prefix
        :return: pv name with prefix
        """
        return "{prefix}{pv}".format(prefix=self.prefix, pv=pv)

    def _wait_for_pv_lambda(self, wait_for_lambda, timeout):
        """
        Wait for a lambda containing a pv to become None; return value or timeout and return actual value.

        :param wait_for_lambda: lambda we expect to be None
        :param timeout: time out period
        :return: final value of lambda
        """
        start_time = time.time()
        current_time = start_time

        if timeout is None:
            timeout = self._default_timeout

        while current_time - start_time < timeout:
            try:
                lambda_value = wait_for_lambda()
                if lambda_value is None:
                    return lambda_value
            except UnableToConnectToPVException:
                pass  # try again next loop maybe the PV will be up
            except Exception as e:
                return "Exception in function while waiting for PV. Error was: {}".format(e)

            time.sleep(0.5)
            current_time = time.time()

        # last try
        return wait_for_lambda()

    def assert_pv_alarm_is(self, pv, alarm, timeout=None):
        """
        Assert that a pv is in alarm state given or timeout.

        :param pv: pv name
        :param alarm: alarm state (see constants ALARM_X)
        :param timeout: length of time to wait for change
        :return:
        :raises AssertionError: if alarm does not become requested value
        :raises UnableToConnectToPVException: if pv does not exist within timeout
        """
        self.assert_that_pv_is("{pv}.SEVR".format(pv=pv), alarm, timeout=timeout)

    def assert_setting_setpoint_sets_readback(self, value, readback_pv, set_point_pv=None, expected_value=None,
                                              expected_alarm=Alarms.NONE, timeout=None):
        """
        Set a pv to a value and check that the readback has the expected value and alarm state.
        :param value: value to set
        :param readback_pv: the pv for the read back (e.g. IN:INST:TEMP)
        :param set_point_pv: the pv to check has the correct value;
            if None use the readback with SP  (e.g. IN:INST:TEMP:SP)
        :param expected_value: the expected return value; if None use the value
        :param expected_alarm: the expected alarm status, None don't check; defaults to ALARM_NONE
        :param timeout: timeout for the pv and alarm to become the expected values
        :return:
        :raises AssertionError: if setback does not become expected value or has incorrect alarm state
        :raises UnableToConnectToPVException: if a pv does not exist within timeout
        """
        if set_point_pv is None:
            set_point_pv = "{}:SP".format(readback_pv)
        if expected_value is None:
            expected_value = value

        self.set_pv_value(set_point_pv, value)
        self.assert_that_pv_is(readback_pv, expected_value, timeout=timeout)
        if expected_alarm is not None:
            self.assert_pv_alarm_is(readback_pv, expected_alarm, timeout=timeout)

    def assert_pv_value_over_time(self, pv, wait, comparator):
        """
        Check that a PV satisfies a given function over time. The initial value is compared to the final value after
        a given time using the comparator.
        :param pv: the PV to check
        :param wait: the number of seconds to wait
        :param comparator: a function taking two arguments; the initial and final values respectively. 
        The function should return true or false.
        :return:
        :raises AssertionError: if the value of the pv has not increased
        """
        initial_value = self.get_pv_value(pv)
        time.sleep(wait)

        message = "Expected value trend to satisfy comparator {}. Initial value was {}."\
            .format(comparator.__name__, self._format_value(initial_value))

        def condition(val):
            return comparator(val, initial_value)

        return self.assert_pv_value_causes_func_to_return_true(pv, condition, message=message)

    # Special cases of assert_pv_value_over_time
    assert_pv_value_is_increasing = partialmethod(assert_pv_value_over_time, comparator=operator.gt)
    assert_pv_value_is_decreasing = partialmethod(assert_pv_value_over_time, comparator=operator.lt)
    assert_pv_value_is_unchanged = partialmethod(assert_pv_value_over_time, comparator=operator.eq)

    def assert_pv_value_causes_func_to_return_true(self, pv, func, timeout=None, message=None):
        """
        Check that a PV satisfies a given function within some timeout.
        :param pv: the PV to check
        :param func: a function that takes one argument, the PV value, and returns True if the value is valid.
        :param timeout: time to wait for the PV to satisfy the function
        :param message: custom message to print on failure
        :raises: AssertionError: If the function does not evaluate to true within the given timeout
        """
        def wrapper(message):
            value = self.get_pv_value(pv)

            try:
                return_value = func(value)
            except Exception as e:
                return "Exception was thrown while evaluating function '{}' on pv value {}. Exception was: {} {}"\
                    .format(func.__name__, self._format_value(value), e.__class__.__name__, e.message)

            if return_value:
                return None
            else:
                return "{}{}{}".format(message, os.linesep, "Final PV value was {}".format(self._format_value(value)))

        if message is None:
            message = "Expected function '{}' to evaluate to True when reading PV '{}'." \
                .format(func.__name__, self._create_pv_with_prefix(pv))

        # Need to use functools.partial here because python won't automatically create a closure for a function that
        # we're not returning.
        err = self._wait_for_pv_lambda(partial(wrapper, message), timeout)

        if err is not None:
            raise AssertionError(err)

    # Using a context manager to put PVs into alarm means they don't accidentally get left in alarm if the test fails
    @contextmanager
    def put_simulated_record_into_alarm(self, pv, alarm):
        """
        Put a simulated record into alarm
        :param pv: pv to put into alarm
        :param alarm: type of alarm
        """
        def _set_and_check_simulated_alarm(set_check_pv, set_check_alarm):
            self.set_pv_value("{}.SIMS".format(set_check_pv), set_check_alarm)
            self.assert_pv_alarm_is("{}".format(set_check_pv), set_check_alarm)

        try:
            _set_and_check_simulated_alarm(pv, alarm)
            yield
        finally:
            _set_and_check_simulated_alarm(pv, self.Alarms.NONE)
