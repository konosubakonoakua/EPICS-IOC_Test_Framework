"""
Lewis emulator interface classes.
"""

import abc
import contextlib
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from functools import partial
from time import sleep, time
from types import TracebackType
from typing import Any, Callable, Dict, Generator, List, Self, Type, TypeAlias, TypeVar

import psutil

from utils.emulator_exceptions import UnableToConnectToEmulatorException
from utils.formatters import format_value
from utils.free_ports import get_free_ports
from utils.ioc_launcher import EPICS_TOP, IOCRegister
from utils.log_file import log_filename
from utils.test_modes import TestModes

DEVICE_EMULATOR_PATH = os.path.join(EPICS_TOP, "support", "DeviceEmulator", "master")
DEFAULT_PY_PATH = os.path.join("C:\\", "Instrument", "Apps", "Python3")


EmulatorValue: TypeAlias = int | float | str | bool

T = TypeVar("T")


class EmulatorRegister(object):
    """
    A way of registering running emulators.
    """

    # Static dictionary of running emulators
    RunningEmulators = {}

    @classmethod
    def get_running(cls, name: str | None) -> "EmulatorLauncher | MultiLewisLauncher | None":
        """
        Get a running emulator by name, return None if not running.

        :param name: name of the lewis emulator to grab
        :return: lewis launcher
        """
        return cls.RunningEmulators.get(name)

    @classmethod
    def add_emulator(cls, name: str, emulator: "EmulatorLauncher | MultiLewisLauncher") -> None:
        """
        Add a emulator to the running list.

        :param name: name of the emmulator
        :param emulator: the emmulator launcher
        """
        cls.RunningEmulators[name] = emulator

    @classmethod
    def remove_emulator(cls, name: str) -> None:
        """
        Removes an emulator from the running list.

        :param name: name of the emmulator
        """
        del cls.RunningEmulators[name]


class EmulatorLauncher(object, metaclass=abc.ABCMeta):
    def __init__(
        self,
        test_name: str,
        device: str,
        emulator_path: str,
        var_dir: str,
        port: int,
        options: dict[str, Any],
    ) -> None:
        """
        Args:
            test_name: The name of the test we are creating a device emulator for
            device: The name of the device to emulate
            emulator_path: The path where the emulator can be found
            var_dir: The directory in which to store logs
            port: The TCP port to listen on for connections
            options: Dictionary of any additional options required by specific launchers
        """
        self._device = device
        self._emulator_id = options.get("emulator_id", self._device)
        self._var_dir = var_dir
        self._port = port
        self._options = options
        self._test_name = test_name
        self._emulator_path = emulator_path

    def __enter__(self) -> Self:
        self._open()
        EmulatorRegister.add_emulator(self._emulator_id, self)
        return self

    def __exit__(
        self,
        exc_type: Type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self._close()
        EmulatorRegister.remove_emulator(self._emulator_id)

    def _get_device(self) -> str:
        return self._device

    def _get_var_dir(self) -> str:
        return self._var_dir

    @abc.abstractmethod
    def _close(self) -> None:
        """
        Close the emulator. This should perform any cleanup required to kill the emulator.
        """

    @abc.abstractmethod
    def _open(self) -> None:
        """
        Open the emulator. This should spawn the emulator process and return once the emulator is
        ready to accept commands.
        """

    @abc.abstractmethod
    def backdoor_get_from_device(
        self, variable: str, *args: list[Any], **kwargs: dict[str, Any]
    ) -> str:
        """
        Get a value from  the device via the back door.

        Args:
            variable: The name of the variable to get
            args: arbitrary arguments
            kwargs: arbitrary keyword arguments

        Returns:
            The value returned via the backdoor
        """

    @abc.abstractmethod
    def backdoor_set_on_device(
        self,
        variable: str,
        value: EmulatorValue,
        *args: list[Any],
        **kwargs: dict[str, Any],
    ) -> None:
        """
        Set a value from  the device via the back door.

        Args:
            variable: The name of the variable to set
            value: The value to set
            args: arbitrary arguments
            kwargs: arbitrary keyword arguments

        Returns:
            Nothing.
        """

    @abc.abstractmethod
    def backdoor_emulator_disconnect_device(
        self, *args: list[Any], **kwargs: dict[str, Any]
    ) -> None:
        """
        Disconnect the device via the back door.

        Args:
            args: arbitrary arguments
            kwargs: arbitrary keyword arguments

        Returns:
            Nothing.
        """

    @abc.abstractmethod
    def backdoor_emulator_connect_device(self, *args: list[Any], **kwargs: dict[str, Any]) -> None:
        """
        Connect the device via the back door.

        Args:
            args: arbitrary arguments
            kwargs: arbitrary keyword arguments

        Returns:
            Nothing.
        """

    @abc.abstractmethod
    def backdoor_run_function_on_device(
        self, function_name: str, arguments: list[Any] | None = None
    ) -> list[bytes]:
        """
        Runs a function on an emulator via the backdoor.

        Args:
            function_name: name of the function to run
            arguments: arguments to the function

        Returns:
            Nothing.
        """

    def backdoor_command(self, command: list[str]) -> list[bytes]:
        """
        Runs a string command on an emulator via the backdoor.

        Precisely how this string is interpreted is dependent on the emulator launcher in use.
        """
        raise NotImplementedError("This emulator launcher does not override backdoor_command.")

    def backdoor_set_and_assert_set(
        self, variable: str, value: EmulatorValue, *args: list[Any], **kwargs: dict[str, Any]
    ) -> None:
        """
        Sets a value on the emulator via the backdoor and gets it back to assert it's been set

        Args:
            variable: The name of the variable to set
            value: The value to set
            args: arbitrary arguments
            kwargs: arbitrary keyword arguments

        Raises:
            AssertionError: if emulator property is not the expected value
        """
        self.backdoor_set_on_device(variable, value)
        self.assert_that_emulator_value_is(variable, str(value))

    def assert_that_emulator_value_is(
        self,
        emulator_property: str,
        expected_value: T,
        timeout: float | None = None,
        message: str | None = None,
        cast: Callable[[str], T] = lambda val: val,
    ) -> None:
        """
        Assert that the emulator property has the expected value or that it becomes the expected
        value within the timeout.

        Args:
            emulator_property (string): emulator property to check
            expected_value: expected value. Emulator backdoor always returns a string, so the value
                should be a string.
            timeout (float): if it hasn't changed within this time raise assertion error
            message (string): Extra message to print
            cast (callable): function which casts the returned value to an appropriate type before
                checking equality. E.g. to cast to float pass the float class as this argument.
        Raises:
            AssertionError: if emulator property is not the expected value
        """

        if message is None:
            message = f"Expected emulator to have value {format_value(expected_value)}."

        return self.assert_that_emulator_value_causes_func_to_return_true(
            emulator_property, lambda val: cast(val) == expected_value, timeout=timeout, msg=message
        )

    def assert_that_emulator_value_is_not(
        self,
        emulator_property: str,
        value: T,
        timeout: float | None = None,
        message: str | None = None,
        cast: Callable[[str], T] = lambda val: val,
    ) -> None:
        """
        Assert that the emulator property does not have the passed value and that it does not become
        the passed value within the timeout.

        Args:
            emulator_property (string): emulator property to check
            value: value to check against. Emulator backdoor always returns a string, so the value
                should be a string.
            timeout (float): if it hasn't changed within this time raise assertion error
            message (string): Extra message to print
            cast (callable): function which casts the returned value to an appropriate type before
                checking equality. E.g. to cast to float pass the float class as this argument.
        Raises:
            AssertionError: if emulator property *is* the passed value
            UnableToConnectToPVException: if emulator property does not exist within timeout
        """

        if message is None:
            message = f"Expected PV to *not* have value {format_value(value)}."

        return self.assert_that_emulator_value_causes_func_to_return_false(
            emulator_property, lambda val: cast(val) == value, timeout=timeout, msg=message
        )

    def assert_that_emulator_value_causes_func_to_return_true(
        self,
        emulator_property: str,
        func: Callable[[str], bool],
        timeout: float | None = None,
        msg: str | None = None,
    ) -> None:
        """
        Check that an emulator property satisfies a given function within some timeout.

        Args:
            emulator_property (string): emulator property to check
            func: a function that takes one argument, the emulator property value, and returns True
                if the value is valid.
            timeout: time to wait for the emulator to satisfy the function
            msg: custom message to print on failure
        Raises:
            AssertionError: If the function does not evaluate to true within the given timeout
        """

        def wrapper(msg: str) -> str | None:
            value = self.backdoor_get_from_device(emulator_property)
            try:
                return_value = func(value)
            except Exception as e:
                try:
                    exception_message = e.message  # type: ignore
                except AttributeError:
                    exception_message = "<no message>"

                return (
                    "Exception was thrown while evaluating function '{}' on emulator property {}. "
                    "Exception was: {} {}".format(
                        func.__name__, format_value(value), e.__class__.__name__, exception_message
                    )
                )
            if return_value:
                return None
            else:
                return "{}{}{}".format(
                    msg,
                    os.linesep,
                    "Final emulator property value was {}".format(format_value(value)),
                )

        if msg is None:
            msg = (
                "Expected function '{}' to evaluate to True " "when reading emulator property '{}'."
            ).format(func.__name__, emulator_property)

        err = self._wait_for_emulator_lambda(partial(wrapper, msg), timeout)

        if err is not None:
            raise AssertionError(err)

    def assert_that_emulator_value_causes_func_to_return_false(
        self,
        emulator_property: str,
        func: Callable[[str], bool],
        timeout: float | None = None,
        msg: str | None = None,
    ) -> None:
        """
        Check that an emulator property does not satisfy a given function within some timeout.

        Args:
            emulator_property (string): emulator property to check
            func: a function that takes one argument, the emulator property value, and returns True
                if the value is valid (i.e. *not* the value we're checking).
            timeout: time to wait for the PV to satisfy the function
            msg: custom message to print on failure
        Raises:
            AssertionError: If the function does not evaluate to false within the given timeout
        """

        def wrapper(msg: str) -> str | None:
            value = self.backdoor_get_from_device(emulator_property)
            try:
                return_value = func(value)
            except Exception as e:
                try:
                    exception_message = e.message  # type: ignore
                except AttributeError:
                    exception_message = "<no message>"
                return (
                    "Exception was thrown while evaluating function '{}' on emulator property {}. "
                    "Exception was: {} {}".format(
                        func.__name__, format_value(value), e.__class__.__name__, exception_message
                    )
                )
            if return_value:
                return "{}{}{}".format(
                    msg,
                    os.linesep,
                    "Final emulator property value was {}".format(format_value(value)),
                )
            else:
                return None

        if msg is None:
            msg = (
                "Expected function '{}' to evaluate to False "
                "when reading emulator property '{}'."
            ).format(func.__name__, emulator_property)

        err = self._wait_for_emulator_lambda(partial(wrapper, msg), timeout)

        if err is not None:
            raise AssertionError(err)

    def _wait_for_emulator_lambda(
        self, wait_for_lambda: Callable[[], T], timeout: float | None
    ) -> T:
        """
        Wait for a lambda containing a emulator property to become None; return value or timeout and
        return actual value.

        Args:
            wait_for_lambda: lambda we expect to be None
            timeout: time out period
        Returns:
            final value of lambda
        """
        start_time: float = time()
        current_time: float = start_time

        if timeout is None:
            assert isinstance(self, LewisLauncher), "No default timeout for non-lewis launchers"
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

    def assert_that_emulator_value_is_greater_than(
        self, emulator_property: str, min_value: float, timeout: float | None = None
    ) -> None:
        """
        Assert that an emulator property has a value greater than the expected value.

        Args:
             emulator_property (string): Name of the numerical emulator property.
             min_value (float): Minimum value (inclusive).Emulator backdoor always returns a string,
             so the value should be a string.
             timeout: if it hasn't changed within this time raise assertion error
        Raises:
             AssertionError: if value does not become requested value
        """

        message = (
            "Expected emulator property {} to have a value greater than or equal to {}".format(
                emulator_property, min_value
            )
        )
        return self.assert_that_emulator_value_causes_func_to_return_true(
            emulator_property, lambda value: min_value <= float(value), timeout, message
        )

    @contextlib.contextmanager
    def backdoor_simulate_disconnected_device(
        self, emulator_property: str = "connected"
    ) -> Generator[None, None, None]:
        """
        Simulate device disconnection
        """
        self.backdoor_set_on_device(emulator_property, False)
        try:
            yield
        finally:
            self.backdoor_set_on_device(emulator_property, True)


class NullEmulatorLauncher(EmulatorLauncher):
    """
    A null emulator launcher that does nothing.
    """

    def _open(self) -> None:
        pass

    def _close(self) -> None:
        pass

    def backdoor_get_from_device(
        self, variable: str, *args: list[Any], **kwargs: dict[str, Any]
    ) -> str:
        return ""

    def backdoor_set_on_device(
        self, variable: str, value: EmulatorValue, *args: list[Any], **kwargs: dict[str, Any]
    ) -> None:
        pass

    def backdoor_emulator_disconnect_device(
        self, *args: list[Any], **kwargs: dict[str, Any]
    ) -> None:
        pass

    def backdoor_emulator_connect_device(self, *args: list[Any], **kwargs: dict[str, Any]) -> None:
        pass

    def backdoor_run_function_on_device(
        self, function_name: str, arguments: list[Any] | None = None
    ) -> list[bytes]:
        return []


@dataclass
class Emulator(object):
    """
    A utility class to capture data required to create a MultiLewisLauncher
    """

    launcher_address: int
    device: str
    var_dir: str
    port: Any
    options: Dict


@dataclass
class TestEmulatorData(object):
    """
    A utility class to capture the required data from a test to create a MultiLewisLauncher.
    """

    emulator: str
    emulator_port: Any
    launcher_address: int


class LewisLauncher(EmulatorLauncher):
    """
    Launches Lewis.
    """

    _DEFAULT_LEWIS_PATH = os.path.join(DEFAULT_PY_PATH, "scripts")

    def __init__(
        self,
        test_name: str,
        device: str,
        emulator_path: str,
        var_dir: str,
        port: int,
        options: dict[str, Any],
    ) -> None:
        """
        Constructor that also launches Lewis.

        Args:
            test_name: name of test we are creating device emulator for
            device: device to start
            emulator_path: The path where the emulator can be found
            var_dir: location of directory to write log file and macros directories
            port: the port to use
        """
        super(LewisLauncher, self).__init__(
            test_name, device, emulator_path, var_dir, port, options
        )

        self._lewis_path: str = options.get("lewis_path", LewisLauncher._DEFAULT_LEWIS_PATH)
        self._python_path: str = options.get(
            "python_path", os.path.join(DEFAULT_PY_PATH, "python.exe")
        )
        self._lewis_protocol: str = options.get("lewis_protocol", "stream")
        self._lewis_additional_path: str = options.get("lewis_additional_path", emulator_path)
        self._lewis_package: str = options.get("lewis_package", "lewis_emulators")
        self._default_timeout: float = options.get("default_timeout", 5)
        self._speed: float = options.get("speed", 100)

        self._process = None
        self._logFile = None
        self._connected = None

    @classmethod
    def from_emulator(cls, test_name: str, emulator: Emulator) -> Self:
        """
        Constructor that also launches Lewis.

        Args:
            test_name: name of test we are creating device emulator for
            emulator: Information to launch the emulator with
        """
        return cls(
            test_name, emulator.device, "", emulator.var_dir, emulator.port, emulator.options
        )

    def _close(self) -> None:
        """
        Closes the Lewis session by killing the process.
        """
        print("Terminating Lewis Emulator ({0})".format(self._device))
        if self._process is not None:
            self._process.terminate()
        if self._logFile is not None:
            self._logFile.close()
            print("Lewis log written to {0}".format(self._log_filename()))

    def _open(self) -> None:
        """
        Start the lewis emulator.

        :param port: the port on which to run lewis
        :return:
        """
        self._logFile = open(self._log_filename(), "w")
        self._control_port = str(get_free_ports(1)[0])
        lewis_command_line = [
            self._python_path,
            "-u",
            "-m",
            "lewis",
            "-r",
            "127.0.0.1:{control_port}".format(control_port=self._control_port),
        ]
        lewis_command_line.extend(
            [
                "-p",
                "{protocol}: {{bind_address: 127.0.0.1, port: {port}}}".format(
                    protocol=self._lewis_protocol, port=self._port
                ),
            ]
        )
        if self._lewis_additional_path is not None:
            lewis_command_line.extend(["-a", self._lewis_additional_path])
        if self._lewis_package is not None:
            lewis_command_line.extend(["-k", self._lewis_package])

        # Set lewis speed
        lewis_command_line.extend(["-e", str(self._speed), self._device])
        print(
            f"Started Lewis Emulator ({self._device}), Lewis log file is {self._log_filename()}\n"
        )
        self._logFile.write("Started Lewis with '{0}'\n".format(" ".join(lewis_command_line)))
        self._logFile.flush()
        print("Started Lewis with '{0}'\n".format(" ".join(lewis_command_line)))
        self._process = subprocess.Popen(
            lewis_command_line,
            creationflags=subprocess.CREATE_NEW_CONSOLE,
            stdout=self._logFile,
            stderr=subprocess.STDOUT,
        )
        self._connected = True

    def _log_filename(self) -> str:
        return log_filename(
            self._test_name, "lewis", self._emulator_id, TestModes.DEVSIM, self._var_dir
        )

    def check(self) -> bool:
        """
        Check that the lewis emulator is running.

        :return: True if it is running; False otherwise
        """
        proc = self._process
        assert proc is not None
        if proc.poll() is None:
            return True
        print("Lewis has terminated! It said:")
        stdoutdata, stderrdata = proc.communicate()
        sys.stderr.write(stderrdata.decode("utf-8"))
        sys.stdout.write(stdoutdata.decode("utf-8"))
        return False

    def _convert_to_string_for_backdoor(self, value: EmulatorValue) -> str:
        """
        Convert the value given to a string for the backdoor. If the type is a string suround with
        quotes otherwise pass it raw, e.g. for a number.
        Args:
            value: value to convert

        Returns: value as a string for the backdoor

        """
        return "'{}'".format(value) if isinstance(value, str) else str(value)

    def backdoor_set_on_device(
        self, variable: str, value: EmulatorValue, *args: list[Any], **kwargs: dict[str, Any]
    ) -> None:
        """
        Set a value in the device using the lewis backdoor.

        :param variable: name of variable to set
        :param value: new value it should have
        :return:
        """
        self.backdoor_command(
            ["device", str(variable), self._convert_to_string_for_backdoor(value)]
        )

    def backdoor_run_function_on_device(
        self,
        function_name: str,
        arguments: list[Any] | None = None,
    ) -> list[bytes]:
        """
        Run a function in lewis using the back door on a device.

        :param function_name: name of the function to call
        :param arguments: an iterable of the arguments for the function; None means no arguments.
            Arguments will automatically be turned into json
        :return:
        """
        command = ["device", function_name]
        if arguments is not None:
            command.extend(
                [self._convert_to_string_for_backdoor(argument) for argument in arguments]
            )

        return self.backdoor_command(command)

    def backdoor_command(self, command: list[str]) -> list[bytes]:
        """
        Send a command to the backdoor of lewis.

        :param command: array of command line arguments to send
        :return: lines from the command output
        """
        lewis_command_line = [
            os.path.join(self._lewis_path, "lewis-control.exe"),
            "-r",
            "127.0.0.1:{control_port}".format(control_port=self._control_port),
        ]
        lewis_command_line.extend(command)
        time_stamp = datetime.fromtimestamp(time()).strftime("%Y-%m-%d %H:%M:%S")
        log_file = self._logFile
        assert log_file is not None
        log_file.write(
            "{0}: lewis backdoor command: {1}\n".format(time_stamp, " ".join(lewis_command_line))
        )
        log_file.flush()
        try:
            p = subprocess.Popen(
                lewis_command_line, stderr=subprocess.STDOUT, stdout=subprocess.PIPE
            )
            for i in range(1, 40):
                code = p.poll()
                if code == 0:
                    break
                sleep(0.1)
            else:
                p.terminate()
                print(f"Lewis backdoor command {lewis_command_line} did not finish!")
                log_file.write(f"Lewis backdoor command {lewis_command_line} did not finish!")
                log_file.flush()

            out = p.stdout
            assert out is not None
            output = [line for line in out]

            for line in output:
                if b"failed to create process" in line.lower():
                    raise IOError(f"Failed to spawn lewis-control.exe for backdoor set {command}.")

            return [line.strip() for line in output]
        except subprocess.CalledProcessError as ex:
            for loc in [sys.stderr, log_file]:
                loc.write(f"Error using backdoor: {ex.output}\n")
                loc.write(f"Error code {ex.returncode}\n")
            log_file.flush()
            raise ex

    def backdoor_emulator_disconnect_device(
        self, *args: list[Any], **kwargs: dict[str, Any]
    ) -> None:
        """
        Disconnect the emulated device.

        :return:
        """
        if self._connected:
            self.backdoor_command(["simulation", "disconnect_device"])
        self._connected = False

    def backdoor_emulator_connect_device(self, *args: list[Any], **kwargs: dict[str, Any]) -> None:
        """
        Connect the emulated device.

        :return:
        """
        if not self._connected:
            self.backdoor_command(["simulation", "connect_device"])
        self._connected = True

    def backdoor_get_from_device(
        self, variable: str, *args: list[Any], **kwargs: dict[str, Any]
    ) -> str:
        """
        Return the string of a value on a device from lewis.
        :param variable: name of the variable
        :return: the variables value
        """
        # backdoor_command returns a list of bytes and join takes str so convert them here
        return "".join(i.decode("utf-8") for i in self.backdoor_command(["device", str(variable)]))


class MultiLewisLauncher(object):
    """
    Launch multiple lewis emulators.
    """

    def __init__(self, test_name: str, emulators: List[Emulator]) -> None:
        self.test_name: str = test_name
        self.emulator_launchers: Dict[int, LewisLauncher] = {
            emulator.launcher_address: LewisLauncher.from_emulator(test_name, emulator)
            for emulator in emulators
        }

    def __enter__(self) -> Self:
        self._open()
        EmulatorRegister.add_emulator(self.test_name, self)
        return self

    def __exit__(
        self,
        exc_type: Type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self._close()
        EmulatorRegister.remove_emulator(self.test_name)

    def _close(self) -> None:
        """
        Stop the lewis emulators.
        """
        for launcher in self.emulator_launchers.values():
            launcher._close()

    def _open(self) -> None:
        """
        Start the lewis emulators.
        """
        for launcher in self.emulator_launchers.values():
            launcher._open()

    def backdoor_get_from_device(
        self, launcher_address: int, variable: str, *args: list[Any], **kwargs: dict[str, Any]
    ) -> str:
        """
        Get the variable value from the emulator addressed with the given launcher address.

        :param launcher_address: The address of the emulator to identify the device we want to get
            the value from.
        :param variable: The variable to obtain the value of from the device.
        :return: The variable's value.
        """
        return self.emulator_launchers[launcher_address].backdoor_get_from_device(variable)

    def backdoor_set_on_device(
        self,
        launcher_address: int,
        variable: str,
        value: EmulatorValue,
        *args: list[Any],
        **kwargs: dict[str, Any],
    ) -> None:
        """
        Set the variable to the given value on the emulator address with the given launcher address.

        :param launcher_address: The identifier of the device we want to set the value on.
        :param variable: The variable on the device to set.
        :param value: The value to set the variable to.
        """
        self.emulator_launchers[launcher_address].backdoor_set_on_device(variable, value)

    def backdoor_emulator_disconnect_device(self, launcher_address: int) -> None:
        """
        Disconnect the emulator addressed by the given launcher address.

        :param launcher_address: The identifier of the device we want to disconnect.
        """
        self.emulator_launchers[launcher_address].backdoor_emulator_disconnect_device()

    def backdoor_emulator_connect_device(self, launcher_address: int) -> None:
        """
        Connect the emulator addressed by the given launcher address.

        :param launcher_address: The identifier of the device we want to connect.
        """
        self.emulator_launchers[launcher_address].backdoor_emulator_connect_device()

    def backdoor_run_function_on_device(
        self, launcher_address: int, function_name: str, arguments: list[Any] | None = None
    ) -> list[bytes]:
        """
        Run a function with the given arguments on the emulator addressed by the launcher address.

        :param launcher_address: The identifier of the device we want to run the function on.
        :param function_name: The name of the function to run on the device.
        :param arguments: The arguments to pass to the function.
        """
        return self.emulator_launchers[launcher_address].backdoor_run_function_on_device(
            function_name, arguments
        )


class CommandLineEmulatorLauncher(EmulatorLauncher):
    def __init__(
        self,
        test_name: str,
        device: str,
        emulator_path: str,
        var_dir: str,
        port: int,
        options: dict[str, Any],
    ) -> None:
        super(CommandLineEmulatorLauncher, self).__init__(
            test_name, device, emulator_path, var_dir, port, options
        )
        try:
            self.command_line = options["emulator_command_line"]
        except KeyError:
            raise KeyError(
                "To use a command line emulator launcher, the 'emulator_command_line' option "
                "must be provided as part of the options dictionary"
            )

        try:
            self.wait = options["emulator_wait_to_finish"]
        except KeyError:
            self.wait = False

        try:
            self._cwd_emulator_path = options["emulator_cwd_emulator_path"]
        except KeyError:
            self._cwd_emulator_path = False

        self._process = None
        self._log_file = None

    def _open(self) -> None:
        self._log_file = open(
            log_filename(
                self._test_name, "cmdemulator", self._device, TestModes.RECSIM, self._var_dir
            ),
            "w",
        )
        self._call_command_line(self.command_line.format(port=self._port))

    def _call_command_line(self, command_line: str | list[str]) -> None:
        if self._cwd_emulator_path:
            cwd = self._emulator_path
        else:
            cwd = None
        self._process = psutil.Popen(
            command_line,
            cwd=cwd,
            creationflags=subprocess.CREATE_NEW_CONSOLE,
            stdout=self._log_file,
            stderr=subprocess.STDOUT,
        )

        if self.wait:
            self._process.wait()

    def _close(self) -> None:
        print("Closing commandline emulator.")
        # We need to catch psutil.NoSuchProcess as it is possible:
        # * the main process may exit after the children have terminated
        #   and before terminate() can be called by us on it
        # * terminating one child may lead to another exiting before
        #   we call terminate() ourselves on it
        proc = self._process
        assert proc is not None
        children = proc.children(recursive=True)
        for child in children:
            if child is not None:
                try:
                    if child.is_running():
                        child.terminate()
                    child.wait()
                except psutil.NoSuchProcess:
                    pass
        if self._process is not None:
            try:
                if self._process.is_running():
                    self._process.terminate()
                self._process.wait()
            except psutil.NoSuchProcess:
                pass
        if self._log_file is not None:
            self._log_file.close()

    def backdoor_get_from_device(
        self, variable: str, *args: list[Any], **kwargs: dict[str, Any]
    ) -> str:
        raise ValueError("Cannot use backdoor for an arbitrary command line launcher")

    def backdoor_set_on_device(
        self, variable: str, value: EmulatorValue, *args: list[Any], **kwargs: dict[str, Any]
    ) -> None:
        raise ValueError("Cannot use backdoor for an arbitrary command line launcher")

    def backdoor_emulator_disconnect_device(
        self, *args: list[Any], **kwargs: dict[str, Any]
    ) -> None:
        raise ValueError("Cannot use backdoor for an arbitrary command line launcher")

    def backdoor_emulator_connect_device(self, *args: list[Any], **kwargs: dict[str, Any]) -> None:
        raise ValueError("Cannot use backdoor for an arbitrary command line launcher")

    def backdoor_run_function_on_device(
        self, function_name: str, arguments: list[Any] | None = None
    ) -> list[bytes]:
        raise ValueError("Cannot use backdoor for an arbitrary command line launcher")


class BeckhoffEmulatorLauncher(CommandLineEmulatorLauncher):
    def __init__(
        self,
        test_name: str,
        device: str,
        emulator_path: str,
        var_dir: str,
        port: int,
        options: dict[str, Any],
    ) -> None:
        try:
            self.beckhoff_root = options["beckhoff_root"]
        except KeyError:
            raise KeyError(
                "To use a beckhoff emulator launcher, the 'beckhoff_root' and 'tpy_file_path' "
                "options must be provided as part of the options dictionary"
            )

        run_bat_file = os.path.join(self.beckhoff_root, "run.bat")
        if IOCRegister.test_mode == TestModes.NOSIM:
            # if in NOSIM do absolutely nothing ie call rundll32
            run_bat_file = "C:\\Windows\\System32\\rundll32.exe"
        if os.path.exists(run_bat_file):
            options["emulator_command_line"] = run_bat_file
            options["emulator_wait_to_finish"] = True
            super(BeckhoffEmulatorLauncher, self).__init__(
                test_name, device, emulator_path, var_dir, port, options
            )
        else:
            raise IOError("Unable to find run.bat. Trying to run {} \n".format(run_bat_file))


class DAQMxEmulatorLauncher(CommandLineEmulatorLauncher):
    def __init__(
        self,
        test_name: str,
        device: str,
        emulator_path: str,
        var_dir: str,
        port: int,
        options: dict[str, Any],
    ) -> None:
        labview_scripts_dir = os.path.join(DEVICE_EMULATOR_PATH, "other_emulators", "DAQmx")
        self.start_command = os.path.join(labview_scripts_dir, "start_sim.bat")
        self.stop_command = os.path.join(labview_scripts_dir, "stop_sim.bat")
        options["emulator_command_line"] = self.start_command
        options["emulator_wait_to_finish"] = True
        super(DAQMxEmulatorLauncher, self).__init__(
            test_name, device, emulator_path, var_dir, port, options
        )

    def _close(self) -> None:
        self.disconnect_device()
        super(DAQMxEmulatorLauncher, self)._close()

    def disconnect_device(self) -> None:
        self._call_command_line(self.stop_command)

    def reconnect_device(self) -> None:
        self._call_command_line(self.start_command)
