#! /usr/bin/env python3

import hashlib
import os
import pathlib
import re
import stat
import sys
import tarfile
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request
import peru.main
import urllib.request
import zipfile


def add_user_agent_to_request(request):
    components = [
        "peru/%s" % peru.main.get_version(),
        urllib.request.URLopener.version
    ]
    request.add_header("User-agent", " ".join(components))
    return request


def build_request(url):
    request = Request(url)
    return add_user_agent_to_request(request)


def get_request_filename(request):
    '''Figure out the filename for an HTTP download.'''
    # Check to see if a filename is specified in the HTTP headers.
    if 'Content-Disposition' in request.info():
        disposition = request.info()['Content-Disposition']
        pieces = re.split(r'\s*;\s*', disposition)
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
            truncated_float = float_str[:decimal_index + 2]
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
        print(
            'downloaded{} {}{}'.format(percentage, kb_downloaded, total_kb),
            file=stdout)
    return digest.hexdigest()


def plugin_sync(url, sha1):
    unpack = os.environ['PERU_MODULE_UNPACK']
    dest = os.environ['PERU_SYNC_DEST']
    if unpack:
        # Download to the tmp dir for later unpacking.
        download_dir = os.environ['PERU_PLUGIN_TMP']
    else:
        # Download directly to the destination dir.
        download_dir = dest

    with urllib.request.urlopen(build_request(url)) as request:
        filename = os.environ['PERU_MODULE_FILENAME']
        if not filename:
            filename = get_request_filename(request)
        full_filepath = os.path.join(download_dir, filename)
        with open(full_filepath, 'wb') as output_file:
            digest = download_file(request, output_file)

    if sha1 and digest != sha1:
        print(
            'Bad checksum!\n     url: {}\nexpected: {}\n  actual: {}'.format(
                url, sha1, digest),
            file=sys.stderr)
        sys.exit(1)

    try:
        if unpack == 'tar':
            extract_tar(full_filepath, dest)
        elif unpack == 'zip':
            extract_zip(full_filepath, dest)
        elif unpack:
            print('Unknown value for "unpack":', unpack, file=sys.stderr)
            sys.exit(1)
    except EvilArchiveError as e:
        print(e.message, file=sys.stderr)
        sys.exit(1)


def extract_tar(archive_path, dest):
    with tarfile.open(archive_path) as t:
        for info in t.getmembers():
            validate_filename(info.path)
            if info.issym():
                validate_symlink(info.path, info.linkname)
        t.extractall(dest)


def extract_zip(archive_path, dest):
    with zipfile.ZipFile(archive_path) as z:
        for name in z.namelist():
            validate_filename(name)
        z.extractall(dest)
        # Set file permissions. Tar does this by default, but with zip we need
        # to do it ourselves.
        for info in z.filelist:
            if not info.filename.endswith('/'):
                # This is how to get file permissions out of a zip archive,
                # according to http://stackoverflow.com/q/434641/823869 and
                # http://bugs.python.org/file34873/issue15795_cleaned.patch.
                mode = (info.external_attr >> 16) & 0o777
                # Don't copy the whole mode, just set the executable bit. Two
                # reasons for this. 1) This is all going to end up in a git
                # tree, which only records the executable bit anyway. 2) Zip's
                # support for Unix file modes is nonstandard, so the mode field
                # is often zero and could be garbage. Mistakenly setting a file
                # executable isn't a big deal, but e.g. removing read
                # permissions would cause an error.
                if mode & stat.S_IXUSR:
                    os.chmod(os.path.join(dest, info.filename), 0o755)


def validate_filename(name):
    path = pathlib.PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts:
        raise EvilArchiveError("Illegal path in archive: " + name)


def validate_symlink(name, target):
    # We might do this twice but that's fine.
    validate_filename(name)

    allowed_parent_parts = len(pathlib.PurePosixPath(name).parts) - 1

    target_path = pathlib.PurePosixPath(target)
    if target_path.is_absolute():
        raise EvilArchiveError("Illegal symlink target in archive: " + target)
    leading_parent_parts = 0
    for part in target_path.parts:
        if part != "..":
            break
        leading_parent_parts += 1
    if leading_parent_parts > allowed_parent_parts:
        raise EvilArchiveError("Illegal symlink target in archive: " + target)
    if ".." in target_path.parts[leading_parent_parts:]:
        raise EvilArchiveError("Illegal symlink target in archive: " + target)


class EvilArchiveError(RuntimeError):
    def __init__(self, message):
        self.message = message


def plugin_reup(url, sha1):
    reup_output = os.environ['PERU_REUP_OUTPUT']
    with urllib.request.urlopen(build_request(url)) as request:
        digest = download_file(request, None)
    with open(reup_output, 'w') as output_file:
        print('sha1:', digest, file=output_file)


def main():
    url = os.environ['PERU_MODULE_URL']
    sha1 = os.environ['PERU_MODULE_SHA1']
    command = os.environ['PERU_PLUGIN_COMMAND']
    try:
        if command == 'sync':
            plugin_sync(url, sha1)
        elif command == 'reup':
            plugin_reup(url, sha1)
        else:
            raise RuntimeError('unknown command: ' + repr(command))
    except (HTTPError, URLError) as e:
        print("Error fetching", url)
        print(e)
        return 1


if __name__ == '__main__':
    sys.exit(main())
