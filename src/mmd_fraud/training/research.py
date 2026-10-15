"""Aggregate-only research evidence and paired chronological block uncertainty."""
import json
from pathlib import Path

import numpy as np
from sklearn.metrics import average_precision_score

from .baselines import evaluate

METRICS = ('pr_auc_average_precision', 'f1', 'recall', 'false_positive_rate')


def paired_intervals(y, steps, baseline, score, baseline_threshold, threshold, repeats=500):
    """Percentile CIs for paired differences; source step is the resampling unit."""
    rng = np.random.default_rng(0)
    units = np.unique(steps)
    blocks = [np.flatnonzero(steps == t) for t in units]
    differences = {name: [] for name in METRICS}
    for _ in range(repeats):
        idx = np.concatenate([blocks[i] for i in rng.integers(0, len(blocks), len(blocks))])
        if len(np.unique(y[idx])) < 2:
            continue
        a, b = evaluate(y[idx], baseline[idx], baseline_threshold), evaluate(y[idx], score[idx], threshold)
        for name in METRICS:
            differences[name].append(b[name] - a[name])
    if not differences[METRICS[0]]:
        raise ValueError('no valid two-class bootstrap resamples')
    return {name: {'lower_95': float(np.quantile(values, .025)),
                   'upper_95': float(np.quantile(values, .975)), 'valid_resamples': len(values)}
            for name, values in differences.items()}


def research_report(directory: Path, audit: dict):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    result = json.loads((directory / 'comparison.json').read_text())
    baseline = np.load(directory / 'transaction_only-private-scores.npz')
    y, steps, original = baseline['y'], baseline['step'], baseline['score']
    baseline_threshold = result['families']['transaction_only']['threshold']
    result['audit'] = audit
    result['paired_step_bootstrap'] = {}
    result['per_step'] = {}
    for family, item in result['families'].items():
        current = np.load(directory / f'{family}-private-scores.npz')
        if not np.array_equal(y, current['y']) or not np.array_equal(steps, current['step']):
            raise ValueError('paired evaluation populations differ')
        score = current['score']
        result['per_step'][family] = [{'step': int(t), 'rows': int((steps == t).sum()),
            'average_precision': float(average_precision_score(y[steps == t], score[steps == t]))
            if len(np.unique(y[steps == t])) == 2 else None} for t in np.unique(steps)]
        if family != 'transaction_only':
            result['paired_step_bootstrap'][family] = paired_intervals(
                y, steps, original, score, baseline_threshold, item['threshold'])
    lines = ['# Phase 4: reproducible Elliptic research evaluation', '',
        'Offline completed-step evaluation. Train 1–34, validation 35–39, test 40–49.',
        'The transaction-only unweighted histogram booster is frozen from PR #11.',
        'Five fixed candidates for each other ablation; validation AP selects each winner.',
        'Thresholds maximize validation F1 under 5% validation FPR; no test guarantee.', '',
        '| Family | Candidate | Validation AP | Test AP | F1 | Recall | FPR |',
        '| --- | --- | ---: | ---: | ---: | ---: | ---: |']
    for family, item in result['families'].items():
        lines.append(f"| {family} | {item['candidate']} | {item['validation']['pr_auc_average_precision']:.6f} | " +
                     ' | '.join(f"{item['test'][k]:.6f}" for k in METRICS) + ' |')
    lines += ['', '## Paired uncertainty', '',
        '500 seeded paired source-step bootstrap draws; 95% percentile intervals on model minus',
        'baseline. Only ten test steps: exploratory uncertainty, no independent lockbox, no',
        'multiple-comparison correction or confirmatory significance claim. FPR improvement is negative.', '',
        '| Family | AP difference 95% CI | F1 difference 95% CI |',
        '| --- | --- | --- |']
    for family, values in result['paired_step_bootstrap'].items():
        lines.append(f'| {family} | ' + ' | '.join(
            f"[{values[k]['lower_95']:.6f}, {values[k]['upper_95']:.6f}]" for k in METRICS[:2]) + ' |')
    lines += ['', '## Audit and interpretation', '',
        f"Cross-step edges: {audit['cross_step_edges']}; backward-time edges: {audit['backward_time_edges']}; "
        f"nodes with historically known neighbor labels: {audit['historical_label_feature_nonzero']}.",
        'If historical labels are unavailable these features remain zero, rather than substituting unknowns',
        'or validation/test labels. Label availability before the next source step is an explicit assumption.',
        'Forward and reverse PageRank use 30 fixed iterations, damping 0.85, dangling redistribution.',
        'Weak components and eight-sweep deterministic majority-vote communities describe the visible prefix.',
        'Community IDs are never predictors. Partitions are heuristics, not claimed optimal communities.',
        'Rolling means/std/anomaly scores use five strictly prior source steps, not wallet histories.',
        'No persistent wallet IDs exist. Source-local feature timing/normalization remains unverified.',
        'Unknown labels are excluded from supervision; all nodes provide unlabeled structural context.',
        'Prior test results have already been inspected. This fixed round is exploratory and offline.', '',
        'Feature train/test moments, zero fractions, all 49 prefix timings, per-step AP, fit warnings,',
        'validation trial logs and hashes are in the accompanying aggregate JSON.', '',
        '![Held-out metrics](research-results.png)', '',
        '## Prefix scalability benchmark', '',
        '| Completed step | Visible nodes | Visible edges | Mining seconds |',
        '| --- | ---: | ---: | ---: |']
    for row in audit['snapshot_benchmarks']:
        if row['step'] in (1, 10, 20, 30, 40, 49):
            lines.append(f"| {row['step']} | {row['visible_nodes']} | {row['visible_edges']} | {row['seconds']:.4f} |")
    lines += ['', 'Prefix timings are observations on this runner, not controlled scaling estimates.',
              'No improvement is established by choosing the largest test score after the run.']
    (directory / 'research-report.md').write_text('\n'.join(lines) + '\n')
    (directory / 'research.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    plt.rcParams.update({'font.size': 9})
    fig, axes = plt.subplots(2, 2, figsize=(12, 9), layout='constrained')
    names = list(result['families'])
    for ax, metric in zip(axes.flat, METRICS):
        ax.barh(names, [result['families'][n]['test'][metric] for n in names], color='#28688d')
        ax.axvline(result['families']['transaction_only']['test'][metric], color='#b33a3a',
                   linestyle='--', label='Preserved baseline')
        ax.set_title(metric.replace('_', ' '))
        ax.set_xlim(left=0)
        ax.grid(axis='x', alpha=.2)
    fig.suptitle('Elliptic held-out steps 40–49 • validation-selected models and thresholds')
    fig.savefig(directory / 'research-results.png', dpi=170)
    plt.close(fig)
    return result
