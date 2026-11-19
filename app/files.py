"""Attachment helpers: safe file names, base64 decoding and ZIP archives (optionally with a password)."""
import base64
import binascii
import io
import os
import struct
import tempfile
import unicodedata
import zipfile

import pyminizip

from .errors import ApiError

MAX_NAME_BYTES = 255


def safe_filename(name) -> str:
    """The last path segment of `name`, without control characters; refuses empty / `.` / `..`."""
    if not isinstance(name, str):
        raise ApiError('filename is required')
    base = name.replace('\\', '/').rsplit('/', 1)[-1]
    base = ''.join(c for c in base if unicodedata.category(c)[0] != 'C').strip()
    if base in ('', '.', '..'):
        raise ApiError(f'Invalid file name: {name!r}')
    while len(base.encode('utf-8')) > MAX_NAME_BYTES:
        stem, ext = os.path.splitext(base)
        base = stem[:-1] + ext if stem else base[:-1]
    return base


def decode_base64(data, name: str) -> bytes:
    if not isinstance(data, str) or not data:
        raise ApiError(f'data of {name} is required (base64)')
    if data.startswith('data:') and ',' in data:  # data URL
        data = data.split(',', 1)[1]
    try:
        return base64.b64decode(data, validate=True)
    except (binascii.Error, ValueError):
        raise ApiError(f'data of {name} is not valid base64') from None


def unique_names(files: list) -> list:
    """`[(name, bytes)]` with duplicate names renamed `a (2).txt`."""
    seen, out = set(), []
    for name, data in files:
        candidate, n = name, 1
        stem, ext = os.path.splitext(name)
        while candidate in seen:
            n += 1
            candidate = f'{stem} ({n}){ext}'
        seen.add(candidate)
        out.append((candidate, data))
    return out


def make_zip(files: list, password: str = '') -> bytes:
    """ZIP of `[(name, bytes)]`. With a password it uses ZipCrypto (opens in Windows Explorer / macOS)."""
    files = unique_names(files)
    if not password:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
            for name, data in files:
                zf.writestr(name, data)
        return buf.getvalue()
    # pyminizip works on files: write them to a private temporary directory.
    with tempfile.TemporaryDirectory() as tmp:
        srcs = []
        for i, (name, data) in enumerate(files):
            folder = os.path.join(tmp, str(i))
            os.mkdir(folder)
            path = os.path.join(folder, name)
            with open(path, 'wb') as f:
                f.write(data)
            srcs.append(path)
        out = os.path.join(tmp, 'archive.zip')
        pyminizip.compress_multiple(srcs, [''] * len(srcs), out, password, 4)
        with open(out, 'rb') as f:
            return mark_utf8_names(f.read())


def mark_utf8_names(data: bytes) -> bytes:
    """Marks every entry name as UTF-8, as Python's zipfile writes them.

    pyminizip writes UTF-8 names without the UTF-8 flag (general purpose bit 11) and records
    MS-DOS as the creating system, so unzip tools read Japanese names with a DOS code page
    (garbled, or "Illegal byte sequence"). The flag, the creating system ("version made by")
    and the file mode are outside the encrypted data and the CRC, so they can be patched.
    """
    buf = bytearray(data)
    eocd = buf.rfind(b'PK\x05\x06')
    if eocd < 0:
        return data
    count, = struct.unpack_from('<H', buf, eocd + 10)
    pos, = struct.unpack_from('<I', buf, eocd + 16)
    for _ in range(count):
        if buf[pos:pos + 4] != b'PK\x01\x02':
            return data
        flags, = struct.unpack_from('<H', buf, pos + 8)
        struct.pack_into('<H', buf, pos + 8, flags | 0x800)
        buf[pos + 5] = 3                                            # made by: Unix
        struct.pack_into('<I', buf, pos + 38, 0o100644 << 16)       # regular file, rw-r--r--
        name_len, extra_len, comment_len = struct.unpack_from('<HHH', buf, pos + 28)
        local, = struct.unpack_from('<I', buf, pos + 42)
        if buf[local:local + 4] == b'PK\x03\x04':
            lflags, = struct.unpack_from('<H', buf, local + 6)
            struct.pack_into('<H', buf, local + 6, lflags | 0x800)
        pos += 46 + name_len + extra_len + comment_len
    return bytes(buf)
