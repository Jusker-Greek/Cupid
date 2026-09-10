import argparse
import json
import time
from pathlib import Path

import wandb


REQUIRED_BASE_KEYS = {
    "train/global_step",
    "train/learning_rate",
    "train/loss_total",
    "smoke/optimizer_step_applied",
    "smoke/checkpoint_written",
}

REQUIRED_SUMMARY_VALUES = {
    "contract/validation_loss": "NOT_APPLICABLE",
    "contract/test_loss": "NOT_APPLICABLE",
    "contract/pose_rotation_error": "NOT_APPLICABLE",
    "contract/pose_direction_error": "NOT_APPLICABLE",
    "contract/pose_translation_scale": "NOT_APPLICABLE",
    "contract/pose_translation_norm": "NOT_APPLICABLE",
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("--attempts", type=int, default=6)
    parser.add_argument("--interval", type=int, default=10)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    contract = json.loads((output_dir / "smoke_observability.json").read_text())
    required_keys = REQUIRED_BASE_KEYS | set(contract["required_scalar_tags"])
    run_receipt = json.loads((output_dir / "wandb_run.json").read_text())
    run_path = "/".join(
        [run_receipt["entity"], run_receipt["project"], run_receipt["id"]]
    )

    last_seen = set()
    for attempt in range(1, args.attempts + 1):
        run = wandb.Api().run(run_path)
        # Fetch all rows because sparse per-bin loss keys are not present on every step.
        rows = list(run.scan_history(page_size=1000))
        last_seen = {key for row in rows for key in required_keys if row.get(key) is not None}
        summary = dict(run.summary)
        summary_ok = all(
            str(summary.get(key, "")).startswith(expected)
            for key, expected in REQUIRED_SUMMARY_VALUES.items()
        )
        if required_keys <= last_seen and summary_ok:
            receipt = {
                "schema": "cupid_wandb_readback/v1",
                "status": "PASS",
                "run_path": run_path,
                "url": run.url,
                "state": run.state,
                "required_keys": sorted(required_keys),
                "seen_keys": sorted(last_seen),
                "required_summary_values": REQUIRED_SUMMARY_VALUES,
                "summary_values": {
                    key: summary.get(key) for key in REQUIRED_SUMMARY_VALUES
                },
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

    missing = sorted(required_keys - last_seen)
    missing_summary = [
        key for key, expected in REQUIRED_SUMMARY_VALUES.items()
        if not str(summary.get(key, "")).startswith(expected)
    ]
    raise RuntimeError(
        "W&B server readback missing required evidence after retries: "
        f"history={missing}, summary={missing_summary}"
    )


if __name__ == "__main__":
    main()
