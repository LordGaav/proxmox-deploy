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

from .cloudinit.templates import ask_cloudinit_questions
from .cloudinit import generate_seed_iso
from .exceptions import CommandInvocationException
from .proxmox import ProxmoxClient, ask_proxmox_questions
from .version import NAME, VERSION, BUILD, DESCRIPTION
from argparse import ArgumentParser
from configobj import ConfigObj
from proxmoxer import ProxmoxAPI, ResourceException
import logging
import os
import sys

root_logger = logging.getLogger(None)
root_logger.addHandler(logging.StreamHandler())
base_logger = logging.getLogger("proxmoxdeploy")
base_logger.setLevel(logging.INFO)
logger = logging.getLogger("proxmoxdeploy.cli")


def get_arguments():
    initial_parser = ArgumentParser(add_help=False)
    initial_parser.add_argument("--config", metavar="CFG", type=str,
                                help="Config file to load")
    initial_parser.add_argument("--version", action="store_true",
                                default=False,
                                help="Display version information and exit")

    args, unknown_args = initial_parser.parse_known_args()

    config = {}
    if args.config:
        config = ConfigObj(args.config)

    parser = ArgumentParser(description=DESCRIPTION)
    parser.add_argument("--config", metavar="CFG", type=str,
                        help="Config file to load.")
    parser.add_argument("--proxmox-host", metavar="HOST", type=str,
                        default=config.get("proxmox-host", None),
                        help="Proxmox API host.")
    parser.add_argument("--proxmox-user", metavar="USER", type=str,
                        default=config.get("proxmox-user", "root"),
                        help="Proxmox API user.")
    parser.add_argument("--cloud-images-dir", metavar="DIR", type=str,
                        default=config.get("cloud-images-dir", None),
                        help="Directory containing Cloud images.")
    args = parser.parse_args()

    if not args.proxmox_host:
        logger.error("No Proxmox API host was supplied.")
        sys.exit(1)

    if not args.cloud_images_dir:
        logger.error("No directory containing Cloud images specified.")
        sys.exit(1)

    return args


def interact_with_user(args, api):
    proxmox_answers = ask_proxmox_questions(api)
    cloudinit_answers = ask_cloudinit_questions(
        cloud_images_dir=args.cloud_images_dir)
    return (proxmox_answers, cloudinit_answers)


def main():
    logger.info("{0} version {1} (build {2}) starting...".format(
        NAME, VERSION, BUILD))

    args = get_arguments()
    api = ProxmoxClient(ProxmoxAPI(args.proxmox_host, port="22", timeout=600,
                                   user=args.proxmox_user, backend="openssh"))

    logger.info("Asking user for configuration input")
    try:
        (proxmox, cloudinit) = interact_with_user(args, api)
        context = dict(proxmox, **cloudinit)
    except KeyboardInterrupt:
        logger.info("Aborted by user")
        sys.exit(0)

    logger.info("")
    logger.info("")
    logger.info("Starting provisioning process")

    try:
        api.create_vm(node=proxmox['node'], vmid=proxmox['vmid'],
                      name=cloudinit['name'], cpu=proxmox['cpu'],
                      cpu_family=proxmox['cpu_family'],
                      memory=proxmox['memory'], vlan_id=cloudinit['vlan_id'])
    except ResourceException:
        logger.error("Failed to create VM")
        sys.exit(1)

    try:
        cloudinit_iso = generate_seed_iso(context=context)
        logger.debug("File generated at: {0}".format(cloudinit_iso))

        logger.info("Uploading cloud-init seed ISO to Proxmox")
        api.attach_seed_iso(node=proxmox['node'], storage=proxmox["storage"],
                            vmid=proxmox['vmid'], iso_file=cloudinit_iso)
        logger.info("Uploading cloud image to Proxmox")
        disk_size = proxmox['disk'] * 1024 ** 2
        api.attach_base_disk(node=proxmox['node'], storage=proxmox["storage"],
                             vmid=proxmox['vmid'],
                             img_file=cloudinit['image'],
                             disk_size=disk_size)
        logger.info("Adding serial console to VM")
        api.attach_serial_console(node=proxmox['node'], vmid=proxmox['vmid'])
    except CommandInvocationException as cie:
        logger.error("Provisioning failed")
        if hasattr(cie, "stdout") or hasattr(cie, "stderr"):
            logger.error("Command output was:")
        if hasattr(cie, "stdout"):
            logger.error(cie.stdout)
        if hasattr(cie, "stderr"):
            logger.error(cie.stderr)
        sys.exit(1)
    finally:
        if os.path.exists(cloudinit_iso):
            logger.debug("Removing seed ISO file")
            os.remove(cloudinit_iso)

    if cloudinit['start_vm']:
        logger.info("Starting VM")
        api.start_vm(node=proxmox['node'], vmid=proxmox['vmid'])

    logger.info("Virtual Machine provisioning completed")

if __name__ == "__main__":
    main()
