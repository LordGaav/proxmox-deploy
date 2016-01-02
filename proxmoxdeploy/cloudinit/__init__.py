# proxmox-deploy is cli-based deployment tool for Proxmox
#
# Copyright (c) 2015 Nick Douma <n.douma@nekoconeko.nl>
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program. If not, see http://www.gnu.org/licenses/.

from ..exceptions import CommandInvocationException
from .templates import generate_user_data, generate_meta_data
from distutils.spawn import find_executable
from shutil import rmtree
from subprocess import Popen, PIPE
import logging
import os
import shlex
import tempfile

BUILDISO_COMMAND = None
if not BUILDISO_COMMAND:
    GENISOIMAGE_COMMAND = find_executable("genisoimage")
    if GENISOIMAGE_COMMAND:
        BUILDISO_COMMAND = GENISOIMAGE_COMMAND + \
            " -output '{0}' -volid cidata -joliet -rock '{1}'"

if not BUILDISO_COMMAND:
    MKISOFS_COMMAND = find_executable("mkisofs")
    if MKISOFS_COMMAND:
        BUILDISO_COMMAND = MKISOFS_COMMAND + \
            " -o '{0}' -V cidata -rock '{1}'"

if not BUILDISO_COMMAND:
    raise RuntimeError(
        "genisoimage (Linux) or mkisofs (FreeBSD) command is missing, "
        "make sure it is installed.")

CLI_ECHO_COMMANDS = False
CLI_ECHO_COMMAND_MESSAGE = "  Running command: `{0}`"
CLI_COMMAND_PREFIX = ""

logger = logging.getLogger(__name__)


def call_cli(command, error_message=None, expected_return_code=0):
    """
    Calls the given CLI command and handles output. If the return code does
    not match the expected_return_code, a CommandInvocationException
    will be raised.

    Parameters
    ----------
    command: str
        Command to execute, will be parsed by shlex.
    error_message: str
        Custom error message to display if the return code does not match
        expected_return_code.
    expected_return_code: int
        Expected return code, raises a CommandInvocationException otherwise.

    Returns
    -------
    Tuple containing (stdout, stderr).
    """
    cmd = str(command.encode("utf-8").decode("ascii", "ignore"))
    if CLI_COMMAND_PREFIX:
        cmd = "{0} {1}".format(CLI_COMMAND_PREFIX, cmd)

    if CLI_ECHO_COMMANDS:
        print CLI_ECHO_COMMAND_MESSAGE.format(cmd)

    env = os.environ.copy()
    proc = Popen(shlex.split(cmd), stdout=PIPE, stderr=PIPE, env=env)
    stdout, stderr = proc.communicate()

    if proc.returncode != expected_return_code:
        if error_message:
            raise CommandInvocationException(
                message="{0}: {1}".format(error_message, stderr),
                stdout=stdout,
                stderr=stderr
            )
        else:
            raise CommandInvocationException(
                message="Failed to execute {0}: {1}".format(cmd, stderr),
                stdout=stdout,
                stderr=stderr
            )

    return (stdout, stderr)


def generate_seed_iso(context, output_file=None):
    """
    Calls genisofs to create an cloud-init compatible ISO file. This ISO file
    can be used to seed a cloud-init installation using the "No Cloud" approach
    (https://cloudinit.readthedocs.org/en/latest
    /topics/datasources.html#no-cloud).

    Parameters
    ----------
    output_file: str
        Filename where the ISO file will be created.
    context: dict
        Dict-like object to use as context for generating the user-data and
        meta-data files.
    """
    if not output_file:
        output_file = tempfile.mkstemp(prefix="cloudinit-seed-iso-",
                                       suffix=".iso")[1]

    temp_dir = tempfile.mkdtemp(prefix="cloudinit-seed-iso")
    logger.info("Generating cloud-init seed files at {0}".format(temp_dir))
    generate_user_data(os.path.join(temp_dir, "user-data"), context)
    generate_meta_data(os.path.join(temp_dir, "meta-data"), context)

    logger.info("Generating cloud-init seed ISO at {0}".format(output_file))
    call_cli(BUILDISO_COMMAND.format(output_file, temp_dir))

    logger.info("Removing cloud-init temp files")
    rmtree(temp_dir)
    return output_file
