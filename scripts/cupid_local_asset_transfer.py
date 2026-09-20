"""User-authorized local asset download and Slurm-side upload verification.

This only transports public official assets; it never runs a model locally.
Existing cluster download roots are not modified.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import time

REVISION = '1191de37cc33b60273a631d4e07fbbe7cee798c1'
EXCLUDED = ('slat_dec_', 'slat_enc_', 'slat_flow_')


def verified(path, item):
    if not path.is_file() or path.stat().st_size != item['size']:
        return False
    digest = hashlib.sha256() if 'lfs' in item else hashlib.sha1()
    if 'lfs' not in item:
        digest.update(f"blob {item['size']}\0".encode())
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b''):
            digest.update(block)
    expected = item['lfs']['sha256'] if 'lfs' in item else item['blobId']
    return digest.hexdigest() == expected


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--proxy', required=True)
    parser.add_argument('--remote-root', required=True)
    parser.add_argument('--wait-pid', type=int)
    args = parser.parse_args()
    lock = (args.root / 'transfer.lock').open('w')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    manifest = json.loads((args.root / 'official_manifest.json').read_text())
    if manifest['sha'] != REVISION:
        raise RuntimeError('Official release mismatch')
    if args.wait_pid:
        print(f'WAIT_EXISTING_CURL pid={args.wait_pid}', flush=True)
        while True:
            try:
                os.kill(args.wait_pid, 0)
            except ProcessLookupError:
                break
            time.sleep(5)
    items = [x for x in manifest['siblings']
             if x['rfilename'].endswith('.safetensors')
             and not Path(x['rfilename']).name.startswith(EXCLUDED)]
    # Continue the already-started large file first, then remaining weights.
    items.sort(key=lambda x: (not x['rfilename'].startswith('ckpts/suv_flow_'),
                              not x['rfilename'].endswith('.safetensors'),
                              x['rfilename']))
    receipt_path = args.root / 'local_transfer_receipt.json'
    receipt = (json.loads(receipt_path.read_text()) if receipt_path.exists() else
               {'revision': REVISION, 'remote_root': args.remote_root,
                'status': 'TRANSFERRING_SUBSET', 'files': {}})
    if receipt['remote_root'] != args.remote_root or receipt['revision'] != REVISION:
        raise RuntimeError('Transfer identity mismatch')

    def save():
        temp = receipt_path.with_suffix('.tmp')
        temp.write_text(json.dumps(receipt, indent=2) + '\n')
        temp.replace(receipt_path)

    for item in items:
        name = item['rfilename']
        if Path(name).is_absolute() or '..' in Path(name).parts:
            raise RuntimeError('Unsafe manifest path')
        target = args.root / name
        partial = target.with_name(target.name + '.partial')
        target.parent.mkdir(parents=True, exist_ok=True)
        if not verified(target, item):
            if target.exists():
                raise RuntimeError(f'Existing final file failed verification: {name}')
            deadline = time.monotonic() + 14400
            while not verified(partial, item):
                if partial.exists() and partial.stat().st_size >= item['size']:
                    raise RuntimeError(f'Official hash or length mismatch: {name}')
                if time.monotonic() >= deadline:
                    raise RuntimeError(f'Local transfer time budget exceeded: {name}')
                print(f'LOCAL_DOWNLOAD {name}', flush=True)
                result = subprocess.run([
                    'curl', '--fail', '--silent', '--show-error', '--location',
                    '--proxy', args.proxy, '--noproxy', '', '--connect-timeout', '15',
                    '--speed-limit', '1024', '--speed-time', '60', '--max-time', '1800',
                    '--continue-at', '-', '--output', str(partial),
                    f'https://huggingface.co/hbb1/Cupid/resolve/{REVISION}/{name}?download=true',
                ])
                print(f'LOCAL_CURL_EXIT {result.returncode} file={name}', flush=True)
                if result.returncode != 0:
                    time.sleep(5)
            partial.replace(target)
        receipt['files'].setdefault(name, {})['local'] = 'OFFICIAL_HASH_VERIFIED'
        save()
        print(f'LOCAL_VERIFIED {name} bytes={item["size"]}', flush=True)
        if receipt['files'][name].get('remote') == 'SHA256_VERIFIED':
            continue
        digest = hashlib.sha256()
        with target.open('rb') as handle:
            for block in iter(lambda: handle.read(8 * 1024 * 1024), b''):
                digest.update(block)
        expected = digest.hexdigest()
        remote = args.remote_root + '/' + name
        incoming = remote + '.incoming_' + str(time.time_ns())
        # srun receives stdin on a compute node. Login only carries the SSH
        # stream; no model bytes are written or hashed on the login node.
        body = '\n'.join([
            'set -eu', 'umask 077',
            'echo TRANSFER_JOB=$SLURM_JOB_ID NODE=$(hostname)',
            'mkdir -p ' + shlex.quote(str(Path(remote).parent)),
            'set -C', 'cat > ' + shlex.quote(incoming), 'set +C',
            'test "$(sha256sum ' + shlex.quote(incoming) + ' | cut -d " " -f 1)" = ' + shlex.quote(expected),
            # Hard-link creation fails atomically if a final file exists.
            # Keep the verified incoming file as provenance if that occurs.
            'ln ' + shlex.quote(incoming) + ' ' + shlex.quote(remote),
            'echo REMOTE_SHA256_VERIFIED ' + shlex.quote(name),
        ])
        command = ('/opt/gridview/slurm/bin/srun -p cpu -N 1 -n 1 -c 1 --mem=1G '
                   '-t 01:00:00 --job-name=cupid_local_upload /bin/bash -c ' + shlex.quote(body))
        print(f'UPLOAD_START {name}', flush=True)
        with target.open('rb') as source:
            result = subprocess.run(['ssh', '-T', '-o', 'BatchMode=yes', '-o',
                                     'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=15',
                                     '-o', 'ServerAliveInterval=15', '-o', 'ServerAliveCountMax=3',
                                     'ricky@10.10.7.1', command], stdin=source,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        print(result.stdout, flush=True)
        receipt['files'][name]['upload_readback'] = result.stdout
        if result.returncode != 0:
            receipt['files'][name]['remote'] = 'UPLOAD_UNVERIFIED'
            save()
            raise RuntimeError(f'Upload failed; preserve incoming evidence: {name}')
        receipt['files'][name]['remote'] = 'SHA256_VERIFIED'
        receipt['files'][name]['sha256'] = expected
        save()
    receipt['status'] = 'SUBSET_UPLOADED_VERIFIED_NOT_FULL_PIPELINE'
    save()
    print(receipt['status'], flush=True)


if __name__ == '__main__':
    main()
