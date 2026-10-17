"""Values shown in the landing page's small charts. Both come from platform code or a file it generated, never typed in.

- The concentration curve is read from app/data/landing_example_curve_v1.json (scripts/landing_example_curve.py).
- The kidney split is computed live from the Simulation 2.0a pathway model (intact-nephron reading).
"""
import json
from pathlib import Path

CURVE_PATH = Path(__file__).resolve().parent.parent / 'app' / 'data' / 'landing_example_curve_v1.json'
KIDNEY_EXAMPLES = ((110.0, 'Normal kidney function'), (40.0, 'Moderate impairment'))


def curve_example(width=320, height=150, left=40, top=12, bottom=28, right=10, y_max=500.0):
    data = json.loads(CURVE_PATH.read_text(encoding='utf-8'))
    points = data['points_time_h_concentration_ng_ml']
    horizon = data['request']['horizon_h']
    plot_w, plot_h = width - left - right, height - top - bottom

    def xy(t, c):
        return left + t / horizon * plot_w, top + (1 - c / y_max) * plot_h

    polyline = ' '.join('%.1f,%.1f' % xy(t, c) for t, c in points)
    peak_x, peak_y = xy(data['peak']['time_h'], data['peak']['concentration_ng_ml'])
    y_ticks = [{'y': round(xy(0, v)[1], 1), 'label': '%g' % v} for v in (0, 250, 500)]
    x_ticks = [{'x': round(xy(t, 0)[0], 1), 'label': '%g h' % t} for t in (0, 6, 12, 18, 24)]
    return dict(data=data, polyline=polyline, width=width, height=height, left=left, right=width - right,
                baseline=top + plot_h, peak_x=round(peak_x, 1), peak_y=round(peak_y, 1),
                y_ticks=y_ticks, x_ticks=x_ticks)


def kidney_example():
    from intelligence_store.lenalidomide_renal_pathways import EVIDENCE_SHA256, calibrate, load_evidence, pathways
    cal = calibrate(load_evidence(), 110.0, 0.77)
    rows = []
    for crcl, label in KIDNEY_EXAMPLES:
        p = pathways(cal, crcl, 'A_intact_nephron')
        total = p['total_ml_min']
        shares = [('Filtration', p['filtration_ml_min'] / total), ('Tubular secretion', p['secretion_ml_min'] / total),
                  ('Non-renal', p['non_renal_ml_min'] / total)]
        rows.append({'label': label, 'crcl': crcl, 'shares': [{'name': n, 'pct': round(100 * s)} for n, s in shares]})
    return {'rows': rows, 'evidence_sha256': EVIDENCE_SHA256}
