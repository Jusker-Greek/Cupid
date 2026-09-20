"""Download and verify the pinned official CUPID release inside Slurm."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import time
import socket
from urllib.parse import urlsplit
from concurrent.futures import ThreadPoolExecutor

import requests

REPO = 'hbb1/Cupid'
REVISION = '1191de37cc33b60273a631d4e07fbbe7cee798c1'


def verify(path, item):
    if not path.is_file() or path.stat().st_size != item['size']:
        return False
    sha = hashlib.sha256() if 'lfs' in item else hashlib.sha1()
    if 'lfs' not in item:
        sha.update(f"blob {item['size']}\0".encode())
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b''):
            sha.update(block)
    expected = item['lfs']['sha256'] if 'lfs' in item else item['blobId']
    return sha.hexdigest() == expected


def main():
    if not os.environ.get('SLURM_JOB_ID'):
        raise RuntimeError('Use a Slurm allocation')
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--wait-local-proxy', type=int, default=0,
                        help='Wait for a session-scoped SSH proxy on the allocated node')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    if args.wait_local_proxy:
        proxy = urlsplit(os.environ.get('https_proxy', ''))
        if proxy.hostname != '127.0.0.1' or not proxy.port:
            raise RuntimeError('Proxy wait requires explicit loopback proxy')
        print(f'WAITING_LOCAL_PROXY host={os.uname().nodename} port={proxy.port}', flush=True)
        deadline = time.monotonic() + args.wait_local_proxy
        while True:
            try:
                with socket.create_connection((proxy.hostname, proxy.port), timeout=2):
                    break
            except OSError:
                if time.monotonic() >= deadline:
                    raise RuntimeError('Session proxy did not become available') from None
                time.sleep(2)
    response = None
    use_environment_proxy = True
    for mode in ('configured_proxy', 'direct'):
        probe = requests.Session()
        probe.trust_env = mode == 'configured_proxy'
        try:
            candidate = probe.get(f'https://huggingface.co/api/models/{REPO}/revision/{REVISION}',
                                  params={'blobs': 'true'}, timeout=(20, 40))
            if candidate.status_code != 200:
                print(f'API_FAILURE mode={mode} HTTP={candidate.status_code}', flush=True)
                continue
            response = candidate
            use_environment_proxy = probe.trust_env
            print(f'DOWNLOAD_TRANSPORT={mode}', flush=True)
            break
        except requests.RequestException as error:
            print(f'API_FAILURE mode={mode} error={type(error).__name__}', flush=True)
        finally:
            probe.close()
    if response is None:
        raise RuntimeError('Official API unavailable through configured proxy and direct TLS')
    manifest = response.json()
    if manifest['sha'] != REVISION:
        raise RuntimeError('Release identity changed')
    items = manifest['siblings']
    total = sum(item['size'] for item in items)
    if total > 8_000_000_000:
        raise RuntimeError('Official release exceeds expected size envelope')
    for item in items:
        path = PurePosixPath(item['rfilename'])
        if path.is_absolute() or '..' in path.parts:
            raise RuntimeError('Invalid model filename')
    receipt = {'schema': 'cupid_official_download/v1', 'repo': REPO, 'revision': REVISION,
               'job': os.environ['SLURM_JOB_ID'], 'host': os.uname().nodename,
               'total_bytes': total, 'files': items, 'status': 'DOWNLOADING'}
    (args.output / 'download_receipt.json').write_text(json.dumps(receipt, indent=2))
    print(f'OFFICIAL_RELEASE={REVISION} FILES={len(items)} BYTES={total}', flush=True)

    def download(item):
        session = requests.Session()
        session.trust_env = use_environment_proxy
        name = item['rfilename']
        target = args.output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        partial = target.with_name(target.name + '.partial')
        for attempt in range(1, 4):
            try:
                # Unique query avoids stale expired CDN redirects; release remains pinned.
                url = f'https://huggingface.co/{REPO}/resolve/{REVISION}/{name}'
                with session.get(url, params={'download': 'true', 'attempt': str(time.time_ns())},
                                  stream=True, timeout=(30, 120)) as result:
                    if result.status_code != 200:
                        raise RuntimeError(f'HTTP_{result.status_code}')
                    written = 0
                    last_progress = 0
                    with partial.open('wb') as handle:
                        for block in result.iter_content(8 * 1024 * 1024):
                            handle.write(block)
                            written += len(block)
                            if written > item['size']:
                                raise RuntimeError('SIZE_OVERFLOW')
                            if written - last_progress >= 256 * 1024 * 1024:
                                print(f'DOWNLOAD {name} {written}/{item["size"]}', flush=True)
                                last_progress = written
                if not verify(partial, item):
                    raise RuntimeError('SIZE_OR_HASH_MISMATCH')
                partial.rename(target)
                print(f'VERIFIED {name} {item["size"]}', flush=True)
                return
            except (requests.RequestException, RuntimeError) as error:
                # Never print signed redirect URLs or credential-bearing request objects.
                kind = str(error) if isinstance(error, RuntimeError) else type(error).__name__
                print(f'DOWNLOAD_FAILURE file={name} attempt={attempt} reason={kind}', flush=True)
                if attempt == 3:
                    raise RuntimeError(f'Download failed for {name}: {kind}') from None
                time.sleep(2 * attempt)

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(download, items))
        pipeline = json.loads((args.output / 'pipeline.json').read_text())
        for model in pipeline['args']['models'].values():
            for suffix in ('.json', '.safetensors'):
                if not (args.output / (model + suffix)).is_file():
                    raise RuntimeError('Pipeline dependency absent')
        receipt.update(status='VERIFIED', image_cond_model=pipeline['args']['image_cond_model'])
        (args.output / 'download_receipt.json').write_text(json.dumps(receipt, indent=2))
        print('CUPID_OFFICIAL_DOWNLOAD=VERIFIED', flush=True)
    except Exception:
        receipt['status'] = 'FAILED'
        (args.output / 'download_receipt.json').write_text(json.dumps(receipt, indent=2))
        raise


if __name__ == '__main__':
    main()
