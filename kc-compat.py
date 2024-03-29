from __future__ import print_function
import struct
import sys
import os

try:
    from urllib.request import urlopen
except ImportError:
    from urllib2 import urlopen

__author__ = 'Igor Seletskiy'
__copyright__ = "Copyright (c) Cloud Linux GmbH & Cloud Linux Software, Inc"
__credits__ = 'Igor Seletskiy'
__license__ = 'Apache License v2.0'
__maintainer__ = 'Igor Seletskiy'
__email__ = 'i@kernelcare.com'
__status__ = 'Production'
__version__ = '1.0'


def get_kernel_hash():
    try:
        # noinspection PyCompatibility
        from hashlib import sha1
    except ImportError:
        from sha import sha as sha1
    f = open('/proc/version', 'rb')
    try:
        return sha1(f.read()).hexdigest()
    finally:
        f.close()


def inside_vz_container():
    """
    determines if we are inside Virtuozzo container
    :return: True if inside container, false otherwise
    """
    return os.path.exists('/proc/vz/veinfo') and not os.path.exists('/proc/vz/version')


def inside_lxc_container():
    return '/lxc/' in open('/proc/1/cgroup').read()


def is_compat():
    url = 'http://patches.kernelcare.com/' + get_kernel_hash() + '/version'
    try:
        urlopen(url)
        return True
    except Exception:
        return False


def myprint(silent, message):
    if not silent:
        print(message)


def main():
    """
    if --silent or -q argument provided, don't print anything, just use exit code
    otherwise print results (COMPATIBLE or UNSUPPORTED)
    else exit with 0 if COMPATIBLE, 1 or more otherwise
    """
    silent = len(sys.argv) > 1 and (sys.argv[1] == '--silent' or sys.argv[1] == '-q')
    if inside_vz_container() or inside_lxc_container():
        myprint(silent, "UNSUPPORTED; INSIDE CONTAINER")
        return 2
    if is_compat():
        myprint(silent, "COMPATIBLE")
        return 0
    else:
        myprint(silent, "UNSUPPORTED")
        return 1


if __name__ == "__main__":
    exit(main())
