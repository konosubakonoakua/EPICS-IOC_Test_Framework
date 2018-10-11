"""
Lewis emulator interface classes.
"""
import os
import subprocess

import sys
from time import sleep, time
from functools import partial

from utils.free_ports import get_free_ports
from utils.log_file import log_filename
from utils.channel_access import format_value

from utils.emulator_exceptions import UnableToConnectToEmulatorException


class LewisRegister(object):
    """
    A way of registering running emulators.
    """

    # Static dictionary of running emulators
    RunningEmulators = {}

    @classmethod
    def get_running(cls, lewis_emulator):
        """
        Get a running emulator by name, return None if not running.

        :param lewis_emulator: name of the lewis emulator to grab
        :return: lewis launcher
        """
        return cls.RunningEmulators.get(lewis_emulator)

    @classmethod
    def add_emulator(cls, name, emulator):
        """
        Add a emulator to the running list.

        :param name: name of the emmulator
        :param emulator: the emmulator launcher
        :return:
        """
        cls.RunningEmulators[name] = emulator


class LewisNone(object):
    """
    Object representing a Lewis Launcher when Lewis is not required.
    """

    def __init__(self, device):
        """
        Constructor.

        :param device: device name
        """
        self.port = None
        self._device = device

    def __enter__(self):
        LewisRegister.add_emulator(self._device, self)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def check(self):
        """
        The none lewis simulator is running.

        :return: True
        """
        return True

    def backdoor_set_on_device(self, variable_name, value):
        """
        Does nothing.

        :param variable_name: name of the variable to set
        :param value: value
        :return:
        """
        pass

    def backdoor_command(self, command):
        pass

    def backdoor_run_function_on_device(self, function_name, arguments=None):
        """
        Does nothing

        :param function_name: name of the function to call
        :param arguments: an iterable of the arguments for the function; None means no arguments. Arguments will
            automatically be turned into json
        :return:
        """
        pass


class LewisLauncher(object):
    """
    Launches Lewis.
    """

    def __init__(self, device, python_path, lewis_path, var_dir, lewis_protocol, lewis_additional_path=None, lewis_package=None, port=None, emulator_id=None, default_timeout = 5):
        """
        Constructor that also launches Lewis.

        :param device: device to start
        :param python_path: path to python.exe
        :param lewis_path: path to lewis
        :param var_dir: location of directory to write log file and macros directories
        :param lewis_protocol: protocol to use
        :param lewis_additional_path: additional path to add to lewis usually the location of the device emulators
        :param lewis_package: package to use by lewis
        :param port: the port to use
        :param emulator_id: the unique id of the emulator
        """
        self._lewis_path = lewis_path
        self._python_path = python_path
        self._lewis_protocol = lewis_protocol
        self._device = device
        self._process = None
        self._lewis_additional_path = lewis_additional_path
        self._lewis_package = lewis_package
        self.port = port
        self._logFile = None
        self._connected = None
        self._var_dir = var_dir
        self._emulator_id = emulator_id if emulator_id is not None else self._device
        self._default_timeout = default_timeout

    def __enter__(self):
        self._open(self.port)
        LewisRegister.add_emulator(self._emulator_id, self)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._close()

    def _close(self):
        """
        Closes the Lewis session by killing the process.
        """
        print("Terminating Lewis")
        if self._process is not None:
            self._process.terminate()
        if self._logFile is not None:
            self._logFile.close()
            print("Lewis log written to {0}".format(self._log_filename()))

    def _open(self, port):
        """
        Start the lewis emulator.

        :param port: the port on which to run lewis
        :return:
        """

        self._control_port = str(get_free_ports(1)[0])
        lewis_command_line = [self._python_path, os.path.join(self._lewis_path, "lewis.exe"),
                              "-r", "127.0.0.1:{control_port}".format(control_port=self._control_port)]
        lewis_command_line.extend(["-p", "{protocol}: {{bind_address: 127.0.0.1, port: {port}}}"
                                  .format(protocol=self._lewis_protocol, port=port)])
        if self._lewis_additional_path is not None:
            lewis_command_line.extend(["-a", self._lewis_additional_path])
        if self._lewis_package is not None:
            lewis_command_line.extend(["-k", self._lewis_package])
        lewis_command_line.extend(["-e", "100", self._device])

        print("Starting Lewis")
        self._logFile = open(self._log_filename(), "w")
        self._logFile.write("Started Lewis with '{0}'\n".format(" ".join(lewis_command_line)))

        self._process = subprocess.Popen(lewis_command_line,
                                         creationflags=subprocess.CREATE_NEW_CONSOLE,
                                         stdout=self._logFile,
                                         stderr=subprocess.STDOUT)
        self._connected = True

    def _log_filename(self):
        return log_filename("lewis", self._emulator_id, False, self._var_dir)

    def check(self):
        """
        Check that the lewis emulator is running.

        :return: True if it is running; False otherwise
        """
        if self._process.poll() is None:
            return True
        print("Lewis has terminated! It said:")
        stdoutdata, stderrdata = self._process.communicate()
        sys.stderr.write(stderrdata)
        sys.stdout.write(stdoutdata)
        return False

    def _convert_to_string_for_backdoor(self, value):
        """
        Convert the value given to a string for the backdoor. If the type is a string suround with quotes otherwise
        pass it raw, e.g. for a number.
        Args:
            value: value to convert

        Returns: value as a string for the backdoor

        """
        return "'{}'".format(value) if isinstance(value, str) else str(value)

    def backdoor_set_on_device(self, variable_name, value):
        """
        Set a value in the device using the lewis backdoor.

        :param variable_name: name of variable to set
        :param value: new value it should have
        :return:
        """
        self.backdoor_command(["device", str(variable_name), self._convert_to_string_for_backdoor(value)])

    def backdoor_run_function_on_device(self, function_name, arguments=None):
        """
        Run a function in lewis using the back door on a device.

        :param function_name: name of the function to call
        :param arguments: an iterable of the arguments for the function; None means no arguments. Arguments will
            automatically be turned into json
        :return:
        """
        command = ["device", function_name]
        if arguments is not None:
            command.extend([self._convert_to_string_for_backdoor(argument) for argument in arguments])

        return self.backdoor_command(command)

    def backdoor_command(self, lewis_command):
        """
        Send a command to the backdoor of lewis.

        :param lewis_command: array of command line arguments to send
        :return: lines from the command output
        """
        lewis_command_line = [self._python_path, os.path.join(self._lewis_path, "lewis-control.exe"),
                              "-r", "127.0.0.1:{control_port}".format(control_port=self._control_port)]
        lewis_command_line.extend(lewis_command)
        self._logFile.write("lewis backdoor command: {0}\n".format(" ".join(lewis_command_line)))
        try:
            p = subprocess.Popen(lewis_command_line, stderr=subprocess.STDOUT, stdout=subprocess.PIPE)
            for i in range(1, 30):
                code = p.poll()
                if code == 0:
                    break
                sleep(0.1)
            else:
                p.terminate()
                print("Lewis backdoor did not finish!")
            return [line.strip() for line in p.stdout]
        except subprocess.CalledProcessError as ex:
            sys.stderr.write("Error using backdoor: {0}\n".format(ex.output))
            sys.stderr.write("Error code {0}\n".format(ex.returncode))
            raise ex

    def backdoor_emulator_disconnect_device(self):
        """
        Disconnect the emulated device.

        :return:
        """
        if self._connected:
            self.backdoor_command(["simulation", "disconnect_device"])
        self._connected = False

    def backdoor_emulator_connect_device(self):
        """
        Connect the emulated device.

        :return:
        """
        if not self._connected:
            self.backdoor_command(["simulation", "connect_device"])
        self._connected = True

    def backdoor_get_from_device(self, variable_name):
        """
        Return the string of a value on a device from lewis.
        :param variable_name: name of the variable
        :return: the variables value, as a string
        """
        return "".join(self.backdoor_command(["device", str(variable_name)]))

    def assert_that_emulator_value_is_greater_than(self, emulator_property, min_value, timeout=None):
            """
            Assert that an emulator property has a value greater than the expected value.

            Args:
                 emulator_property (string): Name of the emulator property.
                 min_value (float): Minimum value (inclusive).
                 timeout: if it hasn't changed within this time raise assertion error
            Raises:
                 AssertionError: if value does not become requested value
                 UnableToConnectToPVException: if pv does not exist within timeout
            """

            message = "Expected emulator property {} to have a value greater than {}".format(
                emulator_property, min_value)
            return self.assert_that_emulator_value_value_causes_func_to_return_true(
                emulator_property, lambda value: min_value <= float(value), timeout, message)

    def assert_that_emulator_value_is(self, emulator_property, expected_value, timeout=None, message=None):
        """
        Assert that the pv has the expected value or that it becomes the expected value within the timeout.

        Args:
            emulator_property (string): emulator property to check
            expected_value: expected value
            timeout (float): if it hasn't changed within this time raise assertion error
            message (string): Extra message to print
        Raises:
            AssertionError: if emulator property is not the expected value
            UnableToConnectToPVException: if emulator property does not exist within timeout
        """

        if message is None:
            message = "Expected PV to have value {}.".format(format_value(expected_value))

        return self.assert_that_emulator_value_value_causes_func_to_return_true(
            emulator_property, lambda val: val == expected_value, timeout=timeout, msg=message)

    def assert_that_emulator_value_value_causes_func_to_return_true(
            self, emulator_property, func, timeout=None, msg=None):
        """
        Check that a emulator property satisfies a given function within some timeout.

        Args:
            emulator_property (string): emulator property to check
            func: a function that takes one argument, the emulator property value, and returns True if the value is
                valid.
            timeout: time to wait for the PV to satisfy the function
            msg: custom message to print on failure
        Raises:
            AssertionError: If the function does not evaluate to true within the given timeout
        """

        def wrapper(msg):
            value = self.backdoor_get_from_device(emulator_property)
            try:
                return_value = func(value)
            except Exception as e:
                return "Exception was thrown while evaluating function '{}' on emulator property {}. " \
                       "Exception was: {} {}".format(func.__name__,
                                                     format_value(value), e.__class__.__name__, e.message)
            if return_value:
                return None
            else:
                return "{}{}{}".format(msg, os.linesep, "Final emulator property value was {}"
                                       .format(format_value(value)))

        if msg is None:
            msg = "Expected function '{}' to evaluate to True when reading emulator property '{}'." \
                .format(func.__name__, emulator_property)

        err = self._wait_for_emulator_lambda(partial(wrapper, msg), timeout)

        if err is not None:
            raise AssertionError(err)

    def _wait_for_emulator_lambda(self, wait_for_lambda, timeout):
        """
        Wait for a lambda containing a emulator property to become None; return value or timeout and return actual value.

        Args:
            wait_for_lambda: lambda we expect to be None
            timeout: time out period
        Returns:
            final value of lambda
        """
        start_time = time()
        current_time = start_time

        if timeout is None:
            timeout = self._default_timeout

        while current_time - start_time < timeout:
            try:
                lambda_value = wait_for_lambda()
                if lambda_value is None:
                    return lambda_value
            except UnableToConnectToEmulatorException:
                pass  # try again next loop maybe the emulator property will have changed

            sleep(0.5)
            current_time = time()

        # last try
        return wait_for_lambda()
