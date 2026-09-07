import argparse
import json
import math
import os

from tensorboard.backend.event_processing.event_accumulator import EventAccumulator


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output_dir", required=True)
    return parser.parse_args()


def main():
    args = parse_args()
    contract_path = os.path.join(args.output_dir, "smoke_observability.json")
    with open(contract_path) as fp:
        contract = json.load(fp)

    accumulator = EventAccumulator(os.path.join(args.output_dir, "tb_logs"))
    accumulator.Reload()
    tags = accumulator.Tags()
    scalar_tags = set(tags["scalars"])
    missing_scalars = set(contract["required_scalar_tags"]) - scalar_tags
    if missing_scalars:
        raise RuntimeError(f"Missing TensorBoard scalar tags: {sorted(missing_scalars)}")

    scalar_summary = {}
    for tag in contract["required_scalar_tags"]:
        events = accumulator.Scalars(tag)
        if not events:
            raise RuntimeError(f"TensorBoard scalar tag has no events: {tag}")
        values = [event.value for event in events]
        if not all(math.isfinite(value) for value in values):
            raise RuntimeError(f"TensorBoard scalar tag is non-finite: {tag}={values}")
        scalar_summary[tag] = {
            "count": len(values),
            "last_step": events[-1].step,
            "last_value": values[-1],
        }

    tensor_tags = set(tags["tensors"])
    required_text_prefixes = {
        "contract/validation_loss": "NOT_APPLICABLE",
        "contract/pose_metrics": "NOT_APPLICABLE",
    }
    matched_text_tags = {}
    for prefix, required_text in required_text_prefixes.items():
        candidates = sorted(tag for tag in tensor_tags if tag.startswith(prefix))
        if not candidates:
            raise RuntimeError(f"Missing TensorBoard text tag for {prefix}")
        tensor_event = accumulator.Tensors(candidates[0])[-1]
        text = tensor_event.tensor_proto.string_val[0].decode("utf-8")
        if required_text not in text:
            raise RuntimeError(f"TensorBoard text tag {candidates[0]} lacks {required_text}")
        matched_text_tags[prefix] = candidates[0]

    result = {
        "status": "PASS",
        "schema": "cupid_tensorboard_readback/v1",
        "output_dir": args.output_dir,
        "scalars": scalar_summary,
        "text_tags": matched_text_tags,
        "not_applicable": contract["not_applicable"],
        "evidence_eligibility": "DEBUG_ONLY / NO_SCIENCE",
    }
    print("TENSORBOARD_READBACK=" + json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
