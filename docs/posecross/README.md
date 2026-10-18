# SC-POSECROSS-V1 component and data audit preparation

These entry points are engineering diagnostics, not a trainable cross-pose
method, proxy objective, pretrained model smoke, S05 pass, or scientific result.
They must only run on Slurm compute nodes after local commit/push and fresh
exact-source checkout. The native training and inference implementations are
unchanged. The main method remains at S01 pending the design/data contract.

- `scripts/posecross_component_audit.py`: use the real native Gaussian renderer
  on explicit synthetic primitives; compare camera autograd to translation
  finite differences and verify primitive gradients. Also audit native DLT's
  UV gradient and whether changing the supplied K changes its outputs.
- `scripts/posecross_data_audit.py`: re-read every bound GSO pair and target
  hash; check all three splits, object/image/source-asset overlap, existing
  empirical camera mapping, rectification residuals and effective crop K.
  Numeric consistency never approves historical renderer/canonical provenance.
- `scripts/posecross_audit_job.sh`: exact clean checkout and Slurm guards;
  `components` requires one GPU; `data` is a CPU job. No automatic submissions.

A completed diagnostic can report a failed component contract. Read the JSON
fields, not only the process exit. No optimizer/checkpoint/flow result is implied.
