proxmox-deploy
==============
Use this tool to deploy ``cloud-init`` enabled images from various Linux
distributions on Proxmox.

Proxmox does not support ``cloud-init`` enabled images out of the box. It's
possible to create template from manually installed VMs. However, with the
availability of ready to deploy images from most major Linux vendors, why
should you install a VM manually?

How it works
------------
cloud-init depends on two things:

1. A minimal base installation of the distribution, usually in the form of a
   raw or qcow2 image. I call this a *cloud image*.
2. The ``cloud-init`` package installed in the image.

cloud-init was originally made for Amazon EC2 and OpenStack. These platforms
have native support for cloud-init, and provide a datasource that ``cloud-init``
can use to configure the VM. However, there are few alternative datasources
available that will work, even if the platform itself has no native support for
``cloud-init``.

``proxmox-deploy`` uses the `NoCloud`_ datasource. For this approach, the VM
must have a copy of the *cloud image* as the first disk, and a read-only vfat or
iso9660 filesystem as the second disk. On this second disk, there must be two
files: ``user-data`` and ``meta-data``.

``proxmox-deploy`` takes care of generating the ``user-data`` and ``meta-data``
files based on user input.  ``proxmox-deploy`` also takes care of creating a
Proxmox VM and uploading the *cloud image* and ``cloud-init`` image into the
proper datastore. All that's left afterwards is turning on the VM.

How to install
--------------

All dependencies are installable using pip. To install globally, execute as
root:

.. code-block:: bash

    # pip install proxmox-deploy

Or to install into a virtualenv (as a normal user):

.. code-block:: bash

    $ virtualenv env
    $ . env/bin/activate
    $ pip install proxmox-deploy

Make sure to activate your virtualenv before using or upgrading the tool later:

.. code-block:: bash

    $ . env/bin/activate

To later upgrade it:

.. code-block:: bash

    $ pip install --upgrade proxmox-deploy


How to use
----------

After installing, simply use:

.. code-block:: bash

    $ proxmox-deploy --proxmox-host <hostname> --cloud-images-dir <images directory>

And answer the interactive questions.

Tested cloud images
-------------------

I have tested ``proxmox-deploy`` with the following *cloud images*:

+---------------+---------------+--------------------------------------------------+
| Distribution  | Version       | Status                                           |
+===============+===============+==================================================+
| Ubuntu        | `14.04`_      | The *-amd64-disk1.img* images work.              |
|               | `15.10`_      |                                                  |
|               | `16.04`_      |                                                  |
+---------------+---------------+--------------------------------------------------+
| Fedora Server | `23`_         | The *qcow2* image works.                         |
+---------------+---------------+--------------------------------------------------+
| openSUSE      | `13.2`_       | The *-OpenStack-Guest.x86_64.qcow2* image works, |
|               |               | provided the VM has at least 512 MB RAM. The     |
|               |               | minimal disk size is 10 GB. However, the first   |
|               |               | NIC is called ``eth1``, so make sure to select   |
|               |               | ``eth1`` to configure. There is no *suse*  user, |
|               |               | login as *root*.                                 |
+---------------+---------------+--------------------------------------------------+
| CentOS        | `6`_          | The CentOS 6 image fails to boot, hanging at     |
|               |               | "Booting from hard disk".                        |
|               |               |                                                  |
|               | `7`_          | The CentOS 7 *-GenericCloud.qcow2.xz* image      |
|               |               | works. The minimal disk size will be 8G.         |
+---------------+---------------+--------------------------------------------------+
| Debian        | `8`_          | Neither the qcow2 nor the raw image works. The   |
|               |               | first boot results in a kernel panic and         |
|               |               | subsequent boots won't run ``cloud-init``,       |
|               |               | rendering the VM unreachable.                    |
+---------------+---------------+--------------------------------------------------+
| FreeBSD       | `10.1 cloud`_ | Does not work, `cloudbase-init-bsd`_ has no      |
|               |               | support for the NoCloud datasource.              |
|               |               |                                                  |
|               | `10.1 vm`_    | The official VM images boot at least, but        |
|               |               | cloud-init is not available. It will boot with   |
|               |               | with DHCP and a default user/password.           |
+---------------+---------------+--------------------------------------------------+

All distributions provide a default user with the name of the distro (*ubuntu*,
*fedora*, *centos*, *debian*, *freebsd*), except openSUSE which only has a
*root* user.

Dependencies
------------
* Proxmox VE 4.1
* Python 2.7
* `proxmoxer`_ as Proxmox API client
* `openssh-wrapper`_ for communicating with the Proxmox API and
  executing commands.
* `Jinja2`_ for generating the ``user-data`` and ``meta-data`` files.
* `configobj`_ for reading configuration files.
* `pytz`_ for timezone names.
* ``genisoimage`` (Linux) or ``mkisofs`` (FreeBSD) command.

Do note that we need to access the Proxmox server via SSH, to perform the
various tasks. We also use the `pvesh` and `pvesm` commands over SSH to
interface with the Proxmox API and datastores respectively. ``proxmox-deploy``
will not ask for passwords to login, so a proper SSH agent and SSH key access
must be configured before hand.

Changelog
---------

+---------+--------------------------------------------------------------------+
|   0.3   | * Support for volumes on nfs and lvm-thin data stores.             |
|         | * Always enable serial console on new VMs. This fixes deploying    |
|         |   Ubuntu 16.04 cloud images.                                       |
+---------+--------------------------------------------------------------------+
|   0.2   | * Support for cloud-init Chef handoff (no autorun yet).            |
|         | * Improve EnumQuestion output by listing and sorting options.      |
|         | * Add option for automatically starting VMs after deployment.      |
|         | * Choose defaults for node and storage selection.                  |
|         | * Support FreeBSD `mkisofs` command.                               |
+---------+--------------------------------------------------------------------+
|   0.1   | * Initial release                                                  |
+---------+--------------------------------------------------------------------+

License
-------
``proxmox-deploy`` is licensed under the GPLv3 license.

.. _NoCloud: http://cloudinit.readthedocs.org/en/latest/topics/datasources.html#no-cloud
.. _14.04: https://cloud-images.ubuntu.com/trusty/current/
.. _15.10: https://cloud-images.ubuntu.com/wily/current/
.. _16.04: https://cloud-images.ubuntu.com/xenial/current/
.. _23: https://getfedora.org/cloud/download/
.. _13.2: http://download.opensuse.org/repositories/Cloud:/Images:/openSUSE_13.2/images/
.. _6: http://cloud.centos.org/centos/6/images/
.. _7: http://cloud.centos.org/centos/7/images/
.. _8: http://cdimage.debian.org/cdimage/openstack/8.2.0/
.. _10.1 cloud: https://blog.nekoconeko.nl/blog/2015/06/04/creating-an-openstack-freebsd-image.html
.. _10.1 vm: https://www.freebsd.org/where.html
.. _cloudbase-init-bsd: https://pellaeon.github.io/bsd-cloudinit/
.. _proxmoxer: https://pypi.python.org/pypi/proxmoxer
.. _openssh-wrapper: https://pypi.python.org/pypi/openssh-wrapper
.. _Jinja2: https://pypi.python.org/pypi/Jinja2
.. _configobj: https://pypi.python.org/pypi/configobj
.. _pytz: https://pypi.python.org/pypi/pytz
