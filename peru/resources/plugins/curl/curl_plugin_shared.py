import hashlib
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


def format_bytes(num_bytes):
    for threshold, unit in ((10**9, 'GB'), (10**6, 'MB'), (10**3, 'KB')):
        if num_bytes >= threshold:
            # Truncate floats instead of rounding.
            float_str = str(num_bytes / threshold)
            decimal_index = float_str.index('.')
            truncated_float = float_str[:decimal_index+2]
            return truncated_float + unit
    return '{}B'.format(num_bytes)


def download_file(request, output_file):
    digest = hashlib.sha1()
    file_size_str = request.info().get('Content-Length')
    file_size = int(file_size_str) if file_size_str is not None else None
    bytes_read = 0
    while True:
        buf = request.read(4096)
        if not buf:
            break
        digest.update(buf)
        if output_file:
            output_file.write(buf)
        bytes_read += len(buf)
        percentage = ''
        kb_downloaded = format_bytes(bytes_read)
        total_kb = ''
        if file_size:
            percentage = ' {}%'.format(round(100 * bytes_read / file_size))
            total_kb = '/' + format_bytes(file_size)
        print('downloaded{} {}{}'.format(percentage, kb_downloaded, total_kb))
    return digest.hexdigest()
