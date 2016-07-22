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

from .cloudinit.templates import VALID_IMAGE_FORMATS, VALID_COMPRESSION_FORMATS
from .exceptions import SSHCommandInvocationException
from .questions import QuestionGroup, IntegerQuestion, EnumQuestion, \
    NoAskQuestion
from openssh_wrapper import SSHError
import logging
import math
import os.path

CPU_FAMILIES = [
    "486", "athlon", "pentium", "pentium2", "pentium3", "coreduo", "core2duo",
    "kvm32", "kvm64", "qemu32", "qemu64", "phenom", "Conroe", "Penryn",
    "Nehalem", "Westmere", "SandyBridge", "IvyBridge", "Haswell", "Broadwell",
    "Opteron_G1", "Opteron_G2", "Opteron_G3", "Opteron_G4", "Opteron_G5",
    "host"
]

logger = logging.getLogger(__name__)


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
    available_nodes = proxmox.get_nodes()
    if len(available_nodes) == 1:
        chosen_node = available_nodes[0]
    else:
        node_q = EnumQuestion("Proxmox Node to create VM on",
                              valid_answers=available_nodes,
                              default=available_nodes[0])
        node_q.ask()
        chosen_node = node_q.answer

    available_storage = proxmox.get_storage(chosen_node)
    storage_q = EnumQuestion("Storage to create disk on",
                             valid_answers=available_storage,
                             default=available_storage[0])
    storage_q.ask()
    chosen_storage = storage_q.answer

    proxmox_questions = QuestionGroup([
        ("node", NoAskQuestion(question=None, default=chosen_node)),
        ("storage", NoAskQuestion(question=None, default=chosen_storage)),
        ("cpu", IntegerQuestion(
            "Amount of CPUs", min_value=1,
            max_value=proxmox.get_max_cpu(chosen_node))),
        ("cpu_family", EnumQuestion(
            "Emulate which CPU family",
            default="host", valid_answers=CPU_FAMILIES)),
        ("memory", IntegerQuestion(
            "Amount of Memory (MB)", min_value=32,
            max_value=proxmox.get_max_memory(chosen_node))),
        ("disk", IntegerQuestion(
            "Size of disk (GB)", min_value=4,
            max_value=proxmox.get_max_disk_size(chosen_node, chosen_storage))),
        ("vmid", IntegerQuestion("Virtual Machine id", min_value=1,
                                 default=proxmox.get_next_vmid()))
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

    def get_next_vmid(self):
        """
        Retrieve the next available vmid.

        Returns
        -------
        The next available vmid.
        """
        return self.client.cluster.nextid.get()

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
            if ("images" in storage['content'].split(",")
                    and storage['type'] in ("dir", "lvm", "lvmthin", "nfs")):
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

    def create_vm(self, node, vmid, name, cpu, cpu_family, memory,
                  vlan_id=None):
        """
        Creates a VM.

        Parameters
        ----------
        node: str
            Name of the node to create the VM on.
        vmid: int
            ID of the VM.
        name: str
            Name of the VM.
        cpu: int
            Number of CPU cores.
        cpu_family: str
            What CPU family to emulate.
        memory: int
            Megabytes of memory.
        vlan_id: int
            VLAN ID of the network device.
        """
        node = self.client.nodes(node)
        net0 = "virtio,bridge=vmbr0"
        if vlan_id:
            net0 += ",tag={0}".format(vlan_id)

        logger.info("Creating Virtual Machine")
        node.qemu.create(
            vmid=vmid, name=name, sockets=1, cores=cpu, cpu=cpu_family,
            memory=memory, net0=net0
        )

    def _upload(self, ssh, filename):
        logger.info("Transferring image to Proxmox")
        tmpfile = os.path.join("/tmp", os.path.basename(filename))
        with open(filename) as _file:
            ssh.upload_file_obj(_file, tmpfile)
        return tmpfile

    def _decompress_image(self, ssh, tmpfile):
        _, ext = os.path.splitext(tmpfile)
        if ext in VALID_COMPRESSION_FORMATS:
            logger.info("Decompressing image")
            if ext == ".xz":
                command = "unxz"
            elif ext == ".gz":
                command = "gunzip"
            else:
                command = "bunzip2"
            stdout, stderr = ssh._exec("{0} '{1}'".format(command,
                                                          tmpfile))
            if len(stdout) > 0 or len(stderr) > 0:
                raise SSHCommandInvocationException(
                    "Failed to decompress image", stdout=stdout, stderr=stderr)
            tmpfile, _ = os.path.splitext(tmpfile)

        _, ext = os.path.splitext(tmpfile)
        if ext not in VALID_IMAGE_FORMATS:
            raise RuntimeError("Provided image is not of a valid type: {0}"
                               .format(", ".join(VALID_IMAGE_FORMATS)))

        return tmpfile

    def _get_virtual_disk_size(self, ssh, tmpfile):
        stdout, stderr = ssh._exec("qemu-img info '{0}'".format(tmpfile))

        if len(stdout) == 0 or len(stderr) > 0:
            raise SSHCommandInvocationException(
                "Failed to get virtual disk size", stdout=stdout,
                stderr=stderr)

        virtual_size = 0
        try:
            for line in stdout.split("\n"):
                if "virtual size" in line:
                    virtual_size = line.split("(")[1].split()[0]
                    virtual_size = int(math.ceil(int(virtual_size) / 1024))
                    break
        except:
            pass
        return virtual_size

    def _allocate_disk(self, ssh, storage, vmid, diskname, disk_size,
                       storagename, disk_format):
        logger.info("Allocating virtual disk")
        stdout, stderr = ssh._exec(
            "pvesm alloc '{0}' {1} '{2}' {3} -format {4}".format(
                storage, vmid, diskname,
                disk_size, disk_format
            )
        )
        if storagename not in stdout and len(stderr) > 0:
            raise SSHCommandInvocationException(
                "Failed to allocate disk", stdout=stdout, stderr=stderr)

    def _get_device_path(self, ssh, storagename):
        stdout, stderr = ssh._exec(
            "pvesm path '{0}'".format(storagename)
        )

        if len(stderr) > 0:
            raise SSHCommandInvocationException(
                "Failed to get path for disk", stdout=stdout, stderr=stderr)

        return stdout.strip()

    def _copy_image_into_disk(self, ssh, disk_format, tmpfile, devicepath):
        logger.info("Copying image into virtual disk")
        stdout, stderr = ssh._exec(
            "qemu-img convert -O {0} '{1}' {2}".format(disk_format, tmpfile,
                                                       devicepath)
        )

        if len(stderr) > 0:
            raise SSHCommandInvocationException(
                "Failed to copy file into disk", stdout=stdout, stderr=stderr)

    def _upload_to_storage(self, ssh_session, storage, vmid, filename,
                           diskname, storagename, disk_format="raw",
                           disk_size=None):
        """
        Upload a file into a datastore. The steps executed are:
          1. The file is uploaded via SFTP to /tmp.
          2. A new disk is allocated using `pvesm`.
          3. The path of this disk is retrieved using `pvesm`.
          4. The file is converted and transfered into the disk
          using `qemu-img`.
          5. The temporary file is removed.

        Parameters
        ----------
        ssh_session: ProxmoxBaseSSHSession subclass
            This is an internal class used by proxmoxer, we're using its ssh
            transfer methods for various operations.
        storage: str
            Name of storage to upload the file into.
        vmid: int
            ID of the VM to associate the file with. This is enforced by
            Proxmox.
        filename: str
            Local filename of the file.
        diskname: str
            Name of the disk to allocate.
        storagename: str
            Full canonical name of the disk.
        disk_format: raw or qcow2
            Format of the file. The source type doesn't matter, as we will call
            `qemu-img` to both transfer and convert the file into the disk.
        disk_size: int
            Override the disk size. If not specified, the size is calculated
            from the file. In kilobytes.
        """
        try:
            tmpfile = self._upload(ssh_session, filename)
            tmpfile = self._decompress_image(ssh_session, tmpfile)
            image_size = self._get_virtual_disk_size(ssh_session, tmpfile)

            if not disk_size:
                logger.warning("Setting disk size to {0}K".format(image_size))
                disk_size = image_size
            elif image_size > disk_size:
                logger.warning("Provided disk size was too small, "
                               "increasing to {0}K".format(image_size))
                disk_size = image_size

            self._allocate_disk(ssh_session, storage, vmid, diskname,
                                disk_size, storagename, disk_format)

            devicepath = self._get_device_path(ssh_session, storagename)

            self._copy_image_into_disk(ssh_session, disk_format, tmpfile,
                                       devicepath)
        finally:
            if tmpfile:
                logger.info("Removing temporary disk file")
                ssh_session._exec("rm '{0}'".format(tmpfile))

    def _upload_to_flat_storage(self, storage, vmid, filename, disk_format,
                                disk_label, disk_size=None):
        """
        Generates appropriate names for uploading a file to a 'dir' datastore.
        Actual work is done by _upload_to_storage.

        Parameters
        -----------
        storage: str
            Name of storage to upload the file into.
        vmid: int
            ID of the VM to associate the file with. This is enforced by
            Proxmox.
        filename: str
            Local filename of the file.
        disk_format: raw or qcow2
            Format of the file. The source type doesn't matter, as we will call
            `qemu-img` to both transfer and convert the file into the disk.
        disk_label: str
            Label to incorporate in the resulting disk name.
        disk_size: int
            Override the disk size. If not specified, the size is calculated
            from the file. In kilobytes.

        Returns
        -------
        Full canonical name of the disk.
        """
        ssh_session = self.client._backend.session
        diskname = "vm-{0}-{1}.{2}".format(vmid, disk_label, disk_format)
        storagename = "{0}:{1}/{2}".format(storage, vmid, diskname)

        logger.info("Uploading to flat storage")
        self._upload_to_storage(ssh_session, storage, vmid, filename,
                                diskname, storagename, disk_format=disk_format,
                                disk_size=disk_size)

        return storagename

    def _upload_to_lvm_storage(self, storage, vmid, filename, disk_format,
                               disk_label, disk_size=None):
        """
        Generates appropriate names for uploading a file to a 'lvm' datastore.
        Actual work is done by _upload_to_storage.

        Parameters
        -----------
        storage: str
            Name of storage to upload the file into.
        vmid: int
            ID of the VM to associate the file with. This is enforced by
            Proxmox.
        filename: str
            Local filename of the file.
        disk_format: raw or qcow2
            Format of the file. Will be overridden into 'raw', because LVM only
            supports RAW disks.
        disk_label: str
            Label to incorporate in the resulting disk name.
        disk_size: int
            Override the disk size. If not specified, the size is calculated
            from the file. In kilobytes.

        Returns
        -------
        Full canonical name of the disk.
        """
        ssh_session = self.client._backend.session
        diskname = "vm-{0}-{1}".format(vmid, disk_label)
        storagename = "{0}:{1}".format(storage, diskname)

        logger.info("Uploading to LVM storage")
        # LVM only supports raw disks, overwrite the disk_format here.
        self._upload_to_storage(ssh_session, storage, vmid, filename,
                                diskname, storagename, disk_format="raw",
                                disk_size=disk_size)

        return storagename

    def upload(self, node, storage, vmid, filename, disk_format, disk_label,
               disk_size=None):
        """
        Upload a file into a datastore.

        Note that we can't yet upload a file to another node, only to the local
        node that we have an SSH connection with.

        Parameters
        ----------
        node: str
            Name of the node to upload to. See the note above.
        storage: str
            Name of storage to upload the file into.
        vmid: int
            ID of the VM to associate the file with. This is enforced by
            Proxmox.
        filename: str
            Local filename of the file.
        disk_format: raw or qcow2
            Format of the file.
        disk_label: str
            Label to incorporate in the resulting disk name.
        disk_size: int
            Override the disk size. If not specified, the size is calculated
            from the file. In kilobytes.
        """
        _node = self.client.nodes(node)
        _storage = _node.storage(storage)
        _type = _storage.status.get()['type']
        if _type in ("dir", "nfs"):
            diskname = self._upload_to_flat_storage(
                storage=storage, vmid=vmid, filename=filename,
                disk_label=disk_label, disk_format=disk_format,
                disk_size=disk_size)
        elif _type == "lvm" or _type == "lvmthin":
            diskname = self._upload_to_lvm_storage(
                storage=storage, vmid=vmid, filename=filename,
                disk_label=disk_label, disk_format=disk_format,
                disk_size=disk_size)
        else:
            raise ValueError(
                "Only dir, lvm, and lvmthin storage are supported at this time")
        return diskname

    def attach_seed_iso(self, node, storage, vmid, iso_file):
        """
        Upload a cloud-init seed ISO file, and attach it to a VM.

        Parameters
        ----------
        node: str
            Name of the node to upload to. See the note above.
        storage: str
            Name of storage to upload the file into.
        vmid: int
            ID of the VM to associate the file with. This is enforced by
            Proxmox.
        iso_file: str
            Local filename of the ISO file.
        """
        _node = self.client.nodes(node)
        diskname = self.upload(node, storage, vmid, iso_file,
                               disk_label="cloudinit-seed", disk_format="raw")
        _node.qemu(vmid).config.set(virtio1=diskname)

    def attach_base_disk(self, node, storage, vmid, img_file, disk_size):
        """
        Upload a Cloud base image, and attach it to a VM.

        Parameters
        ----------
        node: str
            Name of the node to upload to. See the note above.
        storage: str
            Name of storage to upload the file into.
        vmid: int
            ID of the VM to associate the file with. This is enforced by
            Proxmox.
        img_file: str
            Local filename of the ISO file.
        disk_size: int
            Size of the disk to allocate, in kilobytes.
        """
        _node = self.client.nodes(node)
        diskname = self.upload(node, storage, vmid, img_file,
                               disk_label="base-disk", disk_format="qcow2",
                               disk_size=disk_size)
        _node.qemu(vmid).config.set(virtio0=diskname, bootdisk="virtio0")
        try:
            logger.info("Resizing virtual disk")
            _node.qemu(vmid).resize.set(disk="virtio0", size=disk_size * 1024)
        except SSHError as se:
            if "disk size" not in str(se):
                raise se
            logger.error("Failed to set disk size, disk will probably be "
                         "bigger than expected")

    def start_vm(self, node, vmid):
        """
        Starts a VM.

        Parameters
        ----------
        node: str
            Node the VM resides on.
        vmid: int
            ID of VM to start.
        """
        _node = self.client.nodes(node)
        _node.qemu(vmid).status.start.create()

    def attach_serial_console(self, node, vmid):
        """
        Adds a serial console

        Parameters
        ----------
        node: str
            Node the VM resides on.
        vmid: int
            ID of VM to start.
        """
        _node = self.client.nodes(node)
        _node.qemu(vmid).config.set(serial0="socket")
