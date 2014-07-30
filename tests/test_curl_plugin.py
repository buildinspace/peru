import unittest

from peru.resources.plugins.curl.curl_plugin_shared import get_request_filename


class CurlPluginTest(unittest.TestCase):
    def test_get_request_filename(self):
        class MockRequest:
            _info = {}

            def info(self):
                return self._info

        request = MockRequest()
        request.url = 'http://www.example.com/'
        self.assertEqual('index.html', get_request_filename(request))
        request.url = 'http://www.example.com/foo'
        self.assertEqual('foo', get_request_filename(request))
        request._info = {'Content-Disposition':
                         'attachment; filename=bar'}
        self.assertEqual('bar', get_request_filename(request))
