import hashlib
import json
import sqlite3
import struct
import zipfile

from cryptography.fernet import Fernet
import pytest
from desktop import recovery as r


@pytest.fixture
def installation(tmp_path):
    database = tmp_path / 'live.sqlite3'
    media = tmp_path / 'media'
    (media / 'reports').mkdir(parents=True)
    (media / 'reports/result.pdf').write_bytes(b'private report contents')
    with sqlite3.connect(database) as db:
        db.executescript('CREATE TABLE django_migrations (id INTEGER); CREATE TABLE assistant_report (docx TEXT, pdf TEXT);')
        db.execute('INSERT INTO assistant_report VALUES (?,?)', ('', 'reports/result.pdf'))
    return database, media, tmp_path / 'backups', Fernet.generate_key()


def test_archive_roundtrip_does_not_modify_source(installation, tmp_path):
    database, media, folder, key = installation
    before = hashlib.sha256(database.read_bytes()).hexdigest()
    archive, info = r.create_archive(*installation)
    assert info['encrypted'] and info['files'] == 2
    assert b'private report contents' not in archive.read_bytes()
    result = r.verify_archive(archive, key, tmp_path)
    assert result['verified'] and result['files'] == 2
    assert hashlib.sha256(database.read_bytes()).hexdigest() == before
    target = tmp_path / 'restored'
    r.restore_to(archive, target, key)
    assert (target / 'media/reports/result.pdf').read_bytes() == (media / 'reports/result.pdf').read_bytes()
    assert not list(folder.glob('recovery-*'))


def test_existing_destination_is_never_touched(installation, tmp_path):
    archive, _ = r.create_archive(*installation)
    existing = tmp_path / 'important'; existing.mkdir()
    (existing / 'keep').write_text('keep')
    with pytest.raises(r.RecoveryError, match='already exist'):
        r.restore_to(archive, existing, installation[-1])
    assert (existing / 'keep').read_text() == 'keep'


def test_wrong_key_and_truncated_archive(installation, tmp_path):
    archive, _ = r.create_archive(*installation)
    for key in (Fernet.generate_key(), b'not-a-key'):
        with pytest.raises(r.RecoveryError):
            r.restore_to(archive, tmp_path / 'wrong', key)
        assert not (tmp_path / 'wrong').exists()
    archive.write_bytes(archive.read_bytes()[:100])
    with pytest.raises(r.RecoveryError):
        r.verify_archive(archive, installation[-1])


@pytest.mark.parametrize('name', ['../outside', '/absolute', 'C:/outside', 'media/CON.txt', 'media/a\\b', 'media/x.'])
def test_traversal_and_windows_paths_rejected(installation, tmp_path, name):
    archive, _ = r.create_archive(*installation)
    crypt = Fernet(installation[-1])
    with zipfile.ZipFile(archive) as z:
        parts = {i.filename:z.read(i) for i in z.infolist()}
    manifest = json.loads(crypt.decrypt(parts['manifest.fernet']))
    manifest['files'][1]['path'] = name
    parts['manifest.fernet'] = crypt.encrypt(json.dumps(manifest).encode())
    bad = tmp_path / 'malformed.zip'
    with zipfile.ZipFile(bad,'w') as z:
        for n, value in parts.items(): z.writestr(n,value)
    with pytest.raises(r.RecoveryError):
        r.restore_to(bad, tmp_path / 'out', installation[-1])
    assert not (tmp_path / 'out').exists()


def test_missing_report_prevents_publish(installation):
    (installation[1] / 'reports/result.pdf').unlink()
    with pytest.raises(r.RecoveryError, match='missing'):
        r.create_archive(*installation)
    assert not list(installation[2].glob('*.derekbackup'))
    assert not list(installation[2].glob('recovery-*'))


def test_changed_chunk_rejected_and_partial_export_removed(installation, tmp_path):
    archive, _ = r.create_archive(*installation)
    with zipfile.ZipFile(archive) as z:
        parts = {i.filename:z.read(i) for i in z.infolist()}
    parts['data/1/0'] = Fernet(installation[-1]).encrypt(b'different report')
    bad = tmp_path / 'changed.zip'
    with zipfile.ZipFile(bad,'w') as z:
        for name, value in parts.items(): z.writestr(name,value)
    with pytest.raises(r.RecoveryError, match='checksum'):
        r.restore_to(bad, tmp_path / 'out', installation[-1])
    assert not (tmp_path / 'out').exists()


def test_multichunk_file_and_size_bound(installation, monkeypatch):
    report = installation[1] / 'reports/result.pdf'
    report.write_bytes(b'a' * (r.CHUNK + 17))
    archive, _ = r.create_archive(*installation)
    assert r.verify_archive(archive, installation[-1])['verified']
    monkeypatch.setattr(r, 'MAX_TOTAL', 10)
    with pytest.raises(r.RecoveryError, match='size limit'):
        r.create_archive(*installation)


def test_snapshot_includes_wal_commits(installation):
    database, _, _, key = installation
    with sqlite3.connect(database) as db:
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('INSERT INTO django_migrations VALUES (1)'); db.commit()
        archive, _ = r.create_archive(*installation)
        assert r.verify_archive(archive,key)['migrations'] == 1


def test_enormous_manifest_size_rejected_before_allocation(installation, tmp_path):
    archive, _ = r.create_archive(*installation)
    crypt = Fernet(installation[-1])
    with zipfile.ZipFile(archive) as z:
        parts = {i.filename:z.read(i) for i in z.infolist()}
    manifest = json.loads(crypt.decrypt(parts['manifest.fernet']))
    manifest['files'][0]['bytes'] = 10**30
    parts['manifest.fernet'] = crypt.encrypt(json.dumps(manifest).encode())
    bad = tmp_path / 'oversized.zip'
    with zipfile.ZipFile(bad,'w') as z:
        for name, value in parts.items(): z.writestr(name,value)
    with pytest.raises(r.RecoveryError, match='chunk manifest'):
        r.restore_to(bad, tmp_path / 'out', installation[-1])
    assert not (tmp_path / 'out').exists()


def test_zip_directory_limits_checked_before_member_parsing(installation, tmp_path, monkeypatch):
    archive, _ = r.create_archive(*installation)
    data = bytearray(archive.read_bytes())
    end = data.rfind(b'PK\x05\x06')
    struct.pack_into('<HH', data, end + 8, 65000, 65000)
    bad = tmp_path / 'metadata-bomb.zip'; bad.write_bytes(data)
    monkeypatch.setattr(r.zipfile, 'ZipFile', lambda *_: pytest.fail('Member parsing must not occur'))
    with pytest.raises(r.RecoveryError, match='directory limits'):
        r.verify_archive(bad, installation[-1])
