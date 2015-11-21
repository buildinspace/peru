import hashlib
import importlib.machinery
import io
from os.path import abspath, join, dirname

import peru
import shared

curl_plugin_path = abspath(
    join(dirname(peru.__file__), 'resources', 'plugins', 'curl',
         'curl_plugin.py'))
loader = importlib.machinery.SourceFileLoader("curl_plugin", curl_plugin_path)
curl_plugin = loader.load_module()


class MockRequest:
    def __init__(self, url, info, response):
        self.url = url
        self._info = info
        self._response_buffer = io.BytesIO(response)

    def info(self):
        return self._info

    def read(self, *args):
        return self._response_buffer.read(*args)


class CurlPluginTest(shared.PeruTest):
    def test_format_bytes(self):
        self.assertEqual('0B', curl_plugin.format_bytes(0))
        self.assertEqual('999B', curl_plugin.format_bytes(999))
        self.assertEqual('1.0KB', curl_plugin.format_bytes(1000))
        self.assertEqual('999.9KB', curl_plugin.format_bytes(999999))
        self.assertEqual('1.0MB', curl_plugin.format_bytes(10**6))
        self.assertEqual('1.0GB', curl_plugin.format_bytes(10**9))
        self.assertEqual('1000.0GB', curl_plugin.format_bytes(10**12))

    def test_get_request_filename(self):
        request = MockRequest('http://www.example.com/', {}, b'junk')
        self.assertEqual('index.html',
                         curl_plugin.get_request_filename(request))
        request.url = 'http://www.example.com/foo'
        self.assertEqual('foo',
                         curl_plugin.get_request_filename(request))
        request._info = {'Content-Disposition':
                         'attachment; filename=bar'}
        self.assertEqual('bar',
                         curl_plugin.get_request_filename(request))
        # Check quoted filenames.
        request._info = {'Content-Disposition':
                         'attachment; filename="bar"'}
        self.assertEqual('bar',
                         curl_plugin.get_request_filename(request))
        # Check backslashed quotes in filenames.
        request._info = {'Content-Disposition':
                         'attachment; filename="bar\\""'}
        self.assertEqual('bar"',
                         curl_plugin.get_request_filename(request))

    def test_download_file_with_length(self):
        content = b'xy' * 4096
        request = MockRequest(
            'some url',
            {'Content-Length': len(content)},
            content)
        stdout = io.StringIO()
        output_file = io.BytesIO()
        sha1 = curl_plugin.download_file(request, output_file, stdout)
        self.assertEqual(
            'downloaded 50% 4.0KB/8.1KB\ndownloaded 100% 8.1KB/8.1KB\n',
            stdout.getvalue())
        self.assertEqual(content, output_file.getvalue())
        self.assertEqual(hashlib.sha1(content).hexdigest(), sha1)

    def test_download_file_without_length(self):
        content = b'foo'
        request = MockRequest('some url', {}, content)
        stdout = io.StringIO()
        output_file = io.BytesIO()
        sha1 = curl_plugin.download_file(request, output_file, stdout)
        self.assertEqual(
            'downloaded 3B\n',
            stdout.getvalue())
        self.assertEqual(content, output_file.getvalue())
        self.assertEqual(hashlib.sha1(content).hexdigest(), sha1)

    def test_unpack_windows_zip(self):
        '''This zip was packed on Windows, so it doesn't include any file
        permissions. This checks that our executable-flag-restoring code
        doesn't barf when the flag isn't there.'''
        test_dir = shared.create_dir()
        archive = shared.test_resources / 'from_windows.zip'
        curl_plugin.extract_zip(str(archive), test_dir)
        shared.assert_contents(test_dir, {'windows_test/test.txt': 'Notepad!'})
        txt_file = join(test_dir, 'windows_test/test.txt')
        shared.assert_not_executable(txt_file)

    def test_evil_archives(self):
        '''Even though most zip and tar utilities try to prevent absolute paths
        and paths starting with '..', it's entirely possible to construct an
        archive with either. These should always be an error.'''
        dest = shared.create_dir()
        for case in 'absolute_path', 'leading_dots':
            zip_archive = shared.test_resources / (case + '.zip')
            with self.assertRaises(curl_plugin.EvilArchiveError):
                curl_plugin.extract_zip(str(zip_archive), dest)
            tar_archive = shared.test_resources / (case + '.tar')
            with self.assertRaises(curl_plugin.EvilArchiveError):
                curl_plugin.extract_tar(str(tar_archive), dest)
