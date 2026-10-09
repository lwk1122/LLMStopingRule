"""Small behavioral tests independent of the manuscript's expected totals."""
import copy
import unittest

import analyze
from reproduce import control_decision
from editing.exact import apply_edits, source
from editing.matching import apply_with_fallback


def state(code: str, score: int, success: int, status: str | None = None, valid: bool = True) -> dict:
    return dict(hash=code, score=score, success=success, valid=valid,
                status=status or ('pass' if success else 'observed_nonpass'))


def edit(old: str, new: str) -> dict:
    return {'action':'edit', 'replacements':[{'old_text':old, 'new_text':new}]}


class ReplayTests(unittest.TestCase):
    def test_early_pass_and_later_repair(self):
        states = [state('a', 2, 0), state('b', 2, 1)]
        self.assertEqual(analyze.decision(states, 1, 'pass', 'latest'), (0, 0))
        self.assertEqual(analyze.decision(states, 1, 'full', 'earliest'), (1, 0))
        self.assertEqual(analyze.decision(states, 1, 'full', 'latest'), (1, 1))
        self.assertEqual(analyze.diagnostics(states, 0, 0), (1, 0, 0, 1, 0))
        self.assertEqual(analyze.diagnostics(states, 1, 0), (1, 1, 0, 0, 1))

    def test_revision_counter_excludes_initial_generation(self):
        states = [state('a', 1, 0)]*3 + [state('b', 2, 1)]
        self.assertEqual(analyze.decision(states, 3, 'unchanged2', 'earliest'), (2, 0))
        self.assertEqual(analyze.decision(states, 3, 'pass', 'earliest'), (3, 3))

    def test_no_change_counter_resets(self):
        states = [state('a',1,0),state('a',1,0),state('b',1,0),state('b',1,0)]
        self.assertEqual(analyze.decision(states, 3, 'unchanged2', 'last'), (3, 3))

    def test_independent_quality_cannot_change_decisions(self):
        states = [state('a',1,0),state('b',2,0),state('c',2,1)]
        changed = [{**s,'success':1-s['success']} for s in states]
        for stop in ('full','pass','unchanged2'):
            for selector in ('last','earliest','latest'):
                self.assertEqual(analyze.decision(states,2,stop,selector),
                                 analyze.decision(changed,2,stop,selector))

    def test_shared_unknown_outcomes(self):
        states = [state('a',1,0,'undetermined')]*3
        runs = {('set','task',0):states, ('set','task',1):states}
        self.assertEqual(analyze.loss_bounds(runs,'full','earliest'),
                         ([0,0,0,0,0], [2,2,2,0,0]))

    def test_audit_distinguishes_incomplete_from_unknown(self):
        self.assertEqual(analyze.classify(1,True,0), 'pass')
        self.assertEqual(analyze.classify(0,False,1), 'observed_nonpass')
        self.assertEqual(analyze.classify(0,False,0), 'undetermined')
        with self.assertRaises(AssertionError):
            analyze.classify(1,False,0)

    def test_valid_keep_resets_invalid_counter(self):
        states = [state('a',1,0,valid=False),state('a',1,0,valid=False),
                  state('a',1,0,valid=True),state('a',1,0,valid=False)]
        self.assertEqual(control_decision(states,'invalid1')[0], 1)
        self.assertEqual(control_decision(states,'invalid2')[0], 3)
        self.assertEqual(control_decision(states,'unchanged1')[0], 1)
        self.assertEqual(control_decision(states,'unchanged2')[0], 2)

    def test_bad_policy_rejected(self):
        with self.assertRaises(AssertionError):
            analyze.decision([state('a',1,0)],0,'typo','earliest')


class EditorTests(unittest.TestCase):
    def test_exact_path_is_unchanged(self):
        parts = [{'editable':True,'text':'x = 1\n'}]
        self.assertEqual(apply_with_fallback(parts,edit('1','2')),apply_edits(parts,edit('1','2')))

    def test_matching_fallback(self):
        parts = [{'editable':True,'text':'def f():\n    x = 1\n    return x\n'}]
        args = edit('x = 1\nreturn x\n','x = 2\nreturn x\n')
        with self.assertRaises(ValueError):
            apply_edits(parts,args)
        self.assertIn('    x = 2\n    return x',source(apply_with_fallback(parts,args)))

    def test_protected_region_and_ambiguous_match(self):
        parts = [{'editable':False,'text':'x = 1\n'},{'editable':True,'text':'y = 2\n'}]
        with self.assertRaises(ValueError):
            apply_with_fallback(parts,edit('x = 1\n','x = 3\n'))
        with self.assertRaises(ValueError):
            apply_with_fallback(parts*2,edit('y = 2\n','y = 3\n'))

    def test_syntax_failure_is_atomic(self):
        parts = [{'editable':True,'text':'x = 1\n'}]
        before = copy.deepcopy(parts)
        with self.assertRaises(SyntaxError):
            apply_with_fallback(parts,edit('1','('))
        self.assertEqual(parts,before)
        self.assertEqual(apply_with_fallback(parts,{'action':'keep','replacements':[]}),parts)

    def test_multiple_replacements_are_atomic(self):
        parts = [{'editable':True,'text':'x = 1\n'}]
        args = edit('1','2')
        args['replacements'].append({'old_text':'absent','new_text':'3'})
        with self.assertRaises(ValueError):
            apply_edits(parts,args)
        self.assertEqual(source(parts),'x = 1\n')


if __name__ == '__main__':
    unittest.main()
