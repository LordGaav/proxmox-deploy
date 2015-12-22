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

from .exceptions import SSHCommandInvocationException
from contextlib import contextmanager
from paramiko import SSHClient, WarningPolicy
from paramiko.ssh_exception import PasswordRequiredException
import getpass
import types


def connect_ssh(hostname, username, prompt_for_password=True):
    """
    Connect to the given hostname with the given username. Will try to use a
    key from your ssh-agent, and prompt for a password if it isn't unlocked yet.

    Parameters
    ----------
    hostname: str
        Hostname to connect to.
    username: str
        Username to connect as.
    prompt_for_password: boolean
        Prompt for password for unopen keys. If False, will raise an exception
        if no valid open key is found.

    Returns
    -------
    paramiko ssh instance.
    """
    ssh = SSHClient()
    ssh.set_missing_host_key_policy(WarningPolicy())

    try:
        ssh.connect(hostname, username=username)
    except PasswordRequiredException:
        if not prompt_for_password:
            raise
        password = getpass("SSH Private Key password: ")
        ssh.connect(hostname, username=username, password=password)

    def command(self, command, raise_on_error=True):
        chan = self._transport.open_session()
        chan.exec_command(command)
        stdout = chan.makefile('r').read()
        stderr = chan.makefile_stderr('r').read()
        status = chan.recv_exit_status()
        if status != 0:
            raise SSHCommandInvocationException(
                "Failed to execute command `{0}`: {1}"
                    .format(command, stderr[:stderr.rfind("\n")]),
                stdout=stdout,
                stderr=stderr
            )
        return (status, stdout, stderr)

    ssh.command = types.MethodType(command, ssh)
    return ssh


@contextmanager
def ssh_context(hostname, username, prompt_for_password=True):
    """
    Initialize a SSH connection and yields the connection.
    """
    ssh = connect_ssh(hostname, username, prompt_for_password)
    try:
        yield ssh
    finally:
        ssh.close()


@contextmanager
def sftp_context(ssh):
    """
    Initialize an SFTP Channel on an already open SSH connection, and yields it.
    """
    sftp = ssh.opensftp()
    try:
        yield sftp
    finally:
        sftp.close()
