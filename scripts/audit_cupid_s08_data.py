import csv
import hashlib
import json
import os
from pathlib import Path


EXPECTED_METADATA_ROWS = 6670
EXPECTED_FILTERED_INSTANCES = 6467
LATENT_MODEL = "dinov2_vitl14_reg_slat_enc_swin8_B_64l8_fp16"


def _truthy(value):
    return str(value).strip().lower() in {"1", "true", "yes"}


def main():
    checkout = Path(os.environ["CUPID_AUDIT_CHECKOUT"])
    output_dir = Path(os.environ["CUPID_AUDIT_OUTPUT_DIR"])
    expected_commit = os.environ["CUPID_AUDIT_EXPECTED_COMMIT"]
    data_dir = Path(os.environ.get("CUPID_DATA_DIR", "/data/group_gao/trellis/HSSD"))
    config_path = checkout / os.environ.get(
        "CUPID_CONFIG",
        "configs/generation/slat_flow_img_dit_L_64l8p2_fp16-posecond-cluster.json",
    )
    checkpoints = [
        Path(path)
        for path in os.environ["CUPID_REQUIRED_CHECKPOINTS"].split(os.pathsep)
    ]

    with config_path.open() as config_file:
        config = json.load(config_file)
    with (data_dir / "metadata.csv").open(newline="") as metadata_file:
        rows = list(csv.DictReader(metadata_file))

    latent_key = f"latent_{LATENT_MODEL}"
    filtered = [
        row
        for row in rows
        if _truthy(row[latent_key])
        and float(row["aesthetic_score"]) >= 4.5
        and int(float(row["num_voxels"])) <= 32768
        and _truthy(row["cond_rendered"])
    ]

    missing_latents = []
    missing_renders = []
    for row in filtered:
        instance = row["sha256"]
        latent_path = data_dir / "latents" / LATENT_MODEL / f"{instance}.npz"
        render_dir = data_dir / "renders_cond" / instance
        if not latent_path.is_file():
            missing_latents.append(instance)
        if not render_dir.is_dir() or not (render_dir / "transforms.json").is_file():
            missing_renders.append(instance)

    checkpoint_records = []
    for checkpoint in checkpoints:
        if checkpoint.suffix:
            required_files = [checkpoint]
            kind = "file"
        else:
            # models.from_pretrained() resolves a local model prefix to this pair.
            required_files = [
                Path(f"{checkpoint}.json"),
                Path(f"{checkpoint}.safetensors"),
            ]
            kind = "model_prefix"
        files = [
            {
                "path": str(path),
                "exists": path.is_file(),
                "size": path.stat().st_size if path.is_file() else None,
            }
            for path in required_files
        ]
        checkpoint_records.append(
            {
                "path": str(checkpoint),
                "kind": kind,
                "exists": all(item["exists"] for item in files),
                "files": files,
            }
        )

    trainer = config["trainer"]["args"]
    dataset = config["dataset"]["args"]
    receipt = {
        "schema": "cupid_s08_bounded_data_audit/v1",
        "status": "PASS",
        "run_class": "PREFLIGHT_DEBUG",
        "evidence_eligibility": "DEBUG_ONLY / NO_SCIENCE",
        "commit": expected_commit,
        "data_root": str(data_dir),
        "metadata_rows": len(rows),
        "filtered_instances": len(filtered),
        "missing_latents": missing_latents,
        "missing_renders_cond": missing_renders,
        "checkpoints": checkpoint_records,
        "formal_contract": {
            "max_steps": trainer["max_steps"],
            "batch_size_per_gpu": trainer["batch_size_per_gpu"],
            "batch_split": trainer["batch_split"],
            "max_num_voxels": dataset["max_num_voxels"],
            "ema_rate": trainer["ema_rate"],
            "optimizer": trainer["optimizer"]["name"],
            "scheduler": trainer["lr_scheduler"]["name"],
            "fp16_mode": trainer["fp16_mode"],
            "i_sample": trainer["i_sample"],
            "i_save": trainer["i_save"],
        },
    }

    predicates = [
        len(rows) == EXPECTED_METADATA_ROWS,
        len(filtered) == EXPECTED_FILTERED_INSTANCES,
        not missing_latents,
        not missing_renders,
        all(record["exists"] for record in checkpoint_records),
    ]
    if not all(predicates):
        receipt["status"] = "FAIL"

    output_dir.mkdir(parents=True, exist_ok=False)
    receipt_path = output_dir / "data_audit_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print("DATA_AUDIT_RESULT=" + json.dumps(receipt, sort_keys=True), flush=True)
    print(
        "DATA_AUDIT_RECEIPT_SHA256="
        + hashlib.sha256(receipt_path.read_bytes()).hexdigest(),
        flush=True,
    )
    if receipt["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
