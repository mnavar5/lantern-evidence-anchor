import json
import tempfile
import unittest
from pathlib import Path

import anchor

def chain(n):
    cps, prev = [], anchor.GENESIS
    for i in range(1, n + 1):
        cp = {'seq': i, 'created': '2026-09-%02dT00:17:00+00:00' % i, 'first_capture': (i - 1) * 10 + 1, 'last_capture': i * 10,
              'leaves': 10, 'merkle_root': '%064x' % i, 'chain_head': '%064x' % (i + 100), 'prev_checkpoint': prev}
        cp['checkpoint_hash'] = anchor.checkpoint_hash(cp)
        prev = cp['checkpoint_hash']
        cps.append(cp)
    return cps

class AnchorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        anchor.ANCHORS = Path(self.tmp.name) / 'anchors'
        anchor.ANCHORS.mkdir()
    def tearDown(self):
        self.tmp.cleanup()
    def test_valid_chain_passes(self):
        self.assertEqual(anchor.validate(chain(3)), [])
    def test_altered_or_unlinked_checkpoint_is_flagged(self):
        cps = chain(3)
        cps[1]['merkle_root'] = 'f' * 64
        problems = ' '.join(anchor.validate(cps))
        self.assertIn('hash does not match', problems)
    def test_rewrite_of_an_anchored_checkpoint_is_flagged(self):
        cps = chain(2)
        anchor.path_for(1).write_text(anchor.document(cps[0]))
        rewritten = chain(2)
        rewritten[0]['created'] = '2026-09-01T00:18:00+00:00'
        rewritten[0]['checkpoint_hash'] = anchor.checkpoint_hash(rewritten[0])
        rewritten[1]['prev_checkpoint'] = rewritten[0]['checkpoint_hash']
        rewritten[1]['checkpoint_hash'] = anchor.checkpoint_hash(rewritten[1])
        self.assertTrue(any('possible rewrite' in p for p in anchor.validate(rewritten)))
    def test_truncation_after_anchoring_is_flagged(self):
        cps = chain(3)
        for cp in cps:
            anchor.path_for(cp['seq']).write_text(anchor.document(cp))
        self.assertTrue(any('truncation' in p for p in anchor.validate(cps[:2])))

if __name__ == '__main__':
    unittest.main()
