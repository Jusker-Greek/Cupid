import argparse
import json
import time
from pathlib import Path

import wandb


REQUIRED_KEYS = {
    "train/global_step",
    "train/learning_rate",
    "train/loss_total",
    "smoke/optimizer_step_applied",
    "smoke/checkpoint_written",
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("--attempts", type=int, default=6)
    parser.add_argument("--interval", type=int, default=10)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    run_receipt = json.loads((output_dir / "wandb_run.json").read_text())
    run_path = "/".join(
        [run_receipt["entity"], run_receipt["project"], run_receipt["id"]]
    )

    last_seen = set()
    for attempt in range(1, args.attempts + 1):
        run = wandb.Api().run(run_path)
        rows = list(run.scan_history(keys=sorted(REQUIRED_KEYS), page_size=1000))
        last_seen = {key for row in rows for key in REQUIRED_KEYS if row.get(key) is not None}
        if REQUIRED_KEYS <= last_seen:
            receipt = {
                "schema": "cupid_wandb_readback/v1",
                "status": "PASS",
                "run_path": run_path,
                "url": run.url,
                "state": run.state,
                "required_keys": sorted(REQUIRED_KEYS),
                "seen_keys": sorted(last_seen),
                "attempt": attempt,
                "evidence_eligibility": "DEBUG_ONLY / NO_SCIENCE",
            }
            (output_dir / "wandb_readback.json").write_text(
                json.dumps(receipt, indent=2, sort_keys=True) + "\n"
            )
            print("WANDB_READBACK=" + json.dumps(receipt, sort_keys=True), flush=True)
            return
        if attempt < args.attempts:
            time.sleep(args.interval)

    missing = sorted(REQUIRED_KEYS - last_seen)
    raise RuntimeError(f"W&B server readback missing required keys after retries: {missing}")


if __name__ == "__main__":
    main()
