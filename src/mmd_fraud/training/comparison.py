"""Predeclared feature ablations, train-only weighting and validation-only tuning."""
import hashlib
import json
from pathlib import Path
import time
import warnings

import joblib
import numpy as np
import pyarrow.parquet as pq
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_curve
from sklearn.exceptions import ConvergenceWarning
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

from .baselines import chronological_split, evaluate
from .curves import pr_curve
from mmd_fraud.data.acquire import sha256
from mmd_fraud.spark.experiments import FAMILIES

# Fixed before real execution; no adaptive search on test metrics.
CANDIDATES = ('logistic_c01', 'logistic_c1', 'forest', 'hist_unweighted', 'hist_balanced')


def candidate(name, seed):
    if name.startswith('logistic_'):
        return make_pipeline(StandardScaler(), LogisticRegression(
            C=.1 if name == 'logistic_c01' else 1., class_weight='balanced',
            max_iter=1000, random_state=seed))
    if name == 'forest':
        return RandomForestClassifier(n_estimators=128, max_depth=12, min_samples_leaf=3,
                                      class_weight='balanced_subsample', n_jobs=2, random_state=seed)
    if name in ('hist_unweighted', 'hist_balanced'):
        return make_pipeline(StandardScaler(), HistGradientBoostingClassifier(
            max_iter=150, max_leaf_nodes=15, learning_rate=.08, l2_regularization=1.,
            class_weight='balanced' if name == 'hist_balanced' else None,
            early_stopping=False, random_state=seed))
    raise ValueError('candidate is outside the bounded grid')


def validation_threshold(y, score, fpr_cap=.05):
    # ROC thresholds enumerate every attainable predicted-positive set, including none.
    # Pick maximal validation F1 under the fixed FPR cap, then higher threshold on ties.
    if not 0 <= fpr_cap <= 1:
        raise ValueError('invalid validation FPR cap')
    evaluate(y, score)  # validate vocabulary, shape, finite values before threshold selection
    fpr, recall, thresholds = roc_curve(y, score, drop_intermediate=False)
    thresholds = np.where(np.isinf(thresholds), np.nextafter(1., 2.), thresholds)
    positive, negative = int(y.sum()), int((y == 0).sum())
    tp, fp, fn = recall * positive, fpr * negative, (1 - recall) * positive
    f1 = np.divide(2 * tp, 2 * tp + fp + fn, out=np.zeros_like(tp), where=(2 * tp + fp + fn) > 0)
    eligible = np.flatnonzero(fpr <= fpr_cap + 1e-12)
    best = max(eligible, key=lambda i: (f1[i], thresholds[i]))
    return float(thresholds[best])


def train_comparison(feature_path: Path, output: Path, cache: Path,
                     train_end=34, validation_end=39, seed=0, *, families=None,
                     preserve_baseline=False, export_scores=False, cutoff_offset=1,
                     source_policy="93 publisher-local numeric attributes; 72 neighbor aggregates excluded") -> dict:
    families = FAMILIES if families is None else families
    dataset = pq.ParquetDataset(feature_path)
    if sum(pq.read_metadata(p).num_rows for p in dataset.files) > 300000:
        raise ValueError('comparison exceeds bounded release row count')
    columns = list(dict.fromkeys(c for names in families.values() for c in names))
    table = dataset.read(columns=['entity_id', 'time_step', 'label', 'feature_cutoff_exclusive', *columns])
    # Use Arrow/NumPy arrays: no 203K x 123 dictionary materialization.
    metadata = table.select(['entity_id', 'time_step', 'label', 'feature_cutoff_exclusive']).to_pylist()
    splits = chronological_split(metadata, train_end, validation_end, cutoff_offset)
    order = sorted(range(len(metadata)), key=lambda i: (metadata[i]['time_step'], metadata[i]['entity_id']))
    positions = {name: np.array([i for i in order if metadata[i]['label'] != 'unknown' and
                 ('train' if metadata[i]['time_step'] <= train_end else
                  'validation' if metadata[i]['time_step'] <= validation_end else 'test') == name])
                 for name in ('train', 'validation', 'test')}
    y = {name: np.array([int(metadata[i]['label'] == '1') for i in idx]) for name, idx in positions.items()}
    features = {name: table[name].to_numpy(zero_copy_only=False).astype('float64') for name in columns}
    if not all(np.isfinite(values).all() for values in features.values()):
        raise ValueError('nonfinite comparison features')
    identity = {'inputs': {str(Path(p).name): sha256(Path(p)) for p in dataset.files},
                'families': families, 'preserve_baseline': preserve_baseline, 'candidates': CANDIDATES, 'seed': seed,
                'train_end': train_end, 'validation_end': validation_end,
                'cutoff_offset': cutoff_offset, 'source_policy': source_policy, 'code': sha256(Path(__file__))}
    key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    cache = cache / key
    cache.mkdir(parents=True, exist_ok=True)
    output.mkdir()
    result = {'train_end': train_end, 'validation_end': validation_end, 'seed': seed,
              'unknown_excluded': splits['unknown_excluded'],
              'split_counts': {name: {'rows': len(v), 'illicit': int(v.sum())} for name, v in y.items()},
              'threshold_policy': 'maximize validation F1 under validation FPR <= 0.05; no test tuning',
              'source_policy': source_policy, 'cutoff_offset': cutoff_offset,
              'families': {}, 'selected_family': None, 'search_identity': key}
    winners = {}
    with threadpool_limits(limits=2):
        for family, names in families.items():
            x = {name: np.column_stack([features[c][idx] for c in names]) for name, idx in positions.items()}
            trials = {}
            candidates = ('hist_unweighted',) if preserve_baseline and family == 'transaction_only' else CANDIDATES
            for label in candidates:
                checkpoint = cache / f'{family}-{label}'
                model_file = checkpoint.with_suffix('.joblib')
                record_file = checkpoint.with_suffix('.json')
                if record_file.exists():
                    record = json.loads(record_file.read_text())
                    if sha256(model_file) != record['model_sha256']:
                        raise ValueError('corrupt comparison trial checkpoint')
                    model = joblib.load(model_file)  # private run-owned verified checkpoint only
                    checked = evaluate(y['validation'], model.predict_proba(x['validation'])[:, 1])
                    if checked != record['validation']:
                        raise ValueError('corrupt comparison validation checkpoint')
                else:
                    began = time.monotonic()
                    model = candidate(label, seed)
                    with warnings.catch_warnings(record=True) as notices:
                        warnings.simplefilter('always', ConvergenceWarning)
                        model.fit(x['train'], y['train'])
                    if isinstance(model, RandomForestClassifier):
                        model.n_jobs = 1
                    score = model.predict_proba(x['validation'])[:, 1]
                    record = {'validation': evaluate(y['validation'], score),
                              'fit_seconds': time.monotonic() - began,
                              'fit_warnings': sorted({type(w.message).__name__ for w in notices})}
                    temporary = model_file.with_suffix('.tmp')
                    joblib.dump(model, temporary)
                    restored = joblib.load(temporary)
                    if not np.allclose(score, restored.predict_proba(x['validation'])[:, 1], rtol=1e-12, atol=1e-15):
                        raise ValueError('comparison model round-trip failed')
                    temporary.replace(model_file)
                    record['model_sha256'] = sha256(model_file)
                    pending = record_file.with_suffix('.json.tmp')
                    pending.write_text(json.dumps(record, indent=2) + '\n')
                    pending.replace(record_file)
                trials[label] = record
            chosen = max(candidates, key=lambda n: trials[n]['validation']['pr_auc_average_precision'])
            model_file = cache / f'{family}-{chosen}.joblib'
            model = joblib.load(model_file)
            score = model.predict_proba(x['validation'])[:, 1]
            threshold = validation_threshold(y['validation'], score)
            result['families'][family] = {'features': list(names), 'trials': trials, 'candidate': chosen,
                                         'threshold': threshold,
                                         'validation': evaluate(y['validation'], score, threshold),
                                         'validation_fixed': evaluate(y['validation'], score)}
            winners[family] = model
        # Freeze the global choice before any test prediction. All four predeclared
        # family winners are then evaluated for the requested comparison.
        result['selected_family'] = max(families, key=lambda n:
            result['families'][n]['validation']['pr_auc_average_precision'])
        (output / 'selection.json').write_text(json.dumps(result, indent=2) + '\n')
        for family, names in families.items():
            x_test = np.column_stack([features[c][positions['test']] for c in names])
            score = winners[family].predict_proba(x_test)[:, 1]
            item = result['families'][family]
            if export_scores:
                np.savez_compressed(output / f'{family}-private-scores.npz',
                                    score=score, y=y['test'],
                                    step=np.array([metadata[i]['time_step'] for i in positions['test']]))
            item['test_curve'] = pr_curve(y['test'], score)
            item['test'] = evaluate(y['test'], score, item['threshold'])
            item['test_fixed'] = evaluate(y['test'], score)
            joblib.dump(winners[family], output / f'{family}.joblib')
    (output / 'comparison.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    return result
