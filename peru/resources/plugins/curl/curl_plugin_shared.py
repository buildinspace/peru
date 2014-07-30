import os
import re
from urllib.parse import urlsplit


def get_request_filename(request):
    '''Figure out the filename for an HTTP download.'''
    # Check to see if a filename is specified in the HTTP headers.
    if 'Content-Disposition' in request.info():
        disposition = request.info()['Content-Disposition']
        pieces = re.split('\s*;\s*', disposition)
        for piece in pieces:
            if piece.startswith('filename='):
                return piece[len('filename='):]
    # If no filename was specified, pick a reasonable default.
    return os.path.basename(urlsplit(request.url).path) or 'index.html'
