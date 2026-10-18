#!/usr/bin/env python3
"""GPU Slurm-only native/adapter parity and finite-difference audit, no model training."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def main():
    parser=argparse.ArgumentParser(__doc__)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    if not os.environ.get('SLURM_JOB_ID') or not os.environ.get('SLURMD_NODENAME'):
        parser.error('Slurm compute node required')
    output=Path(args.output)
    output.mkdir(parents=True,exist_ok=False)
    receipt=dict(schema='SC_POSECROSS_RENDERER_ADAPTER_V1',status='RUNNING',
        scope='ANISOTROPIC_SYNTHETIC_COMPONENT_ONLY',scientific_evidence=False,model_smoke=False,
        job=os.environ['SLURM_JOB_ID'],node=os.environ['SLURMD_NODENAME'],
        commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        tree=subprocess.check_output(['git','rev-parse','HEAD^{tree}'],text=True).strip())
    try:
        import torch
        from cupid.renderers.gaussian_render import GaussianRenderer
        from cupid.renderers.posecross_gaussian import CameraGradientGaussianRenderer
        from cupid.representations.gaussian import Gaussian
        torch.manual_seed(1842)
        device='cuda'
        options=dict(resolution=96,near=.1,far=10.,ssaa=1,bg_color=[0,0,0])
        native,adapter=GaussianRenderer(options),CameraGradientGaussianRenderer(options)
        xyz=torch.tensor([[-.21,-.11,.03],[.13,.17,.11],[.02,-.16,-.09]],device=device,requires_grad=True)
        gs=Gaussian([-.5,-.5,-.5,1.,1.,1.],sh_degree=0,device=device)
        gs.from_xyz(xyz)
        gs.from_scaling(torch.tensor([[.04,.07,.05],[.08,.03,.05],[.05,.04,.09]],device=device))
        gs.from_rotation(torch.nn.functional.normalize(torch.tensor([[1.,.1,.2,.0],[1.,-.2,.1,.1],[1.,.0,.2,-.1]],device=device),dim=1))
        gs.from_opacity(torch.full((3,1),.8,device=device))
        gs.from_features(torch.tensor([[[1.],[0.],[.3]],[[0.],[1.],[.1]],[[.2],[.3],[1.]]],device=device).transpose(1,2).contiguous())
        K=torch.tensor([[.9,0,.46],[0,1.05,.53],[0,0,1.]],device=device)
        def pose(p):
            c,s=torch.cos(p[0]),torch.sin(p[0])
            z,o=p.new_tensor(0.),p.new_tensor(1.)
            return torch.stack((c,z,s,p[1], z,o,z,z-.04, -s,z,c,z+2., z,z,z,o)).reshape(4,4)
        weights=torch.linspace(.2,1.3,96,device=device)[None,None,:]
        def scalar(p):
            return (adapter.render(gs,pose(p),K)['color']*weights).mean()
        p=torch.tensor([.13,.08],device=device,requires_grad=True)
        a=adapter.render(gs,pose(p),K)['color']
        with torch.no_grad():
            n=native.render(gs,pose(p),K)['color']
        loss=(a*weights).mean()
        gp,gx=torch.autograd.grad(loss,(p,xyz))
        rows=[]
        boundary_diagnostics=[]
        with torch.no_grad():
            for index,name in enumerate(('rotation_y','translation_x')):
                for eps in (3e-3,1e-3,3e-4):
                    plus,minus=p.detach().clone(),p.detach().clone()
                    plus[index]+=eps
                    minus[index]-=eps
                    fd=float((scalar(plus)-scalar(minus))/(2*eps))
                    ad=float(gp[index])
                    rows.append(dict(parameter=name,eps=eps,autograd=ad,finite_difference=fd,
                        absolute_error=abs(ad-fd),relative_error=abs(ad-fd)/max(abs(ad),abs(fd),1e-8)))
                # A separate cause-finding sweep does not replace the acceptance
                # rows/epsilons above. Track support changes across alpha cutoffs.
                for eps in (1e-2,3e-3,1e-3,3e-4,1e-4,3e-5,1e-5,3e-6):
                    plus,minus=p.detach().clone(),p.detach().clone()
                    plus[index]+=eps
                    minus[index]-=eps
                    ip=adapter.render(gs,pose(plus),K)['color']
                    im=adapter.render(gs,pose(minus),K)['color']
                    fd=float(((ip-im)*weights).mean()/(2*eps))
                    ad=float(gp[index])
                    boundary_diagnostics.append(dict(parameter=name,eps=eps,
                        autograd=ad,finite_difference=fd,
                        changed_nonzero_pixels=int(((ip.abs().sum(0)>0)!=(im.abs().sum(0)>0)).sum()),
                        relative_error=abs(ad-fd)/max(abs(ad),abs(fd),1e-8)))
        delta=float((a-n).abs().max().detach())
        finite=bool(torch.isfinite(gp).all() and torch.isfinite(gx).all())
        nonzero=bool((gp.abs()>1e-8).all() and gx.norm()>1e-8)
        # Both smaller FD steps for each pose component must meet the predeclared 5% bound.
        fd_pass=all(r['relative_error']<.05 for r in rows if r['eps'] in (1e-3,3e-4))
        receipt.update(forward_max_abs=delta,forward_mean_abs=float((a-n).abs().mean().detach()),
            pose_gradient=gp.tolist(),primitive_gradient_norm=float(gx.norm()),finite_gradients=finite,
            nonzero_gradients=nonzero,finite_difference=rows,
            boundary_diagnostics=boundary_diagnostics,
            tolerances=dict(forward_max_abs=1e-4,pose_fd_relative=.05,nonzero_min=1e-8),
            status='PASS' if delta<1e-4 and finite and nonzero and fd_pass else 'FAIL')
        if receipt['status']!='PASS':
            raise RuntimeError('Adapter parity/gradient contract failed; thresholds remain frozen')
    except Exception as exc:
        receipt.update(status='ERROR' if receipt['status']=='RUNNING' else receipt['status'],error=type(exc).__name__+': '+str(exc))
        raise
    finally:
        (output/'receipt.json').write_text(json.dumps(receipt,indent=2,allow_nan=False)+'\n')
        print(json.dumps(receipt,indent=2,allow_nan=False),flush=True)


if __name__=='__main__':
    main()
