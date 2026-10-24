"""Encrypted local recovery archives; verification never activates restored work."""
import argparse
import json
import os
import sys
from pathlib import Path
from .state import ROOT, write_record
from .recovery import RecoveryError, create_archive, restore_to, verify_archive


def configured():
    sys.path.insert(0, str(ROOT / 'backend'))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    import django
    django.setup()
    from django.conf import settings
    return settings


def create_backup():
    settings = configured()
    database = settings.DATABASES['default']
    if database['ENGINE'] != 'django.db.backends.sqlite3':
        write_record('backup', {'status': 'not_applicable', 'reason': 'Use database-native backups for this installation.'})
        return None
    path, info = create_archive(database['NAME'], settings.MEDIA_ROOT, ROOT / '.companion/backups', settings.CREDENTIAL_ENCRYPTION_KEY)
    verification = verify_archive(path, settings.CREDENTIAL_ENCRYPTION_KEY)
    write_record('backup', {'status': 'ready', **info, 'verified': verification['verified'], 'file': path.name})
    return path


def main():
    parser = argparse.ArgumentParser(description='Derek local encrypted backup and isolated recovery checks')
    parser.add_argument('command', nargs='?', choices=['create','verify','restore-to'], default='create')
    parser.add_argument('archive', nargs='?', type=Path)
    parser.add_argument('--destination', type=Path, help='New directory for an offline restore export; never the live database.')
    args = parser.parse_args()
    try:
        if args.command == 'create':
            result = create_backup()
            print('Encrypted database/report archive saved and verified.' if result else 'Use database-native backups.')
        else:
            if not args.archive or (args.command == 'restore-to' and not args.destination):
                parser.error('Specify an archive and, for restore-to, --destination with a new directory.')
            key = configured().CREDENTIAL_ENCRYPTION_KEY
            result = (verify_archive(args.archive, key) if args.command == 'verify'
                      else restore_to(args.archive, args.destination, key))
            print(json.dumps(result))
    except Exception as exc:
        if args.command == 'create':
            write_record('backup', {'status': 'needs_attention', 'reason': str(exc) if isinstance(exc, RecoveryError)
                         else 'Recovery archive could not be completed; check storage and local configuration.',
                         'error_type': type(exc).__name__})
        raise SystemExit(str(exc) if isinstance(exc, RecoveryError) else 'Recovery operation failed; no credential values were logged.') from None


if __name__ == '__main__':
    main()
