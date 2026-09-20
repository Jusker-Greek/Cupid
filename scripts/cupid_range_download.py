"""Bounded HTTP ranges with durable chunks and final official-file verification."""
import hashlib
import shutil
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

CHUNK_BYTES = 4 * 1024 * 1024


def download_ranges(item, output, repo, revision, verify, trust_env, reuse=None):
    name, size = item['rfilename'], item['size']
    target = output / name
    target.parent.mkdir(parents=True, exist_ok=True)
    if reuse is not None and verify(reuse / name, item):
        shutil.copyfile(reuse / name, target)
        if not verify(target, item):
            raise RuntimeError('Reused file verification failed')
        print(f'VERIFIED_REUSED {name} {size}', flush=True)
        return
    parts = output / '.ranges' / name
    parts.mkdir(parents=True, exist_ok=False)
    stop = threading.Event()
    starts = list(range(0, size, CHUNK_BYTES))

    def get_part(start):
        end = min(start + CHUNK_BYTES, size) - 1
        expected_size = end - start + 1
        part = parts / f'{start:012d}.bin'
        digest_path = part.with_suffix('.sha256')
        if stop.is_set():
            raise RuntimeError('Range transfer cancelled')
        if reuse is not None:
            old = reuse / '.ranges' / name / part.name
            digest = old.with_suffix('.sha256')
            if old.is_file() and old.stat().st_size == expected_size and digest.is_file():
                value = old.read_bytes()
                if hashlib.sha256(value).hexdigest() == digest.read_text().strip():
                    part.write_bytes(value)
                    digest_path.write_text(hashlib.sha256(value).hexdigest() + '\n')
                    return expected_size
        for attempt in range(1, 6):
            if stop.is_set():
                raise RuntimeError('Range transfer cancelled')
            try:
                with requests.Session() as session:
                    session.trust_env = trust_env
                    headers = {'Range': f'bytes={start}-{end}', 'Accept-Encoding': 'identity'}
                    with session.get(f'https://huggingface.co/{repo}/resolve/{revision}/{name}',
                                     params={'download': 'true', 'range_attempt': str(time.time_ns())},
                                     headers=headers, stream=True, timeout=(15, 40)) as response:
                        expected_range = f'bytes {start}-{end}/{size}'
                        if response.status_code == 206:
                            if response.headers.get('Content-Range') != expected_range:
                                raise RuntimeError('CONTENT_RANGE_MISMATCH')
                        elif not (response.status_code == 200 and start == 0 and expected_size == size):
                            raise RuntimeError(f'HTTP_{response.status_code}_RANGE_NOT_ACCEPTED')
                        value = bytearray()
                        # The proxy can keep a stream alive below 4 MiB/90 s.
                        # Allow slow but active progress; the 40 s socket read
                        # timeout still catches a stalled connection.
                        deadline = time.monotonic() + 300
                        for block in response.iter_content(64 * 1024):
                            if stop.is_set() or time.monotonic() > deadline:
                                raise RuntimeError('RANGE_DEADLINE')
                            value.extend(block)
                            if len(value) > expected_size:
                                raise RuntimeError('RANGE_SIZE_OVERFLOW')
                        if len(value) != expected_size:
                            raise RuntimeError('RANGE_SIZE_MISMATCH')
                partial = part.with_suffix('.partial')
                with partial.open('wb') as handle:
                    handle.write(value)
                    handle.flush()
                    import os
                    os.fsync(handle.fileno())
                partial.rename(part)
                digest_path.write_text(hashlib.sha256(value).hexdigest() + '\n')
                return expected_size
            except (requests.RequestException, RuntimeError) as error:
                reason = str(error) if isinstance(error, RuntimeError) else type(error).__name__
                print(f'RANGE_RETRY file={name} start={start} attempt={attempt} reason={reason}', flush=True)
                if attempt == 5:
                    stop.set()
                    raise RuntimeError(f'Range failed: {name} offset={start}') from None
                stop.wait(min(2 ** attempt, 15))

    # Concurrent streams through the shared proxy stalled together in a16.
    # Isolate the transport with one stream; retain the same chunks/checks.
    pool = ThreadPoolExecutor(max_workers=1)
    futures = [pool.submit(get_part, start) for start in starts]
    completed = 0
    try:
        for future in as_completed(futures):
            completed += future.result()
            print(f'RANGE_PROGRESS file={name} durable_bytes={completed}/{size}', flush=True)
    finally:
        stop.set()
        pool.shutdown(wait=True, cancel_futures=True)
    assembled = target.with_name(target.name + '.partial')
    with assembled.open('wb') as handle:
        for start in starts:
            with (parts / f'{start:012d}.bin').open('rb') as source:
                shutil.copyfileobj(source, handle, length=CHUNK_BYTES)
    if not verify(assembled, item):
        raise RuntimeError(f'Official file hash mismatch: {name}')
    assembled.rename(target)
    print(f'VERIFIED {name} {size}', flush=True)
