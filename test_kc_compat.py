import pytest
import sys
import os
import importlib.util
from unittest.mock import patch, mock_open, MagicMock
from urllib.error import HTTPError, URLError

spec = importlib.util.spec_from_file_location("kc_compat", "kc-compat.py")
kc_compat = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kc_compat)


class TestGetKernelHash:
    @patch('builtins.open', new_callable=mock_open, read_data=b'Linux version 5.4.0-test')
    def test_get_kernel_hash_success(self, mock_file):
        result = kc_compat.get_kernel_hash()
        assert isinstance(result, str)
        assert len(result) == 40  # SHA1 hex digest length
        mock_file.assert_called_once_with('/proc/version', 'rb')

    @patch('builtins.open', side_effect=IOError("File not found"))
    def test_get_kernel_hash_file_error(self, mock_file):
        with pytest.raises(IOError):
            kc_compat.get_kernel_hash()


class TestContainerDetection:
    @patch('os.path.exists')
    def test_inside_vz_container_true(self, mock_exists):
        mock_exists.side_effect = lambda path: {
            '/proc/vz/veinfo': True,
            '/proc/vz/version': False
        }[path]
        assert kc_compat.inside_vz_container() == True

    @patch('os.path.exists')
    def test_inside_vz_container_false_no_veinfo(self, mock_exists):
        mock_exists.side_effect = lambda path: {
            '/proc/vz/veinfo': False,
            '/proc/vz/version': False
        }[path]
        assert kc_compat.inside_vz_container() == False

    @patch('os.path.exists')
    def test_inside_vz_container_false_has_version(self, mock_exists):
        mock_exists.side_effect = lambda path: {
            '/proc/vz/veinfo': True,
            '/proc/vz/version': True
        }[path]
        assert kc_compat.inside_vz_container() == False

    @patch('builtins.open', new_callable=mock_open, read_data='/lxc/container-name\n')
    def test_inside_lxc_container_true(self, mock_file):
        assert kc_compat.inside_lxc_container() == True

    @patch('builtins.open', new_callable=mock_open, read_data='/system.slice/docker.service\n')
    def test_inside_lxc_container_false(self, mock_file):
        assert kc_compat.inside_lxc_container() == False


class TestGetDistroInfo:
    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data='ID=centos\nVERSION_ID="7"\n')
    def test_get_distro_info_success(self, mock_file, mock_exists):
        name, version = kc_compat.get_distro_info()
        assert name == 'centos'
        assert version == '7'

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data='ID="ubuntu"\nVERSION_ID=18.04\n')
    def test_get_distro_info_different_quotes(self, mock_file, mock_exists):
        name, version = kc_compat.get_distro_info()
        assert name == 'ubuntu'
        assert version == '18.04'

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data="ID='fedora'\nVERSION_ID='34'\n")
    def test_get_distro_info_single_quotes(self, mock_file, mock_exists):
        name, version = kc_compat.get_distro_info()
        assert name == 'fedora'
        assert version == '34'

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data='ID=rhel\nNAME="Red Hat Enterprise Linux"\n')
    def test_get_distro_info_missing_version(self, mock_file, mock_exists):
        name, version = kc_compat.get_distro_info()
        assert name == 'rhel'
        assert version is None

    @patch('os.path.exists', return_value=False)
    def test_get_distro_info_no_file(self, mock_exists):
        name, version = kc_compat.get_distro_info()
        assert name is None
        assert version is None

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', side_effect=IOError("Permission denied"))
    def test_get_distro_info_read_error(self, mock_file, mock_exists):
        name, version = kc_compat.get_distro_info()
        assert name is None
        assert version is None


class TestIsDistroSupported:
    def test_is_distro_supported_placeholder(self):
        # Current implementation always returns False
        assert kc_compat.is_distro_supported('centos', '7') == False
        assert kc_compat.is_distro_supported('ubuntu', '18.04') == False


class TestIsCompat:
    @patch.object(kc_compat, 'get_kernel_hash', return_value='abcdef123456')
    @patch.object(kc_compat, 'urlopen')
    def test_is_compat_success(self, mock_urlopen, mock_hash):
        mock_urlopen.return_value = MagicMock()
        assert kc_compat.is_compat() == True
        mock_urlopen.assert_called_once_with('http://patches.kernelcare.com/abcdef123456/version')

    @patch.object(kc_compat, 'get_kernel_hash', return_value='abcdef123456')
    @patch.object(kc_compat, 'urlopen')
    def test_is_compat_404_error(self, mock_urlopen, mock_hash):
        mock_urlopen.side_effect = HTTPError(None, 404, 'Not Found', None, None)
        assert kc_compat.is_compat() == False

    @patch.object(kc_compat, 'get_kernel_hash', return_value='abcdef123456')
    @patch.object(kc_compat, 'urlopen')
    def test_is_compat_500_error_raises(self, mock_urlopen, mock_hash):
        mock_urlopen.side_effect = HTTPError(None, 500, 'Server Error', None, None)
        with pytest.raises(HTTPError):
            kc_compat.is_compat()

    @patch.object(kc_compat, 'get_kernel_hash', return_value='abcdef123456')
    @patch.object(kc_compat, 'urlopen')
    def test_is_compat_url_error_raises(self, mock_urlopen, mock_hash):
        mock_urlopen.side_effect = URLError('Connection refused')
        with pytest.raises(URLError):
            kc_compat.is_compat()


class TestMyprint:
    @patch('builtins.print')
    def test_myprint_not_silent(self, mock_print):
        kc_compat.myprint(False, "test message")
        mock_print.assert_called_once_with("test message")

    @patch('builtins.print')
    def test_myprint_silent(self, mock_print):
        kc_compat.myprint(True, "test message")
        mock_print.assert_not_called()


class TestMain:
    @patch('sys.argv', ['kc-compat.py'])
    @patch.object(kc_compat, 'inside_vz_container', return_value=True)
    @patch('builtins.print')
    def test_main_vz_container(self, mock_print, mock_vz):
        result = kc_compat.main()
        assert result == 2
        mock_print.assert_called_once_with("UNSUPPORTED; INSIDE CONTAINER")

    @patch('sys.argv', ['kc-compat.py'])
    @patch.object(kc_compat, 'inside_vz_container', return_value=False)
    @patch.object(kc_compat, 'inside_lxc_container', return_value=True)
    @patch('builtins.print')
    def test_main_lxc_container(self, mock_print, mock_lxc, mock_vz):
        result = kc_compat.main()
        assert result == 2
        mock_print.assert_called_once_with("UNSUPPORTED; INSIDE CONTAINER")

    @patch('sys.argv', ['kc-compat.py'])
    @patch.object(kc_compat, 'inside_vz_container', return_value=False)
    @patch.object(kc_compat, 'inside_lxc_container', return_value=False)
    @patch.object(kc_compat, 'is_compat', return_value=True)
    @patch('builtins.print')
    def test_main_compatible(self, mock_print, mock_compat, mock_lxc, mock_vz):
        result = kc_compat.main()
        assert result == 0
        mock_print.assert_called_once_with("COMPATIBLE")

    @patch('sys.argv', ['kc-compat.py'])
    @patch.object(kc_compat, 'inside_vz_container', return_value=False)
    @patch.object(kc_compat, 'inside_lxc_container', return_value=False)
    @patch.object(kc_compat, 'is_compat', return_value=False)
    @patch.object(kc_compat, 'get_distro_info', return_value=('centos', '7'))
    @patch.object(kc_compat, 'is_distro_supported', return_value=True)
    @patch('builtins.print')
    def test_main_unsupported_but_distro_supported(self, mock_print, mock_distro_supported, 
                                                  mock_distro_info, mock_compat, mock_lxc, mock_vz):
        result = kc_compat.main()
        assert result == 1
        mock_print.assert_called_once_with("Please contact CloudLinux Inc. support by email at support@cloudlinux.com or by request form at https://www.cloudlinux.com/index.php/support")

    @patch('sys.argv', ['kc-compat.py'])
    @patch.object(kc_compat, 'inside_vz_container', return_value=False)
    @patch.object(kc_compat, 'inside_lxc_container', return_value=False)
    @patch.object(kc_compat, 'is_compat', return_value=False)
    @patch.object(kc_compat, 'get_distro_info', return_value=('unknown', '1'))
    @patch.object(kc_compat, 'is_distro_supported', return_value=False)
    @patch('builtins.print')
    def test_main_unsupported_distro_not_supported(self, mock_print, mock_distro_supported,
                                                  mock_distro_info, mock_compat, mock_lxc, mock_vz):
        result = kc_compat.main()
        assert result == 1
        mock_print.assert_called_once_with("UNSUPPORTED")

    @patch('sys.argv', ['kc-compat.py', '--silent'])
    @patch.object(kc_compat, 'inside_vz_container', return_value=False)
    @patch.object(kc_compat, 'inside_lxc_container', return_value=False)
    @patch.object(kc_compat, 'is_compat', return_value=True)
    @patch('builtins.print')
    def test_main_silent_mode(self, mock_print, mock_compat, mock_lxc, mock_vz):
        result = kc_compat.main()
        assert result == 0
        mock_print.assert_not_called()

    @patch('sys.argv', ['kc-compat.py'])
    @patch.object(kc_compat, 'inside_vz_container', return_value=False)
    @patch.object(kc_compat, 'inside_lxc_container', return_value=False)
    @patch.object(kc_compat, 'is_compat', side_effect=HTTPError(None, 500, 'Server Error', None, None))
    @patch('builtins.print')
    def test_main_http_error(self, mock_print, mock_compat, mock_lxc, mock_vz):
        result = kc_compat.main()
        assert result == 3
        mock_print.assert_called_once_with("CONNECTION ERROR; HTTP 500")

    @patch('sys.argv', ['kc-compat.py'])
    @patch.object(kc_compat, 'inside_vz_container', return_value=False)
    @patch.object(kc_compat, 'inside_lxc_container', return_value=False)
    @patch.object(kc_compat, 'is_compat', side_effect=URLError('Connection refused'))
    @patch('builtins.print')
    def test_main_url_error(self, mock_print, mock_compat, mock_lxc, mock_vz):
        result = kc_compat.main()
        assert result == 3
        mock_print.assert_called_once_with("CONNECTION ERROR; Connection refused")

    @patch('sys.argv', ['kc-compat.py'])
    @patch.object(kc_compat, 'inside_vz_container', return_value=False)
    @patch.object(kc_compat, 'inside_lxc_container', return_value=False)
    @patch.object(kc_compat, 'is_compat', side_effect=IOError('Disk error'))
    @patch('builtins.print')
    def test_main_system_error(self, mock_print, mock_compat, mock_lxc, mock_vz):
        result = kc_compat.main()
        assert result == 4
        mock_print.assert_called_once_with("SYSTEM ERROR; Disk error")

    @patch('sys.argv', ['kc-compat.py'])
    @patch.object(kc_compat, 'inside_vz_container', return_value=False)
    @patch.object(kc_compat, 'inside_lxc_container', return_value=False)
    @patch.object(kc_compat, 'is_compat', side_effect=ValueError('Unexpected error'))
    @patch('builtins.print')
    def test_main_unexpected_error(self, mock_print, mock_compat, mock_lxc, mock_vz):
        result = kc_compat.main()
        assert result == 5
        mock_print.assert_called_once_with("UNEXPECTED ERROR; Unexpected error") 