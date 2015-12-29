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

from .questions import QuestionGroup, IntegerQuestion, EnumQuestion, NoAskQuestion
import math


def ask_proxmox_questions(proxmox):
    """
    Asks the user questions about the Proxmox VM to provision.

    Parameters
    ----------
    proxmox: ProxmoxClient

    Returns
    -------
    dict of key-value pairs of answered questions.
    """
    node_q = EnumQuestion("Proxmox Node to create VM on",
                          valid_answers=proxmox.get_nodes())
    node_q.ask()
    chosen_node = node_q.answer

    storage_q = EnumQuestion("Storage to create disk on",
                             valid_answers=proxmox.get_storage(chosen_node))
    storage_q.ask()
    chosen_storage = storage_q.answer

    proxmox_questions = QuestionGroup([
        ("node", NoAskQuestion(question=None, default=chosen_node)),
        ("storage", NoAskQuestion(question=None, default=chosen_storage)),
        ("cpu", IntegerQuestion(
            "Amount of CPUs", min_value=1,
            max_value=proxmox.get_max_cpu(chosen_node))),
        ("memory", IntegerQuestion(
            "Amount of Memory (MB)", min_value=32,
            max_value=proxmox.get_max_memory(chosen_node))),
        ("disk", IntegerQuestion(
            "Size of disk (GB)", min_value=1,
            max_value=proxmox.get_max_disk_size(chosen_node, chosen_storage)))
    ])

    proxmox_questions.ask_all()
    return proxmox_questions.flatten_answers()


class ProxmoxClient(object):
    """
    Wrapper around Proxmoxer, to encapsulate retrieval logic in one place.
    """
    def __init__(self, client):
        """
        Parameters
        ----------
        client: ProxmoxAPI
            ProxmoxAPI intance
        """
        self.client = client

    def get_nodes(self):
        """
        Retrieve a list of available nodes.

        Returns
        -------
        List of node names.
        """
        return [_node['node'] for _node in self.client.nodes.get()]

    def get_max_cpu(self, node=None):
        """
        Get maximum available cpus.

        Parameters
        ----------
        node: str
            If provided, will retrieve the cpu limit for this specific node. If
            not, will return the lowest common denomitor for all nodes.

        Returns
        -------
        Amount of cpus available.
        """
        if node:
            status = self.client.nodes(node).status.get()
            return status['cpuinfo']['cpus'] * status['cpuinfo']['sockets']
        else:
            return min([_node['maxcpu'] for _node in self.client.nodes.get()])

    def get_max_memory(self, node=None):
        """
        Get maximum amount of memory available.

        Parameters
        ----------
        node: str
            If provided, will retrieve the memory limit for this specific node.
            If not, will return the lowest common denomitor for all nodes.

        Returns
        -------
        Amount of memory available in megabytes.
        """
        if node:
            status = self.client.nodes(node).status.get()
            return int(math.floor(
                status['memory']['total'] / 1024 ** 2))
        else:
            return min(
                [int(math.floor(_node['maxmem'] / 1024 ** 2))
                 for _node in self.client.nodes.get()]
            )

    def get_storage(self, node):
        """
        Get available storages.

        Parameters
        ----------
        node: str
            If provided, will retrieve the storages for this specific node. If
            not, will retrieve the global storages.

        Returns
        -------
        List of storages available.
        """
        storages = []
        for storage in self.client.nodes(node).storage.get():
            if "images" in storage['content'].split(","):
                storages.append(storage['storage'])
        return storages

    def get_max_disk_size(self, node=None, storage=None):
        """
        Get the maximum amount of disk space available.

        Parameters
        ----------
        node: str
            If provided, will retrieve the disk limit for this specific node. A
            storage must also be specified. If not, will return the lowest
            common denomitor for all storages.
        storage: str
            Name of storage to lookup maximum amount for.

        Returns
        -------
        Amount of disk space available in gigabytes.
        """
        if node:
            if not storage:
                raise ValueError(
                    "A storage must also be specified for the given node")
            _storage = self.client.nodes(node).storage.get(storage=storage)[0]
            return int(math.floor(
                _storage['avail'] / 1024 ** 3))
        else:
            return min([int(math.floor(_node['maxdisk'] / 1024 ** 3))
                        for _node in self.client.nodes.get()])
