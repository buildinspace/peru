import imp
from os.path import abspath, join, dirname
import unittest

import peru

CURL_SHARED_PATH = abspath(
    join(dirname(peru.__file__), 'resources', 'plugins', 'curl',
         'curl_plugin_shared.py'))
curl_plugin_shared = imp.load_source('_curl_plugin_shared', CURL_SHARED_PATH)


class CurlPluginTest(unittest.TestCase):
    def test_get_request_filename(self):
        class MockRequest:
            _info = {}

            def info(self):
                return self._info

        request = MockRequest()
        request.url = 'http://www.example.com/'
        self.assertEqual('index.html',
                         curl_plugin_shared.get_request_filename(request))
        request.url = 'http://www.example.com/foo'
        self.assertEqual('foo',
                         curl_plugin_shared.get_request_filename(request))
        request._info = {'Content-Disposition':
                         'attachment; filename=bar'}
        self.assertEqual('bar',
                         curl_plugin_shared.get_request_filename(request))
