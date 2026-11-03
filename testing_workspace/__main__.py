"""Manual isolated workspace commands; no personal runtime imports."""
import argparse
import getpass
import json
import os
from pathlib import Path
import secrets
import shutil
import sqlite3
import subprocess
import sys
import time
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / '.trial-workspace'
CONFIG = DATA / 'config.json'


def load():
    if not CONFIG.exists():
        raise ValueError('Run python -m testing_workspace init first.')
    return json.loads(CONFIG.read_text(encoding='utf-8'))


def save(config):
    DATA.mkdir(exist_ok=True)
    CONFIG.write_text(json.dumps(config, indent=2), encoding='utf-8')
    if os.name != 'nt':
        CONFIG.chmod(0o600)


def environment():
    env = dict(os.environ)
    env.update(DJANGO_SETTINGS_MODULE='config.trial_settings', PYTHONPATH=os.pathsep.join([str(ROOT / 'backend'), str(ROOT)]))
    return env


def django_setup():
    os.environ.update(environment())
    sys.path.insert(0, str(ROOT / 'backend'))
    import django
    django.setup()


def owned_process():
    import psutil
    record = DATA / 'process.json'
    if not record.exists():
        return None
    meta = json.loads(record.read_text())
    try:
        process = psutil.Process(meta['pid'])
        if abs(process.create_time() - meta['created']) < .01 and 'testing_workspace' in ' '.join(process.cmdline()) and 'serve' in process.cmdline():
            return process
    except psutil.Error:
        pass
    return None


def backup():
    source = DATA / 'db.sqlite3'
    if not source.exists():
        return None
    folder = DATA / 'backups' / (time.strftime('%Y%m%d-%H%M%S') + '-' + str(time.time_ns() % 1000000000))
    folder.mkdir(parents=True, exist_ok=False)
    with sqlite3.connect(source) as original, sqlite3.connect(folder / 'db.sqlite3') as target:
        original.backup(target)
        if target.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('Backup database integrity check failed; inspect trial logs before retrying.')
    if (DATA / 'media').exists():
        shutil.copytree(DATA / 'media', folder / 'media')
    return folder


def run_manage(*args):
    subprocess.run([sys.executable, str(ROOT / 'backend/manage.py'), *args], env=environment(), cwd=ROOT, check=True)


def serve(publish):
    import threading
    import signal
    import logging
    from waitress import serve as waitress
    django_setup()
    from django.db import close_old_connections
    from assistant.models import Command, Report
    from assistant.tasks import process_command, research_report
    from config.wsgi import application
    config = load()
    stop = threading.Event()
    (DATA / 'stop').unlink(missing_ok=True)
    children = []
    def finish(*_):
        stop.set()
    signal.signal(signal.SIGTERM, finish)
    signal.signal(signal.SIGINT, finish)
    def jobs():
        last_backup = time.monotonic()
        while not stop.wait(.8):
            if any(child.poll() is not None for child in children):
                logging.error('Trial tunnel exited; stopping workspace. Check ngrok account limits and configuration before restarting.')
                stop.set()
            if (DATA / 'stop').exists() or stop.is_set():
                stop.set()
                break
            close_old_connections()
            try:
                row = Command.objects.filter(status='queued').order_by('created_at').first()
                if row:
                    process_command.run(str(row.pk))

                if time.monotonic() - last_backup > 86400:
                    backup()
                    last_backup = time.monotonic()
            except Exception:
                logging.warning('Trial worker poll failed; saved commands remain available.')
        report_thread.join()
        image_thread.join()
        # Only own web process is terminated after active command returns.
        for child in children:
            child.terminate()
        os._exit(0)
    def report_jobs():
        while not stop.wait(1):
            close_old_connections()
            try:
                report = Report.objects.filter(status='queued').order_by('created_at').first()
                if report:
                    research_report.run(str(report.pk))
            except Exception:
                logging.warning('Trial report worker failed; inspect report status before retrying.')
        close_old_connections()
    report_thread = threading.Thread(target=report_jobs, daemon=True)
    report_thread.start()
    def image_jobs():
        from assistant.image_worker import run_once, recover_interrupted
        recover_interrupted()
        while not stop.wait(1):
            close_old_connections()
            try:
                run_once()
            except Exception:
                logging.warning('Image worker unavailable; inspect saved image status before retrying.')
            finally:
                close_old_connections()
    image_thread = threading.Thread(target=image_jobs, daemon=True)
    image_thread.start()
    threading.Thread(target=jobs, daemon=True).start()
    def telegram_poll():
        from assistant.trial_telegram import configured, poll_once
        while not stop.wait(3):
            if not configured():
                continue
            close_old_connections()
            try:
                poll_once()
            except Exception:
                logging.warning('Trial Telegram poll unavailable; check dedicated bot configuration.')
            finally:
                close_old_connections()
    threading.Thread(target=telegram_poll, daemon=True).start()
    if publish:
        path = shutil.which('ngrok')
        ngrok_config = DATA / 'ngrok.yml'
        if not path or not ngrok_config.exists():
            raise ValueError('Install ngrok and run configure before start --publish.')
        children.append(subprocess.Popen([path, 'http', '--inspect=false', '--config', str(ngrok_config), '--url', 'https://' + config['public_host'], 'http://127.0.0.1:8010'], stdout=sys.stdout, stderr=sys.stderr))
    try:
        waitress(application, host='127.0.0.1', port=8010, threads=6, ident='Derek testing', expose_tracebacks=False,
                 trusted_proxy='127.0.0.1', trusted_proxy_headers={'x-forwarded-proto'}, clear_untrusted_proxy_headers=True)
    finally:
        stop.set()
        for child in children:
            child.terminate()
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()


def main():
    parser = argparse.ArgumentParser(description='Isolated Derek tester workspace on port 8010. Personal Derek on 8000 is never stopped.')
    commands = parser.add_subparsers(dest='command')
    commands.add_parser('init', help='Generate fresh trial keys/directories; never copy personal data.')
    commands.add_parser('telegram-configure', help='Configure a dedicated trial Telegram bot without changing other settings.')
    commands.add_parser('llm-configure', help='Configure your separate text LLM endpoint; image and speech providers stay separate.')
    commands.add_parser('configure', help='Interactively enter invitations, OAuth client, separate router key and ngrok domain/token.')
    owner = commands.add_parser('admin', help='Create the separate trial admin interactively.'); owner.add_argument('username')
    start = commands.add_parser('start', help='Back up, migrate and start manually.'); start.add_argument('--publish', action='store_true', help='Also publish configured ngrok HTTPS domain.')
    commands.add_parser('stop', help='Gracefully stop only the owned trial runtime.')
    commands.add_parser('status', help='Print runtime state as JSON; never prints credentials.')
    commands.add_parser('backup', help='Create independent SQLite/media snapshot.')
    restore = commands.add_parser('restore', help='Restore a trial snapshot while stopped; preserves pre-restore snapshot.'); restore.add_argument('snapshot')
    internal = commands.add_parser('serve', help=argparse.SUPPRESS); internal.add_argument('--publish', action='store_true')
    args = parser.parse_args()
    try:
        if args.command == 'init':
            if CONFIG.exists():
                print('Already initialized. Use configure to change settings.'); return
            from cryptography.fernet import Fernet
            save({'secret_key': secrets.token_urlsafe(64), 'encryption_key': Fernet.generate_key().decode(), 'open_signup': True, 'invited_emails': [], 'public_host': 'peddling-stardust-untapped.ngrok-free.dev'})
            for folder in ['media', 'logs', 'runtime', 'backups', 'static']:
                (DATA / folder).mkdir(exist_ok=True)
            print('Initialized isolated workspace. Next: python -m testing_workspace configure')
        elif args.command == 'telegram-configure':
            if owned_process(): raise ValueError('Stop trial before configuring Telegram.')
            config = load()
            token = getpass.getpass('Dedicated TEST bot token from BotFather (hidden; blank disables): ').strip()
            username = input('Dedicated TEST bot username, without @: ').strip().lstrip('@')
            import re
            if token and (not re.fullmatch(r'[0-9]+:[A-Za-z0-9_-]+', token) or not re.fullmatch(r'[A-Za-z0-9_]{5,32}', username)):
                raise ValueError('Enter a valid dedicated bot token and username.')
            config['telegram_bot_token'] = token
            config['telegram_bot_username'] = username if token else ''
            save(config)
            print('Trial Telegram configuration saved. Restart trial to apply.')
        elif args.command == 'llm-configure':
            if owned_process(): raise ValueError('Stop the trial before configuring its text endpoint.')
            config = load()
            choice = input('Text provider [custom/freellmapi]: ').strip().lower()
            if choice not in {'custom', 'freellmapi'}: raise ValueError('Choose custom or freellmapi.')
            if choice == 'custom':
                base = input('OpenAI-compatible base URL ending /v1: ').strip().rstrip('/')
                parsed = urlsplit(base)
                if (not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment
                    or parsed.path.rstrip('/') != '/v1' or parsed.scheme not in {'https','http'}
                    or (parsed.scheme == 'http' and parsed.hostname not in {'127.0.0.1','localhost','::1'})):
                    raise ValueError('Use HTTPS /v1 or loopback HTTP /v1, without URL credentials.')
                model = input('Model name: ').strip()
                if not model or len(model)>160 or any(c.isspace() for c in model): raise ValueError('Enter a valid model name.')
                config.update(custom_llm_base_url=base, custom_llm_model=model,
                    custom_llm_api_key=getpass.getpass('API key (hidden): '),
                    custom_llm_supports_tools=input('Supports OpenAI tool calls? [y/N]: ').strip().lower()=='y',
                    custom_llm_supports_json_schema=input('Supports JSON schema responses? [y/N]: ').strip().lower()=='y')
                if any(c.isspace() for c in config['custom_llm_api_key']):
                    raise ValueError('API key cannot contain whitespace.')
                if parsed.hostname not in {'127.0.0.1', 'localhost', '::1'} and not config['custom_llm_api_key']:
                    raise ValueError('A remote model endpoint requires an API key.')
            config['text_provider'] = choice
            save(config)
            print('Text provider saved. Restart the trial to apply. Image and speech settings unchanged.')
        elif args.command == 'configure':
            if owned_process(): raise ValueError('Stop the trial before configuring: python -m testing_workspace stop')
            config = load()
            config['open_signup'] = input('Open Google signup, first 10 accounts? [Y/n]: ').strip().lower() != 'n'
            emails = {x.strip().casefold() for x in input('Invited Google emails, comma separated (empty denies all testers): ').split(',') if x.strip()}
            if len(emails) > 10 or any('@' not in x for x in emails): raise ValueError('Enter up to 10 valid email addresses; rerun configure.')
            config['invited_emails'] = sorted(emails)
            config['google_client_id'] = input('Separate Google Web client ID: ').strip()
            config['router_key'] = getpass.getpass('Separate local router credential (hidden): ')
            host = input('Assigned ngrok HTTPS domain (hostname only, blank for local setup): ').strip()
            if host and (urlsplit('https://' + host).hostname != host or not host.endswith(('.ngrok-free.app', '.ngrok-free.dev', '.ngrok.app'))):
                raise ValueError('Enter the exact assigned ngrok hostname, without paths or https://.')
            config['public_host'] = host
            token = getpass.getpass('ngrok authtoken (hidden; blank to leave unchanged): ')
            if token:
                if any(c.isspace() for c in token): raise ValueError('ngrok token cannot contain whitespace; rerun configure.')
                (DATA / 'ngrok.yml').write_text('version: "3"\nagent:\n  authtoken: ' + json.dumps(token) + '\n', encoding='utf-8')
            save(config)
            print('Saved. Next: python -m testing_workspace admin YOUR_USERNAME')
        elif args.command == 'admin':
            load(); backup(); run_manage('migrate', '--noinput'); run_manage('create_owner', args.username)
        elif args.command == 'start':
            config = load()
            if owned_process():
                meta = json.loads((DATA / 'process.json').read_text())
                if args.publish and not meta.get('publish'):
                    raise ValueError('Local trial already running. Stop it, wait for status running:false, then start --publish.')
                print('Test workspace already running.'); return
            if args.publish:
                required = ['public_host', 'google_client_id']
                if config.get('text_provider', 'freellmapi') == 'freellmapi' or (config.get('images_enabled') and config.get('image_provider') == 'freellmapi'):
                    required.append('router_key')
                if config.get('text_provider') == 'custom':
                    required.extend(['custom_llm_base_url', 'custom_llm_model'])
                if not all(config.get(k) for k in required):
                    raise ValueError('Publishing requires OAuth, domain and configured provider credentials. Run configure or llm-configure first.')
            if args.publish and not config.get('open_signup') and not config.get('invited_emails'): raise ValueError('Invitation-only mode requires invited emails.')
            (DATA / 'static').mkdir(exist_ok=True)
            if not (ROOT / 'web_dashboard/dist/index.html').exists(): raise ValueError('Build frontend first: npm --prefix web_dashboard run build')
            shutil.copytree(ROOT / 'web_dashboard/dist', DATA / 'dashboard', dirs_exist_ok=True)
            import socket
            with socket.socket() as sock:
                try: sock.bind(('127.0.0.1', 8010))
                except OSError: raise ValueError('Port 8010 is occupied. Stop its owning application; personal Derek is untouched.') from None
            backup(); run_manage('migrate', '--noinput')
            if args.publish:
                django_setup()
                from django.contrib.auth import get_user_model
                if not get_user_model().objects.filter(is_active=True, is_staff=True).exists():
                    raise ValueError('Create trial admin first: python -m testing_workspace admin YOUR_USERNAME')
            log = open(DATA / 'logs/runtime.log', 'a', encoding='utf-8')
            proc = subprocess.Popen([sys.executable, '-m', 'testing_workspace', 'serve'] + (['--publish'] if args.publish else []), cwd=ROOT, env=environment(), stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            import psutil
            (DATA / 'process.json').write_text(json.dumps({'pid': proc.pid, 'created': psutil.Process(proc.pid).create_time(), 'publish': bool(args.publish)}))
            time.sleep(1)
            if proc.poll() is not None: raise ValueError('Trial failed to start. Inspect .trial-workspace/logs/runtime.log and retry.')
            print('Started trial on http://127.0.0.1:8010' + ('; tunnel requested for https://' + config['public_host'] + ' (verify public login before sharing)'  if args.publish else ' (not published).'))
        elif args.command == 'stop':
            if owned_process():
                (DATA / 'stop').touch()
                print('Trial stopping after its active request finishes. Personal Derek remains running.')
            else: print('Trial is stopped.')
        elif args.command == 'status': print(json.dumps({'running': owned_process() is not None, 'port': 8010, 'configured': CONFIG.exists()}))
        elif args.command == 'backup': print(str(backup() or 'No trial database to back up.'))
        elif args.command == 'restore':
            if owned_process(): raise ValueError('Stop trial and wait for status running:false before restore.')
            folder = Path(args.snapshot).resolve()
            if folder.parent != (DATA / 'backups').resolve() or not (folder / 'db.sqlite3').is_file(): raise ValueError('Choose a snapshot directory inside .trial-workspace/backups.')
            with sqlite3.connect(folder / 'db.sqlite3') as check:
                if check.execute('PRAGMA integrity_check').fetchone()[0] != 'ok': raise ValueError('Snapshot failed integrity check; choose another backup.')
            backup()
            for suffix in ['-wal', '-shm']:
                (DATA / ('db.sqlite3' + suffix)).unlink(missing_ok=True)
            shutil.copy2(folder / 'db.sqlite3', DATA / 'db.sqlite3')
            media = (DATA / 'media').resolve()
            if media.parent != DATA.resolve(): raise ValueError('Media path escaped trial root; inspect paths.')
            if media.exists(): shutil.rmtree(media)
            if (folder / 'media').exists(): shutil.copytree(folder / 'media', media)
            else: media.mkdir()
            print('Restored trial snapshot. Start when ready; personal data untouched.')
        elif args.command == 'serve': serve(args.publish)
        else: parser.print_help()
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        print('Error: ' + str(exc), file=sys.stderr); return 1
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
