"""Verify the release and reproduce the manuscript's core numerical results."""
import csv
import hashlib
import io
import json
import math
from contextlib import redirect_stdout
from pathlib import Path

import analyze

HERE = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path: Path) -> list[dict]:
    with path.open(newline='') as stream:
        return list(csv.DictReader(stream))


def control_decision(states: list[dict], policy: str) -> tuple[int, int]:
    standard = {'last3': ('full', 'last'), 'best3': ('full', 'earliest'),
                'pass_current': ('pass', 'last'), 'pass_best': ('pass', 'earliest'),
                'unchanged2': ('unchanged2', 'earliest')}
    if policy in standard:
        return analyze.decision(states, 3, *standard[policy])
    assert policy in ('unchanged1', 'invalid1', 'invalid2')
    end, unchanged, invalid = 3, 0, 0
    for i, state in enumerate(states[:4]):
        if i:
            unchanged = unchanged + 1 if state['hash'] == states[i-1]['hash'] else 0
            invalid = invalid + 1 if not state['valid'] else 0
        if (state['score'] == 2 or (policy == 'unchanged1' and unchanged >= 1)
                or (policy.startswith('invalid') and invalid >= int(policy[-1]))):
            end = i
            break
    return end, max(range(end+1), key=lambda i: states[i]['score'])


def table2(groups: dict) -> list[dict]:
    result = []
    for reference in rows(HERE / 'reference/controls.csv'):
        runs = {k:v for k,v in groups.items() if k[0] == reference['cohort']}
        successes, tokens, calls = 0, 0, 0
        for states in runs.values():
            end, selected = control_decision(states, reference['policy'])
            successes += states[selected]['success']
            tokens += sum(s['tokens'] for s in states[:end+1])
            calls += end+1
        row = dict(cohort=reference['cohort'], policy=reference['policy'],
                   tasks=len({k[1] for k in runs}), runs=len(runs), successes=successes,
                   mean_tokens=tokens/len(runs), mean_calls=calls/len(runs))
        for field in ('tasks', 'runs', 'successes', 'mean_tokens', 'mean_calls'):
            assert math.isclose(row[field], float(reference[field]), rel_tol=0, abs_tol=1e-10), (field, row)
        result.append(row)
    analyze.write_csv('table2_controls.csv', result)
    return result


def fresh_tables() -> None:
    budget = rows(analyze.OUT / 'budget_summary.csv')
    table3 = []
    for cohort in ('exact', 'aider_match'):
        choices = [('Initial generation', 0, 'full', 'last'),
                   ('Full budget, last version', 6, 'full', 'last'),
                   ('Full budget, earliest highest score', 6, 'full', 'earliest'),
                   ('Full budget, latest highest score', 6, 'full', 'latest'),
                   ('Stop on pass, current version', 6, 'pass', 'last'),
                   ('Stop on pass, earliest highest score', 6, 'pass', 'earliest'),
                   ('Pass or two unchanged revisions', 6, 'unchanged2', 'earliest')]
        for name, limit, stop, selector in choices:
            r = next(r for r in budget if (r['cohort'], int(r['budget']), r['stopping'], r['selector'])
                     == (cohort, limit, stop, selector))
            table3.append(dict(cohort=cohort, rule=name, runs=r['runs'],
                               successes=r['successes'], mean_tokens=r['mean_tokens']))
    analyze.write_csv('table3_fresh.csv', table3)
    losses = rows(analyze.OUT / 'loss_summary.csv')
    table4 = [r for r in losses if r['cohort'] in ('exact', 'aider_match') and
              (r['stopping'], r['selector']) in (('full','earliest'), ('full','latest'),
                                                ('pass','earliest'), ('unchanged2','earliest'))]
    analyze.write_csv('table4_losses.csv', table4)
    table5 = [r for r in budget if r['cohort'] in ('exact', 'aider_match') and r['stopping'] == 'full']
    analyze.write_csv('table5_budgets.csv', table5)


def figure4(groups: dict) -> dict:
    data = []
    for reference in rows(HERE / 'reference/figure4_versions.csv'):
        key = reference['protocol'], reference['task'], int(reference['repeat'])
        state = groups[key][int(reference['step'])]
        row = {k:reference[k] for k in ('panel', 'protocol', 'task', 'repeat', 'step')}
        for field, column in (('hash','hash'), ('score','score'), ('success','success'),
                              ('complete','audit_complete'), ('valid','valid'), ('changed','changed'),
                              ('matcher_fallback_used','matcher_fallback_used'), ('tokens','tokens')):
            value = state[field]
            if column in ('success', 'audit_complete', 'valid', 'changed', 'matcher_fallback_used'):
                value = bool(value)
            assert str(value) == reference[column], (key, column)
            row[column] = value
        data.append(row)
    decisions = []
    policies = {'pass_best':('pass','earliest'), 'best6':('full','earliest'),
                'latest6':('full','latest'), 'unchanged2':('unchanged2','earliest')}
    for reference in rows(HERE / 'reference/figure4_decisions.csv'):
        key = reference['protocol'], reference['task'], int(reference['repeat'])
        end, selected = analyze.decision(groups[key], 6, *policies[reference['policy']])
        assert (end, selected) == (int(reference['stop']), int(reference['selected_step']))
        decisions.append({**reference, 'stop':end, 'selected_step':selected})
    analyze.write_csv('figure4_versions.csv', data)
    analyze.write_csv('figure4_decisions.csv', decisions)
    return dict(versions=len(data), decisions=len(decisions))


def main() -> None:
    manifest = json.loads((HERE / 'MANIFEST.json').read_text())
    for name, expected in manifest['files'].items():
        assert sha(HERE / name) == expected, f'Release file changed: {name}'
    captured = io.StringIO()
    with redirect_stdout(captured):
        analyze.main()
    expected = json.loads((HERE / 'reference/output_hashes.json').read_text())
    for name, digest in expected.items():
        assert sha(analyze.OUT / name) == digest, f'Analysis differs from manuscript: {name}'
    groups = analyze.load()
    controls = table2(groups)
    fresh_tables()
    trajectories = figure4(groups)
    report = dict(status='passed', release_files_verified=len(manifest['files']),
        analysis=json.loads(captured.getvalue()), original_analysis_outputs_matched=len(expected),
        table2_rows_verified=len(controls), figure4=trajectories,
        scope='Numerical replay of normalized observations; raw-log audit and model/test execution are separate',
        new_model_calls=0)
    (analyze.OUT / 'verification.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
