"""Authenticated, bounded local archives and isolated restore drills.

No live activation, outgoing work, browser profiles or private-chat access.
"""
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sqlite3
import struct
import tempfile
import time
import uuid
import zipfile

from cryptography.fernet import Fernet, InvalidToken

CHUNK = 1024 * 1024
MAX_TOTAL = 2 * 1024 * 1024 * 1024
MAX_FILES = 10000
MAX_MANIFEST = 8 * 1024 * 1024
SCOPE = 'Normal assistant SQLite database and its referenced report files; excludes private chat, credentials outside the database, browser sessions and model files.'


class RecoveryError(ValueError):
    pass


def cipher(key):
    try:
        if not key:
            raise ValueError()
        return Fernet(key.encode() if isinstance(key, str) else key)
    except (ValueError, TypeError):
        raise RecoveryError('A valid credential encryption key is required for recovery archives.') from None


def safe_name(value):
    if not isinstance(value, str) or not value or len(value) > 1024:
        raise RecoveryError('Invalid archive path.')
    path = PurePosixPath(value)
    if path.is_absolute() or '\\' in value or any(
        part in {'', '.', '..'} or part.rstrip(' .') != part
        or any(ord(c) < 32 or c in ':<>"|?*' for c in part)
        or part.split('.')[0].upper() in {'CON','PRN','AUX','NUL',*[f'COM{i}' for i in range(1,10)],*[f'LPT{i}' for i in range(1,10)]}
        for part in value.split('/')
    ):
        raise RecoveryError('Invalid archive path.')
    return path


def inspect_database(path):
    with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=10)) as connection:
        if connection.execute('PRAGMA integrity_check').fetchone() != ('ok',):
            raise RecoveryError('Snapshot database integrity check failed.')
        if connection.execute('PRAGMA foreign_key_check').fetchone():
            raise RecoveryError('Snapshot database has broken foreign keys.')
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if 'django_migrations' not in tables or 'assistant_report' not in tables:
            raise RecoveryError('This is not a supported Derek database.')
        reports = set()
        for row in connection.execute('SELECT docx, pdf FROM assistant_report'):
            reports.update(value for value in row if value)
        return {'reports': sorted(reports), 'tables': len(tables),
                'migrations': connection.execute('SELECT COUNT(*) FROM django_migrations').fetchone()[0]}


def snapshot_database(source, target):
    if not source.is_file():
        raise RecoveryError('The configured database does not exist.')
    deadline = time.monotonic() + 120
    def progress(*_):
        if time.monotonic() > deadline:
            raise RecoveryError('Database snapshot timed out; retry after current writes complete.')
    with closing(sqlite3.connect(source.resolve().as_uri() + '?mode=ro', uri=True, timeout=10)) as original:
        with closing(sqlite3.connect(target)) as snapshot:
            original.backup(snapshot, pages=128, progress=progress, sleep=0.02)
    return inspect_database(target.resolve())


def create_archive(database, media_root, destination, key):
    crypt = cipher(key)
    destination, media_root = Path(destination), Path(media_root).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    ident = 'derek-' + datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-') + uuid.uuid4().hex[:8]
    final = destination / (ident + '.derekbackup')
    with tempfile.TemporaryDirectory(prefix='recovery-', dir=destination) as temporary:
        temporary = Path(temporary)
        db = temporary / 'database.sqlite3'
        inspection = snapshot_database(Path(database), db)
        files = [('database.sqlite3', db)]
        for name in inspection['reports']:
            relative = safe_name(name)
            source = media_root.joinpath(*relative.parts)
            if source.resolve() != source or not source.is_file() or not source.is_relative_to(media_root):
                raise RecoveryError('A referenced report is missing or outside local media storage; archive was not published.')
            files.append(('media/' + name, source))
        if len(files) > MAX_FILES:
            raise RecoveryError('Archive file limit exceeded.')
        manifest = {'format': 1, 'id': ident, 'created_at': datetime.now(timezone.utc).isoformat(), 'scope': SCOPE,
                    'database': {k:v for k,v in inspection.items() if k != 'reports'}, 'files': []}
        total = 0
        staging = temporary / 'archive.tmp'
        with zipfile.ZipFile(staging, 'w', compression=zipfile.ZIP_STORED) as archive:
            for index, (name, source) in enumerate(files):
                digest, size, chunks = hashlib.sha256(), 0, []
                before = source.stat()
                with source.open('rb') as stream:
                    while body := stream.read(CHUNK):
                        total += len(body)
                        if total > MAX_TOTAL:
                            raise RecoveryError('Archive size limit exceeded.')
                        chunk_name = f'data/{index}/{len(chunks)}'
                        archive.writestr(chunk_name, crypt.encrypt(body))
                        digest.update(body); size += len(body); chunks.append(chunk_name)
                after = source.stat()
                if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                    raise RecoveryError('A report changed during backup; retry with a fresh snapshot.')
                manifest['files'].append({'path': name, 'bytes': size, 'sha256': digest.hexdigest(), 'chunks': chunks})
            encoded = json.dumps(manifest).encode()
            if len(encoded) > MAX_MANIFEST:
                raise RecoveryError('Archive metadata limit exceeded.')
            archive.writestr('manifest.fernet', crypt.encrypt(encoded))
        with staging.open('r+b') as stream:
            os.fsync(stream.fileno())
        os.replace(staging, final)
    return final, {'id': ident, 'created_at': manifest['created_at'], 'encrypted': True,
                   'bytes': final.stat().st_size, 'files': len(files), 'scope': SCOPE,
                   'format': 1, 'database_checked': True}


def check_zip_directory(path):
    """Bound ZIP metadata before zipfile constructs its in-memory member list."""
    size = Path(path).stat().st_size
    if size > MAX_TOTAL * 2 + MAX_MANIFEST * 2:
        raise RecoveryError('Archive size limit exceeded.')
    with open(path, 'rb') as stream:
        stream.seek(max(0, size - 65557))
        tail = stream.read(65557)
        index = tail.rfind(b'PK\x05\x06')
        if index < 0 or index + 22 > len(tail):
            raise RecoveryError('Invalid ZIP directory.')
        _, disk, directory_disk, disk_entries, entries, directory_size, directory_offset, comment = struct.unpack('<4s4H2LH', tail[index:index+22])
        if index + 22 + comment != len(tail) or disk or directory_disk or disk_entries != entries:
            raise RecoveryError('Unsupported ZIP directory.')
        absolute_end = size - len(tail) + index
        if absolute_end >= 20:
            stream.seek(absolute_end - 20)
            locator = stream.read(20)
            if locator[:4] == b'PK\x06\x07':
                _, zip_disk, offset, disks = struct.unpack('<4sLQL', locator)
                if zip_disk or disks != 1 or offset > absolute_end - 76:
                    raise RecoveryError('Unsupported ZIP64 directory.')
                stream.seek(offset)
                record = stream.read(56)
                if len(record) != 56 or record[:4] != b'PK\x06\x06':
                    raise RecoveryError('Invalid ZIP64 directory.')
                _, length, _, _, disk, directory_disk, disk_entries, entries, directory_size, directory_offset = struct.unpack('<4sQ2H2L4Q', record)
                if length != 44 or disk or directory_disk or disk_entries != entries:
                    raise RecoveryError('Unsupported ZIP64 directory.')
        if (entries > MAX_TOTAL // CHUNK + MAX_FILES + 1 or directory_size > 16 * 1024 * 1024
                or directory_offset + directory_size > absolute_end):
            raise RecoveryError('ZIP directory limits exceeded.')


def restore_to(archive_path, destination, key):
    """Export into a NEW directory only. Never activates the restored database."""
    crypt = cipher(key)
    check_zip_directory(archive_path)
    destination = Path(destination)
    if destination.exists() or destination.is_symlink():
        raise RecoveryError('Restore destination must not already exist.')
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination = destination.parent.resolve() / destination.name
    created = False
    try:
        with zipfile.ZipFile(archive_path) as archive:
            infos = archive.infolist()
            names = {i.filename for i in infos}
            if len(names) != len(infos) or len(infos) > MAX_TOTAL // CHUNK + MAX_FILES + 1:
                raise RecoveryError('Invalid archive members.')
            for entry in infos:
                limit = MAX_MANIFEST * 2 if entry.filename == 'manifest.fernet' else CHUNK * 2
                if entry.compress_type != zipfile.ZIP_STORED or entry.file_size > limit:
                    raise RecoveryError('Unsupported or oversized archive member.')
            decoded = crypt.decrypt(archive.read('manifest.fernet'))
            if len(decoded) > MAX_MANIFEST:
                raise RecoveryError('Archive metadata limit exceeded.')
            manifest = json.loads(decoded)
            if manifest.get('format') != 1 or not isinstance(manifest.get('files'), list) or not 1 <= len(manifest['files']) <= MAX_FILES:
                raise RecoveryError('Unsupported recovery manifest.')
            expected, paths, total = {'manifest.fernet'}, set(), 0
            for index, item in enumerate(manifest['files']):
                relative = safe_name(item['path'])
                path_key = str(relative).casefold()
                if path_key in paths or (str(relative) != 'database.sqlite3' and not str(relative).startswith('media/')):
                    raise RecoveryError('Invalid or duplicate restored file.')
                paths.add(path_key)
                if type(item['bytes']) is not int or item['bytes'] < 0 or not isinstance(item['chunks'], list):
                    raise RecoveryError('Invalid recovery file size.')
                total += item['bytes']
                if total > MAX_TOTAL:
                    raise RecoveryError('Invalid recovery chunk manifest.')
                chunks = [f'data/{index}/{i}' for i in range((item['bytes'] + CHUNK - 1)//CHUNK)]
                if total > MAX_TOTAL or item['chunks'] != chunks:
                    raise RecoveryError('Invalid recovery chunk manifest.')
                expected.update(chunks)
            if 'database.sqlite3' not in paths or names != expected:
                raise RecoveryError('Archive has missing or unexpected files.')
            destination.mkdir(mode=0o700); created = True
            for item in manifest['files']:
                target = destination.joinpath(*safe_name(item['path']).parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                digest, written = hashlib.sha256(), 0
                with target.open('xb') as output:
                    for name in item['chunks']:
                        body = crypt.decrypt(archive.read(name))
                        if len(body) > CHUNK:
                            raise RecoveryError('Oversized decrypted chunk.')
                        digest.update(body); written += len(body); output.write(body)
                if written != item['bytes'] or digest.hexdigest() != item['sha256']:
                    raise RecoveryError('Recovery file checksum mismatch.')
            inspection = inspect_database(destination / 'database.sqlite3')
            wanted = {'database.sqlite3', *('media/' + name for name in inspection['reports'])}
            if wanted != {i['path'] for i in manifest['files']}:
                raise RecoveryError('Recovered report inventory differs from the database snapshot.')
            return {'verified': True, 'files': len(manifest['files']), 'bytes': total,
                    'tables': inspection['tables'], 'migrations': inspection['migrations'], 'scope': SCOPE}
    except Exception as exc:
        if created:
            # Only the new directory created by this call can be removed.
            shutil.rmtree(destination)
        if isinstance(exc, RecoveryError):
            raise
        if isinstance(exc, (InvalidToken, ValueError, KeyError, TypeError, sqlite3.Error, zipfile.BadZipFile)):
            raise RecoveryError('Archive is invalid, corrupted, or encrypted with another key.') from None
        raise


def verify_archive(archive_path, key, scratch_parent=None):
    with tempfile.TemporaryDirectory(prefix='derek-verify-', dir=scratch_parent) as folder:
        return restore_to(archive_path, Path(folder) / 'restored', key)
