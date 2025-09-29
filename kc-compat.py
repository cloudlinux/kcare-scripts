from __future__ import print_function
import struct
import sys
import os

try:
    from urllib.request import urlopen
    from urllib.error import HTTPError, URLError
except ImportError:
    from urllib2 import urlopen, HTTPError, URLError

__author__ = 'Igor Seletskiy'
__copyright__ = "Copyright (c) Cloud Linux GmbH & Cloud Linux Software, Inc"
__credits__ = 'Igor Seletskiy'
__license__ = 'Apache License v2.0'
__maintainer__ = 'Igor Seletskiy'
__email__ = 'i@kernelcare.com'
__status__ = 'Production'
__version__ = '1.0'


SUPPORTED_DISTROS = {
    "almalinux", 
    "amzn",
    "centos",
    "cloudlinux",
    "debian",
    "ol",
    "raspbian",
    "rhel",
    "rocky",
    "ubuntu", 
    "proxmox",
}


def get_kernel_hash_from_data(version_data):
    try:
        # noinspection PyCompatibility
        from hashlib import sha1
    except ImportError:
        from sha import sha as sha1
    return sha1(version_data).hexdigest()


def inside_vz_container():
    """
    determines if we are inside Virtuozzo container
    :return: True if inside container, false otherwise
    """
    return os.path.exists('/proc/vz/veinfo') and not os.path.exists('/proc/vz/version')


def inside_lxc_container():
    return '/lxc/' in open('/proc/1/cgroup').read()


def get_distro_info():
    """
    Get current distribution name and version
    :return: tuple of (distro_name, distro_version) or (None, None) if detection fails
    """
    
    def parse_value(line):
        return line.split('=', 1)[1].strip().strip('"\'')
    
    os_release_path = '/etc/os-release'
    if not os.path.exists(os_release_path):
        return None, None

    try:
        distro_name = None
        distro_version = None
        with open(os_release_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line.startswith('ID='):
                    distro_name = parse_value(line)
                elif line.startswith('VERSION_ID='):
                    distro_version = parse_value(line)
        return distro_name, distro_version
    except (IOError, OSError):
        return None, None


def is_distro_supported(distro_name):
    """
    Check if the given distro name is supported
    """
    return distro_name in SUPPORTED_DISTROS


def is_compat(kernel_hash):
    url = 'http://patches.kernelcare.com/' + kernel_hash + '/version'
    try:
        urlopen(url)
        return True
    except HTTPError as e:
        if e.code == 404:
            return False
        else:
            raise
    except URLError:
        raise


def myprint(silent, message):
    if not silent:
        print(message)


def main():
    """
    if --silent or -q argument provided, don't print anything, just use exit code
    if --report provided, show system information for support
    otherwise print results (COMPATIBLE or support contact messages)
    else exit with 0 if COMPATIBLE, 1 or more otherwise
    """
    silent = len(sys.argv) > 1 and (sys.argv[1] == '--silent' or sys.argv[1] == '-q')
    report = len(sys.argv) > 1 and sys.argv[1] == '--report'

    if inside_vz_container() or inside_lxc_container():
        myprint(silent, "UNSUPPORTED; INSIDE CONTAINER")
        return 2

    try:
        with open('/proc/version', 'rb') as f:
            version_data = f.read()
    except (IOError, OSError):
        version_data = b''
    
    kernel_hash = get_kernel_hash_from_data(version_data)
    distro_name, distro_version = get_distro_info()

    if report:
        print("=== KernelCare Compatibility Report ===")
        print(f"Kernel Hash: {kernel_hash}")
        print(f"Distribution: {distro_name or 'Unknown'}")
        print(f"Version: {distro_version or 'Unknown'}")
        print(f"Kernel: {version_data.decode('utf-8', errors='replace').strip()}")
        print("=====================================")
    
    try:
        if is_compat(kernel_hash):
            myprint(silent, "COMPATIBLE")
            return 0
        else:
            # Handle 404 case - check if distro is supported
            if distro_name and is_distro_supported(distro_name):
                myprint(silent, "NEEDS REVIEW")
                myprint(silent, "We support your distribution, but we're having trouble detecting your precise kernel configuration. Please, contact CloudLinux Inc. support by email at support@cloudlinux.com or by request form at https://www.cloudlinux.com/index.php/support")
                return 1
            else:
                myprint(silent, "NEEDS REVIEW")
                myprint(silent, "Please contact CloudLinux Inc. support by email at support@cloudlinux.com or by request form at https://www.cloudlinux.com/index.php/support")
                return 1
    except HTTPError as e:
        myprint(silent, "CONNECTION ERROR; HTTP %d" % e.code)
        return 3
    except URLError as e:
        myprint(silent, "CONNECTION ERROR; %s" % str(e.reason))
        return 3
    except (IOError, OSError) as e:
        myprint(silent, "SYSTEM ERROR; %s" % str(e))
        return 4
    except Exception as e:
        myprint(silent, "UNEXPECTED ERROR; %s" % str(e))
        return 5


if __name__ == "__main__":
    exit(main())
