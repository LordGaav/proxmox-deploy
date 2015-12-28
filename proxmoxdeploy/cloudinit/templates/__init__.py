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

from jinja2 import Environment, PackageLoader, Template


def _generate_data(output_file, context, template_file, default_template):
    if not template_file:
        env = Environment(loader=PackageLoader("proxmoxdeploy.cloudinit"))
        template = env.get_template(default_template)
    else:
        template = Template(template_file.read())

    with open(output_file, "w") as output:
        output.write(template.render(context=context))


def generate_user_data(output_file, context, template_file=None):
    """
    Generates the user-data part of the "No Cloud" cloud-init approach.

    Parameters
    ----------
    output_file: str
        Filename where the user-data file will be created.
    context: dict
        Dict(-like) object where the required template variables can be looked
        up.
    template_file: file
        File to read the Jinja2 template to populate from. If not set, will load
        the default template. The file will be read to the end.
    """
    _generate_data(output_file, context, template_file, "user-data.j2")


def generate_meta_data(output_file, context, template_file=None):
    """
    Generates the meta-data part of the "No Cloud" cloud-init approach.

    Parameters
    ----------
    output_file: str
        Filename where the meta-data file will be created.
    context: dict
        Dict(-like) object where the required template variables can be looked
        up.
    template_file: file
        File to read the Jinja2 template to populate from. If not set, will load
        the default template. The file will be read to the end.
    """
    _generate_data(output_file, context, template_file, "meta-data.j2")
