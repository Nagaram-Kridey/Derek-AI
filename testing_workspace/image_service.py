"""Pinned loopback-only AUTOMATIC1111 lifecycle and fail-closed benchmark gate."""
import argparse
import hashlib
import json
import os
import shutil
import socket
import subprocess
import threading
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / '.trial-workspace'
INSTALL = ROOT / '.tools' / 'a1111-v1.10.1'
PIN = '82a973c04367123ae98bd9abdf80d9eda9b910e2'
TAG = 'v1.10.1'
BASE = 'http://127.0.0.1:7860'
PYTHON = INSTALL / 'venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')

def read(name):
    try: return json.loads((DATA / name).read_text())
    except (OSError, ValueError): return {}

def write(name, value):
    DATA.mkdir(exist_ok=True)
    (DATA / name).write_text(json.dumps(value, indent=2))

def sha256(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1024*1024), b''): result.update(block)
    return result.hexdigest()

def validated_gate():
    config, model, evidence = read('config.json'), read('image-checkpoint.json'), read('image-benchmark.json')
    reason = 'Image generation awaits a licensed checkpoint and local benchmark.'
    try:
        stat = Path(model['path']).stat()
        rows = evidence.get('results', [])
        passed = (evidence.get('passed') is True and evidence.get('pin') == PIN
            and evidence.get('checkpoint_sha256') == model['sha256']
            and model.get('pin') == PIN and model.get('size') == stat.st_size and model.get('mtime_ns') == stat.st_mtime_ns
            and evidence.get('api_verified') is True and len(rows) == 3
            and all(0 < row['seconds'] <= 180 and row['chat_ok'] is True for row in rows))
        if passed:
            reason = 'Local feasibility passed; tester access is disabled until explicitly enabled.'
            if config.get('images_enable_testers') is True:
                return {'enabled': True, 'reason': '', 'checkpoint': model['sha256']}
        elif evidence:
            reason = 'Local image benchmark has not passed or checkpoint changed.'
    except (KeyError, OSError, TypeError): pass
    return {'enabled': False, 'reason': reason, 'checkpoint': model.get('sha256', '')}

def own_process():
    import psutil
    record = read('image-process.json')
    try:
        process = psutil.Process(record['pid'])
        args = process.cmdline()
        if (abs(process.create_time()-record['created']) < .01
            and str(INSTALL / 'launch.py') in args and '--port' in args and '7860' in args): return process
    except (KeyError, psutil.Error): pass
    return None

def api(path, payload=None, timeout=10):
    body = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(BASE + path, data=body, headers={'Content-Type':'application/json'})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req, timeout=timeout) as response:
        data = response.read(24*1024*1024+1)
        if len(data)>24*1024*1024: raise ValueError('Response exceeds image limit')
        return json.loads(data)

def clean_env():
    keep = {'PATH','SYSTEMROOT','WINDIR','USERPROFILE','LOCALAPPDATA','APPDATA','TEMP','TMP','COMSPEC','PATHEXT'}
    env = {k:v for k,v in os.environ.items() if k.upper() in keep}
    env.update(GRADIO_ANALYTICS_ENABLED='False', TORCH_COMMAND='pip install torch==2.1.2 torchvision==0.16.2 --index-url https://download.pytorch.org/whl/cpu')
    return env

def install():
    if not INSTALL.exists():
        subprocess.run(['git','clone','--depth','1','--branch',TAG,'https://github.com/AUTOMATIC1111/stable-diffusion-webui.git',str(INSTALL)],check=True)
    commit = subprocess.check_output(['git','-C',str(INSTALL),'rev-parse','HEAD'],text=True).strip()
    if commit != PIN: raise ValueError('Installation revision differs from pinned release; no update performed')
    if not PYTHON.exists():
        uv = shutil.which('uv')
        if not uv: raise ValueError('Install uv or provide isolated Python3.10 before installing')
        subprocess.run([uv,'python','install','3.10'],check=True)
        subprocess.run([uv,'venv','--python','3.10','--seed',str(INSTALL/'venv')],check=True)
    subprocess.run([str(PYTHON),'-m','pip','install','setuptools==69.5.1','wheel==0.45.1'],check=True)
    subprocess.run([str(PYTHON),'-m','pip','install','--no-build-isolation','https://github.com/openai/CLIP/archive/d50d76daa670286dd6cacf3bcd80b5e4823fc8e1.zip'],check=True)
    log = DATA / 'image-install.log'
    DATA.mkdir(exist_ok=True)
    with log.open('a') as stream:
        subprocess.run([str(PYTHON),str(INSTALL/'launch.py'),'--exit','--skip-torch-cuda-test','--disable-all-extensions','--no-download-sd-model'],cwd=INSTALL,env=clean_env(),stdout=stream,stderr=stream,check=True,timeout=1800)
    write('image-install.json',{'pin':PIN,'tag':TAG,'installed':True})
    print('Pinned isolated WebUI dependencies installed.')

def start():
    if own_process(): print('Image service already running'); return
    commit = subprocess.check_output(['git','-C',str(INSTALL),'rev-parse','HEAD'],text=True).strip()
    if commit != PIN: raise ValueError('Image service revision does not match approved pin')
    model = read('image-checkpoint.json')
    if not model or sha256(model['path']) != model['sha256']: raise ValueError('Register a licensed checkpoint first; hash must match')
    if not read('image-install.json').get('installed'): raise ValueError('Run install successfully before start')
    with socket.socket() as sock:
        try: sock.bind(('127.0.0.1',7860))
        except OSError: raise ValueError('Port7860 occupied; unrelated service left untouched') from None
    flags = ['--api','--nowebui','--server-name','127.0.0.1','--port','7860','--use-cpu','all','--precision','full','--no-half','--skip-torch-cuda-test','--disable-all-extensions','--no-download-sd-model','--ckpt',model['path']]
    (DATA/'logs').mkdir(exist_ok=True)
    with (DATA/'logs/image-service.log').open('a') as log:
        process = subprocess.Popen([str(PYTHON),str(INSTALL/'launch.py'),*flags],cwd=INSTALL,env=clean_env(),stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    import psutil
    write('image-process.json',{'pid':process.pid,'created':psutil.Process(process.pid).create_time()})
    print('Image service starting on loopback7860; inspect status before benchmarking.')

def stop():
    process = own_process()
    if process:
        import psutil
        children = process.children(recursive=True)
        for child in children: child.terminate()
        process.terminate()
        _, alive = psutil.wait_procs([process,*children],timeout=10)
        for child in alive: child.kill()
    print('Owned image service stopped; no other runtime touched.')

def benchmark(chat_url):
    model = read('image-checkpoint.json')
    evidence = {'pin':PIN,'at':time.time(),'checkpoint_sha256':model.get('sha256'),'passed':False,'api_verified':False,'results':[]}
    write('image-benchmark.json', evidence)
    try:
        if not model or sha256(model['path']) != model['sha256']: raise ValueError('Checkpoint missing or changed')
        schema = api('/openapi.json')
        if '/sdapi/v1/txt2img' not in schema.get('paths',{}): raise ValueError('Installed API schema lacks txt2img')
        available = api('/sdapi/v1/sd-models')
        if not any(row.get('sha256') == model['sha256'] for row in available): raise ValueError('Registered checkpoint is not present in installed API model list')
        evidence['api_verified'] = True
        # An actual normal chat request must run concurrently; URL is a local
        # owner-operated probe endpoint, never supplied by a remote client.
        if chat_url != 'http://127.0.0.1:8010': raise ValueError('Chat probe must use isolated trial8010')
        import getpass
        token = getpass.getpass('Trial admin API token for local chat responsiveness probe (hidden): ')
        if not token: raise ValueError('A trial admin API token is required for the concurrent chat probe')
        for index in range(3):
            result = {'chat_ok':False}
            def probe(result=result):
                time.sleep(2)
                started = time.monotonic()
                try:
                    request = urllib.request.Request(chat_url+'/v1/turn',data=json.dumps({'text':'What is 2 plus 3? Reply with just the number.','request_id':'image-benchmark-'+str(time.time_ns())}).encode(),headers={'Authorization':'Token '+token,'Content-Type':'application/json'})
                    with urllib.request.urlopen(request,timeout=60) as response: outcome=json.load(response)
                    command = outcome.get('command_id')
                    while command and time.monotonic()-started < 60:
                        query=urllib.request.Request(chat_url+'/v1/commands/'+command+'/',headers={'Authorization':'Token '+token})
                        with urllib.request.urlopen(query,timeout=10) as response: outcome=json.load(response)
                        if outcome.get('status') not in ['queued','running']: break
                        time.sleep(1)
                    reply=outcome.get('reply_text') or outcome.get('response',{}).get('reply_text','')
                    result['chat_ok']=outcome.get('status')=='completed' and str(reply).strip()=='5'
                except Exception:  # noqa: BLE001 -- sanitized probe status only, never credentials
                    result['chat_ok'] = False
                result['chat_seconds']=round(time.monotonic()-started,3)
            thread=threading.Thread(target=probe,daemon=True); thread.start()
            started=time.monotonic()
            output=api('/sdapi/v1/txt2img',{'prompt':'a red ceramic cup on a wooden table, natural light','width':512,'height':512,'steps':15,'batch_size':1,'n_iter':1,'seed':index,'sampler_name':'Euler','save_images':False,'send_images':True,'override_settings':{'sd_model_checkpoint':model['sha256']}},timeout=180)
            result['seconds']=round(time.monotonic()-started,3)
            thread.join(timeout=65)
            import base64
            import io

            from PIL import Image
            images = output.get('images') or []
            if len(images) != 1: raise ValueError('Expected one generated image')
            raw = base64.b64decode(images[0], validate=True)
            with Image.open(io.BytesIO(raw)) as image:
                if image.format != 'PNG' or image.size != (512,512): raise ValueError('Expected PNG512x512 output')
                image.verify()
            if result['seconds']>180 or not result['chat_ok']: raise ValueError('Generation or concurrent chat failed benchmark')
            evidence['results'].append(result); write('image-benchmark.json',evidence)
        evidence['passed']=True
    except Exception as error:  # noqa: BLE001 -- fail-closed benchmark and stop on any uncertain outcome
        evidence['failure']=type(error).__name__
        # Unknown generation outcome is stopped; never replay benchmark calls.
        stop()
    write('image-benchmark.json',evidence)
    print(json.dumps(evidence))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    for command in ['install','start','stop','status','enable-testers','disable-testers']: sub.add_parser(command)
    register=sub.add_parser('register-checkpoint'); register.add_argument('path'); register.add_argument('--source',required=True); register.add_argument('--license',required=True)
    test=sub.add_parser('benchmark');test.add_argument('--chat-url',default='http://127.0.0.1:8010')
    args=parser.parse_args()
    if args.command in {'enable-testers','disable-testers'}:
        config=read('config.json')
        config['images_enable_testers']=args.command=='enable-testers'
        write('config.json',config)
        gate=validated_gate()
        if args.command=='enable-testers' and not gate['enabled']:
            config['images_enable_testers']=False;write('config.json',config)
            raise ValueError(gate['reason'])
        print('Tester image setting updated; restart trial to apply.')
    elif args.command=='install': install()
    elif args.command=='start': start()
    elif args.command=='stop': stop()
    elif args.command=='status': print(json.dumps({'running':own_process() is not None, **validated_gate()}))
    elif args.command=='benchmark': benchmark(args.chat_url)
    elif args.command=='register-checkpoint':
        path=Path(args.path).resolve()
        if path.suffix.lower()!='.safetensors' or not path.is_file(): raise ValueError('Choose an existing licensed SD1.5 SafeTensors checkpoint')
        if not args.source.startswith('https://') or not args.license.strip(): raise ValueError('Record an HTTPS source and nonempty reviewed license')
        stat=path.stat()
        write('image-checkpoint.json',{'path':str(path),'sha256':sha256(path),'source':args.source,'license':args.license,'pin':PIN,'size':stat.st_size,'mtime_ns':stat.st_mtime_ns})
        write('image-benchmark.json',{'passed':False,'failure':'checkpoint_changed'})
        print('Checkpoint registered; generation remains disabled pending benchmark.')

if __name__=='__main__': main()
