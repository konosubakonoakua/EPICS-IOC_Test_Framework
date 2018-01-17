import os
import imp
import importlib
import unittest

import sys

import xmlrunner
import argparse
from contextlib import contextmanager

from utils.device_launcher import device_launcher, device_collection_launcher
from utils.lewis_launcher import LewisLauncher, LewisNone
from utils.ioc_launcher import IocLauncher, EPICS_TOP
from utils.free_ports import get_free_ports
from utils.test_modes import TestModes


def package_contents(package_name):
    """
    Finds all the modules in a package.

    :param package_name: the name of the package
    :return: a set containing all the module names
    """
    filename, pathname, description = imp.find_module(package_name)
    if filename:
        raise ImportError('Not a package: %r', package_name)
    # Use a set because some may be both source and compiled.
    return set([os.path.splitext(module)[0] for module in os.listdir(pathname)
                if module.endswith('.py') and not module.startswith("__init__")])


def load_module(name):
    """
    Loads a module based on its name.

    :param name: the name of the module
    :return: a reference to the module
    """
    return importlib.import_module(name, )


@contextmanager
def modified_environment(**kwargs):
    """
    Modifies the environment variables as required then returns them to their original state.

    :param kwargs: the settings to apply
    """
    # Copying old values
    old_env = {name: os.environ.get(name, '') for name in kwargs.keys()}

    # Apply new settings and then yield
    os.environ.update(kwargs)
    yield

    # Restore old values
    os.environ.update(old_env)


def run_test(prefix, test_module, device_launchers):
    """
    Runs the tests for the specified set of devices.

    :param prefix: the instrument prefix
    :param test_module: the test module
    :param device_launchers: context manager that launches the necessary iocs and associated emulators
    """
    # Define an environment variable with the prefix in it
    # This can then be accessed elsewhere
    os.environ["testing_prefix"] = prefix

    # Need to set epics address list to local broadcast otherwise channel access won't work
    settings = {
        'EPICS_CA_ADDR_LIST': "127.255.255.255"
    }

    with modified_environment(**settings), device_launchers:

        runner = xmlrunner.XMLTestRunner(output='test-reports')

        test_classes = [getattr(test_module, s) for s in dir(test_module) if s.endswith("Tests")]

        if len(test_classes) < 1:
            raise ValueError("No test suites found in {}".format(test_module.__name__))

        test_results = []
        for test_class in test_classes:
            print("Running tests in {}".format(test_class.__name__))
            test_suite = unittest.TestLoader().loadTestsFromTestCase(test_class)
            test_results.append(runner.run(test_suite).wasSuccessful())
        return all(result is True for result in test_results)


def make_device_launchers_from_module(test_module, recsim):
    """
    Returns a list of device launchers for the given test module
    :param test_module: module containing IOC tests
    :param recsim: True to run in recsim. False to run in devsim.
    :return: list of device launchers (context managers which launch ioc + emulator pairs)
    """

    try:
        iocs = test_module.IOCS
    except AttributeError:
        raise AttributeError("Expected module '{}' to contain an IOCS attribute".format(test_module.__name__))

    if len(iocs) < 1:
        raise ValueError("Need at least one IOC to launch")

    print("Testing module {} in {} mode.".format(test_module.__name__, "recsim" if recsim else "devsim"))

    device_launchers = []
    for ioc in iocs:

        free_port = str(get_free_ports(1)[0])
        macros = ioc["macros"]
        macros['EMULATOR_PORT'] = free_port

        ioc_launcher = IocLauncher(device=ioc["name"],
                                   directory=ioc["directory"],
                                   macros=macros,
                                   use_rec_sim=recsim,
                                   var_dir=var_dir,
                                   port=free_port)

        if "emulator" in ioc and not recsim:

            emulator_name = ioc["emulator"]
            try:
                emulator_protocol = ioc["emulator_protocol"]
            except KeyError:
                emulator_protocol = "stream"

            try:
                emulator_device_package = ioc["emulator_package"]
            except KeyError:
                emulator_device_package = "lewis_emulators"

            try:
                emulator_path = ioc["emulator_path"]
            except KeyError:
                emulator_path = os.path.join(EPICS_TOP, "support", "DeviceEmulator", "master")

            lewis_launcher = LewisLauncher(
                device=emulator_name,
                python_path=os.path.abspath(arguments.python_path),
                lewis_path=os.path.abspath(arguments.emulator_path),
                lewis_protocol=emulator_protocol,
                lewis_additional_path=emulator_path,
                lewis_package=emulator_device_package,
                var_dir=var_dir,
                port=free_port
            )

        elif "emulator" in ioc:
            lewis_launcher = LewisNone(ioc["emulator"])
        else:
            lewis_launcher = None

        device_launchers.append(device_launcher(ioc_launcher, lewis_launcher))

    return device_launchers


def load_module_by_name_and_run_tests(module_name):
    test_module = load_module("tests.{}".format(module_name))

    try:
        modes = test_module.TEST_MODES
    except AttributeError:
        raise ValueError("Expected test module {} to contain a TEST_MODES attribute".format(test_module.__name__))

    test_results = []
    for mode in modes:
        device_launchers = make_device_launchers_from_module(test_module, recsim=(mode == TestModes.RECSIM))
        test_results.append(run_test(arguments.prefix, test_module, device_collection_launcher(device_launchers)))

    return all(test_result is True for test_result in test_results)


if __name__ == '__main__':

    pythondir = os.environ.get("PYTHONDIR", None)
    if pythondir is not None:
        emulator_path = os.path.join(pythondir, "scripts")
    else:
        emulator_path = None

    parser = argparse.ArgumentParser(
        description='Test an IOC under emulation by running tests against it')
    parser.add_argument('-l', '--list-devices',
                        help="List available devices for testing.", action="store_true")
    parser.add_argument('-pf', '--prefix', default=os.environ.get("MYPVPREFIX", None),
                        help='The instrument prefix; e.g. TE:NDW1373')
    parser.add_argument('-tm', '--test-module', default=None, nargs="+",
                        help="Test module to run")
    parser.add_argument('-e', '--emulator-path', default=emulator_path,
                        help="The path of the lewis.py file")
    parser.add_argument('-py', '--python-path', default="C:\Instrument\Apps\Python\python.exe",
                        help="The path of python.exe")
    parser.add_argument('--var-dir', default=None,
                        help="Directory in which to create a log dir to write log file to and directory in which to "
                             "create tmp dir which contains environments variables for the IOC. Defaults to "
                             "environment variable ICPVARDIR and current dir if empty.")

    arguments = parser.parse_args()

    if arguments.list_devices:
        print("Available tests:")
        print('\n'.join(package_contents("tests")))
        sys.exit(0)

    var_dir = arguments.var_dir if arguments.var_dir is not None else os.getenv("ICPVARDIR", os.curdir)

    if arguments.prefix is None:
        print("Cannot run without instrument prefix")
        sys.exit(-1)

    if arguments.emulator_path is None:
        print("Cannot run without emulator path")
        sys.exit(-1)

    module_results = []

    if arguments.test_module is not None:
        for test_module in arguments.test_module:
            try:
                module_results.append(load_module_by_name_and_run_tests(test_module))
            except Exception as e:
                print("ERROR: {}: {}".format(e.__class__.__name__, e))
                module_results.append(False)
    else:
        for module_name in package_contents("tests"):
            try:
                module_results.append(load_module_by_name_and_run_tests(module_name))
            except Exception as e:
                print("ERROR: {}: {}".format(e.__class__.__name__, e))
                module_results.append(False)

    success = all(result is True for result in module_results)
    sys.exit(0 if success else 1)
