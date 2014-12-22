#! /usr/bin/env python3

import hashlib
import os
import pathlib
import re
import sys
import tarfile
from urllib.parse import urlsplit
import urllib.request
import zipfile


def get_request_filename(request):
    '''Figure out the filename for an HTTP download.'''
    # Check to see if a filename is specified in the HTTP headers.
    if 'Content-Disposition' in request.info():
        disposition = request.info()['Content-Disposition']
        pieces = re.split('\s*;\s*', disposition)
        for piece in pieces:
            if piece.startswith('filename='):
                filename = piece[len('filename='):]
                # Strip exactly one " from each end.
                if filename.startswith('"'):
                    filename = filename[1:]
                if filename.endswith('"'):
                    filename = filename[:-1]
                # Interpret backslashed quotes.
                filename = filename.replace('\\"', '"')
                return filename
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


def download_file(request, output_file, stdout=sys.stdout):
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
        print('downloaded{} {}{}'.format(percentage, kb_downloaded, total_kb),
              file=stdout)
    return digest.hexdigest()


def plugin_fetch(url, sha1):
    unpack = os.environ['PERU_MODULE_UNPACK']
    dest = os.environ['PERU_FETCH_DEST']
    if unpack:
        # Download to the tmp dir for later unpacking.
        download_dir = os.environ['PERU_PLUGIN_TMP']
    else:
        # Download directly to the destination dir.
        download_dir = dest

    with urllib.request.urlopen(url) as request:
        filename = os.environ['PERU_MODULE_FILENAME']
        if not filename:
            filename = get_request_filename(request)
        full_filepath = os.path.join(download_dir, filename)
        with open(full_filepath, 'wb') as output_file:
            digest = download_file(request, output_file)

    if sha1 and digest != sha1:
        print('Bad checksum!\n     url: {}\nexpected: {}\n  actual: {}'
              .format(url, sha1, digest), file=sys.stderr)
        sys.exit(1)

    if unpack == 'tar':
        with tarfile.open(full_filepath) as t:
            validate_filenames(info.path for info in t.getmembers())
            t.extractall(dest)
    elif unpack == 'zip':
        with zipfile.ZipFile(full_filepath) as z:
            # The zipfile library automatically strips .. and leading slashes.
            z.extractall(dest)
    elif unpack:
        print('Unknown value for "unpack":', unpack, file=sys.stderr)
        sys.exit(1)


def validate_filenames(names):
    for name in names:
        path = pathlib.PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts:
            print('Illegal path in archive:', name, file=sys.stderr)
            sys.exit(1)


def plugin_reup(url, sha1):
    reup_output = os.environ['PERU_REUP_OUTPUT']
    with urllib.request.urlopen(url) as request:
        digest = download_file(request, None)
    with open(reup_output, 'w') as output_file:
        print('sha1:', digest, file=output_file)


def main():
    url = os.environ['PERU_MODULE_URL']
    sha1 = os.environ['PERU_MODULE_SHA1']
    command = os.environ['PERU_PLUGIN_COMMAND']
    if command == 'fetch':
        plugin_fetch(url, sha1)
    elif command == 'reup':
        plugin_reup(url, sha1)
    else:
        raise RuntimeError('unknown command: ' + repr(command))


if __name__ == '__main__':
    main()
