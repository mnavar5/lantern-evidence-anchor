# Lantern evidence anchor

An independent, public record of when [Lantern — Agent Observatory](https://github.com/mnavar5/Agent-HouseBoard)'s evidence existed.

Lantern stores every captured source in an append-only vault. Once a day it seals the new records into a **checkpoint**: a Merkle root over that day's records plus the hash of the previous checkpoint, so each checkpoint commits to everything before it.

This repository holds a copy of every checkpoint (`anchors/<seq>.json`, hashes only, never content) and an [OpenTimestamps](https://opentimestamps.org) receipt for each (`anchors/<seq>.json.ots`). The receipt proves the file, and therefore the checkpoint, existed no later than a specific Bitcoin block.

## What this proves
- **When:** a checkpoint existed by the time in its receipt.
- **Consistency:** each checkpoint's hash matches its fields and links to the previous one. If a checkpoint that was already anchored ever changes, the daily job writes `alerts/<time>.json` and fails.
- **Inclusion:** Lantern can prove a single evidence record belongs to a checkpoint (`vault.py prove <capture>`) without revealing any other record.

## Verify a checkpoint yourself
```sh
pip install opentimestamps-client
ots verify anchors/000001.json.ots   # needs a Bitcoin node, or upload the .ots at https://opentimestamps.org
```
A receipt is *pending* for a few hours until its Bitcoin transaction confirms; the daily job upgrades it automatically.

## How it runs
A daily GitHub Actions job (`.github/workflows/anchor.yml`) reads the public checkpoint roots from Lantern's Supabase Data API with the public key, validates the chain, anchors new checkpoints and commits. It has no secrets and no access to Lantern's evidence, database writes or code; its only write permission is to this repository.

Configuration: repository variables `LANTERN_SUPABASE_URL` and `LANTERN_SUPABASE_KEY` (both public values).
