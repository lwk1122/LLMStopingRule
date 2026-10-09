"""Offline budget/tie replay and joint loss bounds from compact observations.

The analysis is retained from the manuscript's archived replay script.
Only input loading and output locations are adapted for this release.
"""
import csv
import hashlib
import itertools
import json
import random
import statistics
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / 'results'


def classify(success: int, complete: bool, required_failures: int) -> str:
    if success:
        assert complete and required_failures == 0
        return 'pass'
    if complete or required_failures:
        return 'observed_nonpass'
    return 'undetermined'


def load(path: Path = HERE / 'data/versions.csv') -> dict:
    groups = defaultdict(list)
    with path.open(newline='') as stream:
        rows = list(csv.DictReader(stream))
    for row in rows:
        integers = ('step', 'score', 'success', 'tokens', 'prompt_tokens', 'completion_tokens',
                    'required_failures', 'ordinary_pass', 'issue_pass')
        state = {k:int(row[k]) for k in integers}
        for field in ('complete', 'valid', 'changed', 'matcher_fallback_used'):
            assert row[field] in ('0', '1'), (field, row[field])
            state[field] = row[field] == '1'
        assert state['success'] in (0, 1)
        assert state['ordinary_pass'] in (0, 1) and state['issue_pass'] in (0, 1)
        assert state['score'] == state['ordinary_pass'] + state['issue_pass']
        assert state['tokens'] == state['prompt_tokens'] + state['completion_tokens']
        status = classify(state['success'], state['complete'], state['required_failures'])
        assert status == row['status']
        state.update(hash=row['hash'], repo=row['repo'], status=status, grade=row['grade'])
        key = (row['cohort'], row['task'], int(row['repeat']))
        groups[key].append(state)
    return {k: sorted(v, key=lambda s:s['step']) for k,v in groups.items()}


def decision(states: list[dict], budget: int, stopping: str, selector: str) -> tuple[int, int]:
    assert 0 <= budget < len(states)
    assert stopping in ('full', 'pass', 'unchanged2')
    assert selector in ('earliest', 'latest', 'last')
    end, unchanged = budget, 0
    for i in range(budget + 1):
        if i:
            unchanged = unchanged + 1 if states[i]['hash'] == states[i-1]['hash'] else 0
        if stopping != 'full' and (states[i]['score'] == 2 or (stopping == 'unchanged2' and unchanged >= 2)):
            end = i
            break
    if selector == 'last':
        selected = end
    else:
        selected = max(range(end+1), key=lambda i:(states[i]['score'], i if selector == 'latest' else -i))
    return end, selected


def diagnostics(states: list[dict], end: int, selected: int, assignment: dict | None = None) -> tuple:
    assignment = assignment or {}
    y = [assignment.get(s['hash'], s['success']) for s in states]
    whole, prefix, returned = max(y), max(y[:end+1]), y[selected]
    assert whole >= prefix >= returned
    return (whole, prefix, returned, whole-prefix, prefix-returned)


def loss_bounds(runs: dict, stopping: str, selector: str) -> tuple[list, list]:
    # Enumerate each task's unknown patches jointly across repeated appearances.
    bytask = defaultdict(list)
    for key, states in runs.items():
        bytask[key[1]].append(states)
    low, high = [0]*5, [0]*5
    for task_runs in bytask.values():
        unknown = sorted({s['hash'] for ss in task_runs for s in ss if s['status']=='undetermined'})
        assert len(unknown) <= 16
        values = []
        for bits in itertools.product((0,1), repeat=len(unknown)):
            assignment = dict(zip(unknown, bits))
            rows = [diagnostics(ss, *decision(ss,len(ss)-1,stopping,selector), assignment) for ss in task_runs]
            values.append([sum(r[i] for r in rows) for i in range(5)])
        for i in range(5):
            low[i] += min(v[i] for v in values)
            high[i] += max(v[i] for v in values)
    return low, high


def write_csv(name: str, rows: list[dict]) -> None:
    with (OUT/name).open('w', newline='') as f:
        writer=csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def main() -> None:
    OUT.mkdir(exist_ok=True)
    observed = load()
    old = {k:v for k,v in observed.items() if k[0] in ('Round9', 'Round7b')}
    fresh = {k:v for k,v in observed.items() if k[0] in ('exact', 'aider_match')}
    extra = {k:v for k,v in observed.items() if k[0] == 'Extension'}
    extension = {('Extension',k[1],k[2]):old[('Round9',k[1],k[2])]+v for k,v in extra.items()}
    groups = {**old, **fresh, **extension}
    assert len(old)==126 and len(fresh)==54 and len(extension)==10
    assert all([s['step'] for s in v]==list(range(len(v))) for v in groups.values())
    ledger = {}
    for key, states in groups.items():
        for s in states:
            identity=(key[1],s['hash'])
            entry=dict(task=key[1],hash=s['hash'],status=s['status'],
                original_success=s['success'],complete=s['complete'],
                required_failures=s['required_failures'],grade=s['grade'])
            if identity in ledger:
                assert ledger[identity]['status']==entry['status']
            ledger[identity]=entry
    write_csv('outcome_audit.csv',list(ledger.values()))
    policies=list(itertools.product(('full','pass','unchanged2'),('earliest','latest','last')))
    outcomes, summaries, losses, pair_rows=[],[],[],[]
    fields=['any_full','any_before_stop','returned','missed_after_stop','missed_by_selection']
    for cohort in ('Round9','Round7b','exact','aider_match','Extension'):
        runs={k:v for k,v in groups.items() if k[0]==cohort}
        horizon=len(next(iter(runs.values())))-1
        for h in range(horizon+1):
            for stopping,selector in policies:
                points=[]
                for key,states in runs.items():
                    end,k=decision(states,h,stopping,selector)
                    row=dict(cohort=cohort,task=key[1],repeat=key[2],budget=h,
                        stopping=stopping,selector=selector,stop=end,selected_step=k,
                        selected_hash=states[k]['hash'],success=states[k]['success'],
                        complete=states[k]['complete'],status=states[k]['status'],
                        tokens=sum(s['tokens'] for s in states[:end+1]))
                    outcomes.append(row);points.append(row)
                summaries.append(dict(cohort=cohort,budget=h,stopping=stopping,selector=selector,
                    tasks=len({k[1] for k in runs}),runs=len(runs),successes=sum(r['success'] for r in points),
                    mean_tokens=sum(r['tokens'] for r in points)/len(points),
                    incomplete=sum(not r['complete'] for r in points)))
        for stopping,selector in policies:
            values=[diagnostics(ss,*decision(ss,horizon,stopping,selector)) for ss in runs.values()]
            low,high=loss_bounds(runs,stopping,selector)
            row=dict(cohort=cohort,budget=horizon,stopping=stopping,selector=selector,runs=len(runs))
            for i,name in enumerate(fields):
                row[name]=sum(v[i] for v in values)
                row[name+'_low']=low[i]; row[name+'_high']=high[i]
            losses.append(row)
        comparisons=[('latest_vs_earliest',('full','latest'),('full','earliest')),
                     ('last_vs_pass_current',('full','last'),('pass','last')),
                     ('unchanged_vs_pass',('unchanged2','earliest'),('pass','earliest'))]
        for name,a,b in comparisons:
            for key,states in runs.items():
                ia=decision(states,horizon,*a)[1];ib=decision(states,horizon,*b)[1]
                pair_rows.append(dict(cohort=cohort,comparison=name,task=key[1],repeat=key[2],
                    selected_a=ia,selected_b=ib,success_a=states[ia]['success'],success_b=states[ib]['success'],
                    difference=states[ia]['success']-states[ib]['success'],
                    same_patch=states[ia]['hash']==states[ib]['hash']))
    write_csv('policy_outcomes.csv',outcomes);write_csv('budget_summary.csv',summaries)
    write_csv('loss_summary.csv',losses);write_csv('paired_changes.csv',pair_rows)
    task_effects, intervals = [], []
    for cohort in ('exact','aider_match'):
        bytask=defaultdict(list)
        for r in pair_rows:
            if r['cohort']==cohort and r['comparison']=='latest_vs_earliest':
                bytask[r['task']].append(r['difference'])
        byrepo=defaultdict(list)
        for task,values in sorted(bytask.items()):
            effect=statistics.mean(values)
            repo=groups[(cohort,task,0)][0]['repo']
            byrepo[repo].append(effect)
            task_effects.append(dict(cohort=cohort,task=task,repo=repo,difference=effect))
        rng=random.Random(2026100901)
        draws=[statistics.mean([v for group in byrepo.values() for v in rng.choices(group,k=len(group))])
               for _ in range(10000)]
        q=statistics.quantiles(draws,n=40,method='inclusive')
        effects=[statistics.mean(v) for v in bytask.values()]
        intervals.append(dict(cohort=cohort,tasks=len(effects),mean_pp=100*statistics.mean(effects),
            task_sd_pp=100*statistics.stdev(effects),descriptive_low_pp=100*q[0],descriptive_high_pp=100*q[-1]))
    write_csv('tie_task_effects.csv',task_effects)
    write_csv('tie_intervals.csv',intervals)
    audit_counts={}
    for cohort in ('Round9','Round7b','exact','aider_match','Extension'):
        ss=[s for k,v in groups.items() if k[0]==cohort for s in v]
        unique={(k[1],s['hash']):s for k,v in groups.items() if k[0]==cohort for s in v}
        audit_counts[cohort]={'versions':len(ss),'incomplete_versions':sum(not s['complete'] for s in ss),
            'incomplete_distinct':dict(Counter(s['status'] for s in unique.values() if not s['complete']))}
    (OUT/'audit_summary.json').write_text(json.dumps(audit_counts,indent=2)+'\n', encoding='utf-8', newline='\n')
    hashes = {'data/versions.csv': hashlib.sha256((HERE/'data/versions.csv').read_bytes()).hexdigest()}
    (OUT/'input_hashes.json').write_text(json.dumps(hashes,indent=2)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps({'runs_by_cohort':dict(Counter(k[0] for k in groups)),
        'archived_versions_read':sum(len(v) for v in old.values())+sum(len(v) for v in fresh.values())+sum(len(v) for v in extra.values()),
        'replayed_policy_rows':len(outcomes),'new_model_calls':0,'outcome_audit':audit_counts},indent=2))


if __name__=='__main__':
    main()
