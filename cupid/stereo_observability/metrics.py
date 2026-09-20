"""Raw, unaligned object-to-camera Sim(3) metrics with explicit eligibility.

Inputs are ordinary JSON objects. No fitting/alignment to GT takes place here.
Canonical IDs must encode axes, origin AND normalization; frame IDs must encode
camera/view and handedness. Provenance is asserted by the data adapter, not
inferred from filenames or a scene_unit label.
"""
import math
from collections import Counter

METRICS = (
    'rotation_error_deg', 'translation_error', 'translation_error_m',
    'translation_direction_error_deg', 'translation_norm', 'translation_norm_gt',
    'translation_norm_ratio', 'translation_norm_abs_error',
    'pose_scale', 'pose_scale_gt', 'scale_abs_error', 'scale_relative_error',
)


def result(value=None, status='UNVERIFIED', reason='not_evaluated', unit=None):
    return dict(value=value, status=status, reason=reason, unit=unit)


def number(value):
    if isinstance(value, bool):
        raise ValueError('boolean_not_scalar')
    value = float(value)
    if not math.isfinite(value):
        raise ValueError('nonfinite_scalar')
    return value


def vector(value):
    if len(value) != 3:
        raise ValueError('expected_vector3')
    return [number(x) for x in value]


def rotation(value):
    r = [vector(row) for row in value]
    if len(r) != 3:
        raise ValueError('expected_rotation3x3')
    dot = lambda a, b: sum(x*y for x, y in zip(a, b))
    if max(abs(dot(r[i], r[j]) - (i == j)) for i in range(3) for j in range(3)) > 1e-5:
        raise ValueError('rotation_not_orthogonal')
    det = (r[0][0]*(r[1][1]*r[2][2]-r[1][2]*r[2][1])
           - r[0][1]*(r[1][0]*r[2][2]-r[1][2]*r[2][0])
           + r[0][2]*(r[1][0]*r[2][1]-r[1][1]*r[2][0]))
    if abs(det-1) > 1e-5:
        raise ValueError('rotation_not_proper_SO3')
    return r


def norm(v):
    return math.sqrt(sum(x*x for x in v))


def angle(cosine):
    return math.degrees(math.acos(max(-1., min(1., cosine))))


def evaluate_sample(sample):
    """One sample always returns all metrics, including failed/missing predictions.

    sample: sample_id, prediction_status=OK, prediction={rotation,translation,
    scale,canonical_id,target_frame,length_unit}, gt={same fields,verified:true,
    provenance:<reference>,metric_unit_verified:true/false},
    prediction_uses_gt_alignment:false (must be explicit).
    """
    if not str(sample.get('sample_id', '')).strip():
        raise ValueError('sample_id_required')
    out = dict(sample_id=sample['sample_id'], prediction_status=sample.get('prediction_status', 'UNVERIFIED'),
               metrics={k: result() for k in METRICS})
    m = out['metrics']
    if sample.get('prediction_status') != 'OK':
        reason = sample.get('failure_reason') or 'prediction_not_OK'
        out['metrics'] = {k: result(reason=reason) for k in METRICS}
        return out
    if sample.get('prediction_uses_gt_alignment') is not False:
        reason = ('GT_alignment_forbidden' if sample.get('prediction_uses_gt_alignment') is True
                  else 'prediction_alignment_provenance_missing')
        out['metrics'] = {k: result(reason=reason) for k in METRICS}
        return out
    pred = sample.get('prediction') or {}
    unit = pred.get('length_unit')
    unit = unit if unit and unit != 'unknown' else None
    parsed = {}
    for key, parse in [('rotation', rotation), ('translation', vector), ('scale', number)]:
        try:
            parsed[key] = parse(pred[key])
            if key == 'scale' and parsed[key] <= 0:
                raise ValueError('nonpositive_scale')
        except (KeyError, TypeError, ValueError, OverflowError) as error:
            parsed[key] = None
            out.setdefault('invalid_prediction', {})[key] = type(error).__name__
    if parsed['translation'] is not None:
        m['translation_norm'] = result(norm(parsed['translation']), 'OK', 'raw_prediction', unit or 'unknown')
    if parsed['scale'] is not None:
        m['pose_scale'] = result(parsed['scale'], 'OK', 'raw_prediction', (unit or 'unknown') + '/canonical_unit')
    gt = sample.get('gt')
    if not gt:
        for key in METRICS:
            if m[key]['status'] != 'OK':
                m[key] = result(status='NOT_APPLICABLE', reason='independent_GT_not_available')
        return out
    if gt.get('verified') is not True or not gt.get('provenance'):
        reason = 'GT_provenance_unverified'
    elif not pred.get('canonical_id') or pred.get('canonical_id') != gt.get('canonical_id'):
        reason = 'common_canonical_axes_origin_normalization_unverified'
    elif not pred.get('target_frame') or pred.get('target_frame') != gt.get('target_frame'):
        reason = 'common_target_frame_unverified'
    else:
        reason = None
    if reason:
        for key in METRICS:
            if m[key]['status'] != 'OK':
                m[key] = result(reason=reason)
        return out
    # Both rotations must be proper SO(3). Reflections are never repaired here.
    try:
        gr = rotation(gt['rotation'])
        pr = parsed['rotation']
        if pr is None:
            raise ValueError('prediction_rotation_invalid')
        trace = sum(pr[i][j]*gr[i][j] for i in range(3) for j in range(3))
        m['rotation_error_deg'] = result(angle((trace-1)/2), 'OK', 'raw_no_alignment', 'deg')
    except (KeyError, TypeError, ValueError, OverflowError):
        m['rotation_error_deg'] = result(reason='invalid_or_missing_proper_rotation')
    if not unit or unit != gt.get('length_unit'):
        for key in METRICS:
            if m[key]['status'] != 'OK' and key != 'rotation_error_deg':
                m[key] = result(reason='common_length_unit_unverified')
        return out
    try:
        pt, gt_t = parsed['translation'], vector(gt['translation'])
        if pt is None:
            raise ValueError('prediction_translation_invalid')
        pn, gn = norm(pt), norm(gt_t)
        error = norm([a-b for a, b in zip(pt, gt_t)])
        m['translation_norm_gt'] = result(gn, 'OK', 'verified_GT', unit)
        m['translation_error'] = result(error, 'OK', 'raw_no_alignment', unit)
        m['translation_norm_abs_error'] = result(abs(pn-gn), 'OK', 'raw_no_alignment', unit)
        if unit == 'm' and gt.get('metric_unit_verified') is True:
            m['translation_error_m'] = result(error, 'OK', 'verified_metric_unit', 'm')
        else:
            m['translation_error_m'] = result(status='NOT_APPLICABLE', reason='physical_metre_not_verified', unit='m')
        m['translation_norm_ratio'] = (result(pn/gn, 'OK', 'raw_no_alignment', 'ratio') if gn > 0
            else result(status='NOT_APPLICABLE', reason='zero_GT_translation_norm'))
        m['translation_direction_error_deg'] = (result(angle(sum(a*b for a, b in zip(pt, gt_t))/(pn*gn)),
            'OK', 'raw_no_alignment', 'deg') if pn > 0 and gn > 0 else
            result(status='NOT_APPLICABLE', reason='zero_translation_direction_undefined'))
    except (KeyError, TypeError, ValueError, OverflowError):
        for key in ('translation_error', 'translation_error_m', 'translation_norm_gt',
                    'translation_norm_ratio', 'translation_norm_abs_error', 'translation_direction_error_deg'):
            m[key] = result(reason='invalid_or_missing_translation')
    try:
        ps, gs = parsed['scale'], number(gt['scale'])
        if ps is None or gs <= 0:
            raise ValueError('invalid_scale')
        m['pose_scale_gt'] = result(gs, 'OK', 'verified_GT', unit+'/canonical_unit')
        m['scale_abs_error'] = result(abs(ps-gs), 'OK', 'raw_no_alignment', unit+'/canonical_unit')
        m['scale_relative_error'] = result(abs(ps-gs)/gs, 'OK', 'raw_no_alignment', 'ratio')
    except (KeyError, TypeError, ValueError, OverflowError):
        for key in ('pose_scale_gt', 'scale_abs_error', 'scale_relative_error'):
            m[key] = result(reason='invalid_or_missing_positive_scale')
    return out


def summarize(samples):
    """Keep all expected samples in coverage denominator; never zero-fill errors."""
    samples = list(samples)
    ids = [s['sample_id'] for s in samples]
    if len(set(ids)) != len(ids):
        raise ValueError('duplicate_sample_id')
    count = len(samples)
    out = dict(num_expected=count, num_prediction_ok=sum(s['prediction_status'] == 'OK' for s in samples), metrics={})
    for key in METRICS:
        items = [s['metrics'][key] for s in samples]
        valid = [x for x in items if x['status'] == 'OK']
        units = {x['unit'] for x in valid}
        mixed = len(units) > 1
        values = [x['value'] for x in valid]
        out['metrics'][key] = dict(
            status='UNVERIFIED' if mixed or not values else 'OK',
            reason='mixed_units_no_aggregation' if mixed else ('no_eligible_samples' if not values else 'eligible_subset_mean'),
            mean=None if mixed or not values else sum(values)/len(values),
            unit=next(iter(units)) if len(units) == 1 else None,
            num_valid=len(valid), num_expected=count,
            coverage=len(valid)/count if count else None,
            statuses=dict(Counter(x['status'] for x in items)),
            reasons=dict(Counter(x['reason'] for x in items if x['status'] != 'OK')))
    return out


def from_v1_result(receipt, sample_id, gt=None, canonical_id=None):
    """Adapter for run_stereo_cupid.py result.json, without changing frozen V1.

    V1's raw similarity comes from stereo points, not GT alignment. Its generic
    'cupid_canonical' label does NOT establish compatibility with a GT canonical.
    canonical_id may only be supplied after an independent coordinate audit.
    """
    fit = receipt.get('similarity')
    valid = bool(fit) and receipt.get('geometry_status') == 'OK'
    prediction = dict(fit or {})
    prediction.update(canonical_id=canonical_id, length_unit=receipt.get('length_unit'))
    return dict(sample_id=sample_id, prediction_status='OK' if valid else 'FAILED',
                failure_reason=receipt.get('geometry_status', receipt.get('status', 'result_missing')),
                prediction_uses_gt_alignment=False, prediction=prediction, gt=gt)
