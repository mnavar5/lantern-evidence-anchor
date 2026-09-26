#!/usr/bin/env python3
"""Lantern evidence anchor.

Publishes an independent, timestamped copy of every Lantern vault checkpoint. A checkpoint is a Merkle root over
a batch of evidence records plus the hash of the previous checkpoint, so each one commits to everything before it.

This job holds no secrets and cannot touch evidence. It reads the public checkpoint roots (hashes only) from
Lantern's Supabase Data API, checks that each checkpoint's hash is correct and links to the one before, writes
anchors/<seq>.json, and timestamps that file with OpenTimestamps (free, Bitcoin-backed). If a checkpoint that was
already anchored ever comes back different, it writes an alert and fails, so GitHub notifies the owner.
"""
import hashlib
import json
import os
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ANCHORS, ALERTS = ROOT / 'anchors', ROOT / 'alerts'
FIELDS = ('seq', 'created', 'first_capture', 'last_capture', 'leaves', 'merkle_root', 'chain_head', 'prev_checkpoint')
GENESIS = '0' * 64

def checkpoint_hash(cp):
    """Same rule as Lantern's vault: SHA-256 of the canonical JSON of the checkpoint fields."""
    canonical = json.dumps({k: cp[k] for k in FIELDS}, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
    return hashlib.sha256(canonical).hexdigest()

def fetch_roots(url, key):
    req = urllib.request.Request(url.rstrip('/') + '/rest/v1/checkpoint_roots?select=*&order=seq.asc',
                                 headers={'apikey': key, 'Accept': 'application/json', 'User-Agent': 'lantern-evidence-anchor'})
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read())

def path_for(seq):
    return ANCHORS / ('%06d.json' % seq)

def document(cp):
    return json.dumps({k: cp[k] for k in FIELDS + ('checkpoint_hash',)}, indent=2, sort_keys=True) + '\n'

def validate(cps):
    """Problems with the chain as served, and already-anchored checkpoints that changed."""
    problems, prev = [], GENESIS
    for i, cp in enumerate(cps, 1):
        if cp['seq'] != i:
            problems.append('checkpoint sequence gap or reorder at position %d (seq %s)' % (i, cp['seq']))
        if checkpoint_hash(cp) != cp['checkpoint_hash']:
            problems.append('checkpoint %s: hash does not match its fields' % cp['seq'])
        if cp['prev_checkpoint'] != prev:
            problems.append('checkpoint %s: does not link to the previous checkpoint' % cp['seq'])
        prev = cp['checkpoint_hash']
        existing = path_for(cp['seq'])
        if existing.exists() and existing.read_text() != document(cp):
            problems.append('checkpoint %s: differs from the copy anchored earlier (possible rewrite)' % cp['seq'])
    anchored = sorted(int(p.stem) for p in ANCHORS.glob('*.json'))
    if anchored and anchored[-1] > len(cps):
        problems.append('checkpoints up to %d were anchored but only %d are served now (possible truncation)' % (anchored[-1], len(cps)))
    return problems

def ots(*args):
    return subprocess.run(['ots', *args], capture_output=True, text=True)

def main():
    url, key = os.environ.get('LANTERN_SUPABASE_URL'), os.environ.get('LANTERN_SUPABASE_KEY')
    if not url or not key:
        print('Not configured: set repository variables LANTERN_SUPABASE_URL and LANTERN_SUPABASE_KEY (public values).')
        return 0
    ANCHORS.mkdir(exist_ok=True)
    cps = fetch_roots(url, key)
    problems = validate(cps)
    if problems:
        ALERTS.mkdir(exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H%M%SZ')
        (ALERTS / (stamp + '.json')).write_text(json.dumps({'detected': stamp, 'problems': problems, 'served': cps}, indent=2) + '\n')
        print('ALERT: ' + '; '.join(problems))
        return 1
    new = [cp for cp in cps if not path_for(cp['seq']).exists()]
    for cp in new:
        path = path_for(cp['seq'])
        path.write_text(document(cp))
        result = ots('stamp', str(path))
        if result.returncode != 0:
            print('OpenTimestamps stamp failed for %s: %s' % (path.name, result.stderr.strip()))
            return 1
    upgraded = 0
    for receipt in sorted(ANCHORS.glob('*.ots')):
        if ots('upgrade', str(receipt)).returncode == 0:
            upgraded += 1
    print('Checkpoints served: %d · newly anchored: %d · receipts upgraded or pending: %d' % (len(cps), len(new), upgraded))
    return 0

if __name__ == '__main__':
    sys.exit(main())
