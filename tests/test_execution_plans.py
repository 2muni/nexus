"""Development semantic checks: offline data only, never dispatch authority."""
import copy
import json
from pathlib import Path
import runpy
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CHECKER = runpy.run_path(str(ROOT / 'scripts/check-plan.py'))
REF = 'a' * 40
OUTPUT = 'b' * 40


def task(tid='T1', repository='nexus', dependencies=(), write=False):
    return {'id': tid, 'title': 'Check observable outcome', 'type': 'implementation' if write else 'research',
            'complexity': 'low', 'risk': 'low', 'context_size': 'small', 'parallelizable': True,
            'repository': repository, 'dependencies': list(dependencies),
            'mutation_scope': {'mode': 'write' if write else 'read-only', 'targets': ['docs/' + tid + '.md'], 'do_not_touch': ['other repositories', 'main']},
            'base': {'source': 'initial', 'ref': REF}, 'acceptance': ['Expected observable checks pass'], 'architecture_sensitive': False,
            'routing': {'task_class': 'implementation-standard' if write else 'research', 'agent': 'codex',
                        'fallback_agent': 'opencode' if write else 'antigravity', 'model_profile': 'standard',
                        'effort': 'medium', 'reasons': ['Bounded scope with inherited uncertainty'],
                        'validation': {'required': False, 'independent_session': False, 'preferred_agent': 'antigravity'},
                        'resolution': {'status': 'inherit-with-uncertainty', 'model': None, 'effort': None}}}


def plan(*tasks, waves=None):
    tasks = list(tasks) or [task()]
    repos = list(dict.fromkeys(t['repository'] for t in tasks))
    return {'version': 1, 'objective': 'Check bounded plans before human review', 'mode': 'ORCHESTRATED',
            'repositories': repos, 'requirements': ['Preserve ownership and observable acceptance'],
            'baselines': {r: {'ref': REF, 'scope': 'committed snapshot', 'dirty_state': 'exclude and preserve inspected dirty changes'} for r in repos},
            'tasks': tasks, 'waves': waves or [{'id': 'W' + str(i), 'tasks': [t['id']]} for i, t in enumerate(tasks)],
            'final_gate': 'human-review-required'}


def completed(t, ref=OUTPUT):
    t['result'] = {'outcome': 'succeeded', 'ref': ref, 'evidence': ['immutable worker result receipt']}
    return t


def validation(t, profile='deep'):
    t['routing']['model_profile'] = profile
    t['routing']['effort'] = 'maximum' if profile == 'critical' else 'high'
    t['routing']['validation'].update(required=True, independent_session=True)
    t['validation_sessions'] = {'implementation': 'impl-' + t['id'], 'validation': 'validate-' + t['id']}


def gated(manual=True):
    a, b = completed(task('A', write=True)), completed(task('B', write=True), 'c' * 40)
    g = completed(task('G', dependencies=['A', 'B']))
    g['type'] = 'integration'
    g['routing'].update(task_class='integration', fallback_agent='antigravity', model_profile='deep', effort='high')
    g['gate'] = {'kind': 'integration', 'upstream': ['A', 'B'], 'result': 'PASS', 'evidence': ['compatibility report'],
                 'baselines': {'nexus': OUTPUT}, 'manual_review_required': manual,
                 'approval': {'status': 'not-required', 'evidence': None, 'scope': None}}
    if manual:
        g['gate']['approval'] = {'status': 'approved', 'evidence': 'human decision reference',
                                 'scope': {'gate_id': 'G', 'upstream': {'A': OUTPUT, 'B': 'c' * 40}, 'baselines': {'nexus': OUTPUT}}}
    consumer = task('C', dependencies=['G'], write=True)
    consumer['base'] = {'source': 'G', 'ref': OUTPUT}
    consumer['type'] = 'integration'
    consumer['upstream_mutations'] = ['A', 'B']
    consumer['routing'].update(task_class='integration', fallback_agent='antigravity')
    validation(consumer)
    return plan(a, b, g, consumer, waves=[{'id': 'W1', 'tasks': ['A', 'B']}, {'id': 'W2', 'tasks': ['G']}, {'id': 'W3', 'tasks': ['C']}])


def assignment(t, role='implementer'):
    r = t['routing']
    receipt = {'agent': r['agent'], 'model_profile': r['model_profile'], 'model': None, 'effort': None, 'status': 'inherit-with-uncertainty'}
    t['assignment'] = {'id': 'assign-' + t['id'], 'work_item_id': 'https://github.com/2muni/nexus/issues/5', 'task_id': t['id'],
                       'repository': t['repository'], 'role': role, 'agent': r['agent'], 'model_profile': r['model_profile'],
                       'effort_intent': r['effort'], 'session_ref': 'impl-' + t['id'], 'backend': 'orca',
                       'requested': copy.deepcopy(receipt), 'effective': copy.deepcopy(receipt), 'evidence': ['supplied receipt; unverified host'],
                       'validation': {'required': r['validation']['required'], 'independent_session': r['validation']['independent_session'], 'candidate': None}}


class ExecutionPlans(unittest.TestCase):
    def check(self, p, **options):
        return CHECKER['check'](p, **options)

    def passes(self, p, **options):
        result = self.check(p, **options)
        self.assertEqual('PASS', result['result'], result['diagnostics'])
        self.assertIs(False, result['dispatch_authority'])
        return result

    def rejects(self, p, field=None, **options):
        result = self.check(p, **options)
        self.assertEqual('NEEDS-WORK', result['result'], result)
        if field:
            self.assertTrue(any(field in d['field'] for d in result['diagnostics']), result)
        return result

    def test_resolved_single_direct(self):
        p = plan()
        p['mode'] = 'DIRECT'
        self.passes(p)

    def test_resolved_multi_repo_read_only_parallel(self):
        self.passes(plan(task('A', 'basecamp'), task('B', 'foundry'), waves=[{'id': 'W', 'tasks': ['A', 'B']}]))

    def test_serial_and_parallel_writers(self):
        a, b = task('A', write=True), task('B', dependencies=['A'], write=True)
        self.passes(plan(a, b))
        b['dependencies'] = []
        self.passes(plan(a, b, waves=[{'id': 'W', 'tasks': ['A', 'B']}]))
        b['mutation_scope']['targets'] = ['docs']
        self.rejects(plan(a, b, waves=[{'id': 'W', 'tasks': ['A', 'B']}]), 'mutation_scope')

    def test_writer_reader_and_ambiguous_component_conflicts(self):
        a, b = task('A', write=True), task('B')
        for target in ['docs', 'docs/A.md', 'docs/*', 'component name', '../docs']:
            with self.subTest(target=target):
                b['mutation_scope']['targets'] = [target]
                self.rejects(plan(a, b, waves=[{'id': 'W', 'tasks': ['A', 'B']}]), 'mutation_scope')

    def test_owner_and_baseline_coverage(self):
        for mutate in [lambda p: p['repositories'].append('unknown'), lambda p: p['baselines'].pop('nexus'),
                       lambda p: p['tasks'][0].update(repository='foundry'), lambda p: p['repositories'].append('nexus')]:
            p = plan()
            mutate(p)
            self.rejects(p)

    def test_duplicate_unknown_missing_wave_ids(self):
        for tasks, waves in [([task(), task()], [{'id': 'W', 'tasks': ['T1']}]),
                             ([task()], [{'id': 'W', 'tasks': ['T1']}, {'id': 'W', 'tasks': ['T1']}]),
                             ([task()], [{'id': 'W', 'tasks': ['unknown']}]),
                             ([task(), task('T2')], [{'id': 'W', 'tasks': ['T1']}])]:
            self.rejects(plan(*tasks, waves=waves))

    def test_dependencies_cycle_self_unknown_order(self):
        for deps in [['T1'], ['missing'], ['T2', 'T2']]:
            self.rejects(plan(task(dependencies=deps)))
        self.rejects(plan(task('A', dependencies=['B']), task('B', dependencies=['A'])), 'dependencies')
        self.rejects(plan(task('A', dependencies=['B']), task('B')), 'dependencies')
        self.rejects(plan(task('A'), task('B', dependencies=['A']), waves=[{'id': 'W', 'tasks': ['A', 'B']}]), 'dependencies')

    def test_immutable_refs_and_sources(self):
        for ref in ['main', 'HEAD', 'REPLACE_WITH_REF', 'pending', True, 1, {}, 'a' * 7, None]:
            p = plan()
            p['tasks'][0]['base']['ref'] = ref
            self.rejects(p, 'base.ref')
        p = plan()
        p['tasks'][0]['base']['ref'] = OUTPUT
        self.rejects(p, 'base.ref')
        p = plan()
        p['tasks'][0]['base']['source'] = 'missing'
        self.rejects(p, 'base.source')

    def test_completed_dependency_exact_ref(self):
        a, b = completed(task('A', write=True)), task('B', dependencies=['A'])
        b['base'] = {'source': 'A', 'ref': OUTPUT}
        self.passes(plan(a, b))
        a['result']['ref'] = 'c' * 40
        self.rejects(plan(a, b), 'base.ref')

    def test_false_direct(self):
        cases = [plan(task('A'), task('B')), plan(task('A', 'nexus'), task('B', 'foundry'))]
        for field, value in [('risk', 'medium'), ('type', 'architecture'), ('architecture_sensitive', True)]:
            p = plan()
            p['tasks'][0][field] = value
            cases.append(p)
        p = plan()
        p['cross_repository_reasoning'] = True
        cases.append(p)
        for p in cases:
            p['mode'] = 'DIRECT'
            self.rejects(p)

    def test_actual_routing_rules_monotonic_or(self):
        p = plan()
        for field, value in [('complexity', 'high'), ('context_size', 'large'), ('risk', 'high'), ('complexity', 'critical'),
                             ('type', 'architecture'), ('architecture_sensitive', True), ('severity', 'P0'), ('severity', 'P1')]:
            q = copy.deepcopy(p)
            q['tasks'][0][field] = value
            with self.subTest(field=field, value=value):
                self.rejects(q, 'routing.model_profile')
        t = task()
        t.update(risk='high', complexity='critical')
        validation(t, 'critical')
        t['routing']['resolution'] = {'status': 'verified', 'model': 'supplied-model', 'effort': 'supplied-supported-effort'}
        self.passes(plan(t))
        t['routing']['model_profile'] = 'deep'
        self.rejects(plan(t), 'routing.model_profile')

    def test_independent_session_and_fallback(self):
        t = task()
        t['architecture_sensitive'] = True
        validation(t)
        self.passes(plan(t))
        t['routing']['validation']['independent_session'] = False
        self.rejects(plan(t), 'independent_session')
        t['routing']['validation']['independent_session'] = True
        t['validation_sessions']['validation'] = t['validation_sessions']['implementation']
        self.rejects(plan(t), 'validation_sessions')
        t['validation_sessions']['validation'] = 'fresh'
        t['routing']['fallback_agent'] = 'opencode'
        self.rejects(plan(t), 'routing.agent')

    def test_class_validation_and_review_floors(self):
        t = task()
        t['type'] = 'architecture'
        t['routing'].update(task_class='architecture', model_profile='deep', effort='high')
        self.rejects(plan(t), 'required')
        t = task()
        t['type'] = 'review'
        t['routing'].update(task_class='independent-review', model_profile='deep', effort='high')
        self.rejects(plan(t), 'independent_session')

    def test_manual_gate_and_exact_changed_scope(self):
        self.passes(gated(), ready_task='C')
        for key, value in [('gate_id', 'old-gate'), ('upstream', {'A': REF, 'B': 'c' * 40}), ('baselines', {'nexus': REF})]:
            p = gated()
            p['tasks'][2]['gate']['approval']['scope'][key] = value
            self.rejects(p, 'gate.approval.scope', ready_task='C')
        p = gated()
        p['tasks'][0]['result']['ref'] = REF
        self.rejects(p, 'gate.approval.scope', ready_task='C')
        p = gated()
        p['tasks'][2]['gate']['baselines']['nexus'] = REF
        self.rejects(p, 'gate.approval.scope', ready_task='C')

    def test_gate_holds_every_transitive_consumer(self):
        for status in ['pending', 'rejected', 'not-required']:
            p = gated()
            p['tasks'][2]['gate']['approval'].update(status=status, evidence=None, scope=None)
            self.rejects(p, 'gate.approval', ready_task='C')
        for status in ['pending', 'FAIL', 'NEEDS-WORK']:
            p = gated(False)
            p['tasks'][2]['gate']['result'] = status
            self.rejects(p, 'gate.result', ready_task='C')
        p = gated(False)
        p['tasks'][2]['gate']['evidence'] = []
        self.rejects(p, 'gate.evidence')
        p = gated(False)
        p['tasks'][2]['gate']['approval']['evidence'] = 'not human authority'
        self.rejects(p, 'gate.approval')

    def test_gate_requires_complete_upstreams_and_baselines(self):
        for mutate in [lambda p: p['tasks'][0].pop('result'), lambda p: p['tasks'][0]['result'].update(outcome='failed'),
                       lambda p: p['tasks'][2]['gate'].update(upstream=['A']),
                       lambda p: p['tasks'][2]['gate'].update(baselines={'foundry': OUTPUT})]:
            p = gated(False)
            mutate(p)
            self.rejects(p)

    def test_shared_parallel_writers_need_gate(self):
        self.rejects(plan(task('A', write=True), task('B', write=True), task('C', dependencies=['A', 'B']),
                          waves=[{'id': 'W', 'tasks': ['A', 'B']}, {'id': 'Next', 'tasks': ['C']}]), 'dependencies')

    def test_upstream_count_includes_gate_inputs(self):
        p = gated(False)
        p['tasks'][3]['routing']['validation']['required'] = False
        self.rejects(p, 'required')
        p = gated(False)
        p['tasks'][3]['upstream_mutations'] = ['A']
        self.rejects(p, 'upstream_mutations')

    def test_draft_never_releases_pending_consumer(self):
        p = gated(False)
        p['tasks'][2].pop('result')
        p['tasks'][2]['gate'].update(result='pending', evidence=[], baselines={'nexus': None})
        p['tasks'][3]['base']['ref'] = None
        p['tasks'][3]['routing']['resolution']['status'] = 'pending'
        result = self.passes(p, draft=True)
        self.assertEqual('draft', result['kind'])
        self.passes(p, ready_wave='W1')
        self.rejects(p, ready_task='C')
        self.rejects(p, ready_task='unknown')
        self.rejects(p, ready_wave='unknown')

    def test_ready_prerequisite_needs_result(self):
        self.rejects(plan(task('A'), task('B', dependencies=['A'])), 'dependencies', ready_task='B')

    def test_canonical_managed_execution_binding(self):
        t = task(write=True)
        assignment(t)
        p = plan(t)
        p['work_item_binding'] = {'provider': 'github', 'repository': '2muni/nexus', 'issue_url': 'https://github.com/2muni/nexus/issues/5'}
        self.passes(p, execution=True)
        t['assignment']['work_item_id'] = 'https://github.com/2muni/nexus/issues/6'
        self.rejects(p, 'assignment.work_item_id', execution=True)
        t['assignment']['work_item_id'] = p['work_item_binding']['issue_url']
        for field, value in [('provider', 'other'), ('repository', '2muni/other'), ('issue_url', 'not-an-issue')]:
            q = copy.deepcopy(p)
            q['work_item_binding'][field] = value
            self.rejects(q, 'work_item_binding.' + field, execution=True)

    def test_renamed_only_and_duplicate_binding_rejected(self):
        t = task(write=True)
        assignment(t)
        p = plan(t)
        binding = {'provider': 'github', 'repository': '2muni/nexus', 'issue_url': 'https://github.com/2muni/nexus/issues/5'}
        p['work_item'] = copy.deepcopy(binding)
        for duplicate in [False, True]:
            with self.subTest(duplicate=duplicate):
                if duplicate:
                    p['work_item_binding'] = copy.deepcopy(binding)
                for execution in [False, True]:
                    result = self.rejects(p, 'plan.work_item', execution=execution)
                    self.assertIs(False, result['dispatch_authority'])

    def test_execution_assignment_claims(self):
        t = task(write=True)
        p = plan(t)
        self.rejects(p, 'assignment', execution=True)
        assignment(t)
        p['work_item_binding'] = {'provider': 'github', 'repository': '2muni/nexus', 'issue_url': 'https://github.com/2muni/nexus/issues/5'}
        self.passes(p, execution=True)
        for field, value in [('role', 'reviewer'), ('task_id', 'other'), ('repository', 'foundry'), ('backend', 'unknown')]:
            q = copy.deepcopy(p)
            q['tasks'][0]['assignment'][field] = value
            self.rejects(q, 'assignment', execution=True)
        q = copy.deepcopy(p)
        q['tasks'][0]['assignment']['effective']['model_profile'] = 'fast'
        self.rejects(q, 'assignment.effective', execution=True)

    def test_gate_consumer_cannot_bypass_selected_baseline(self):
        p = gated(False)
        p['tasks'][3]['base'] = {'source': 'initial', 'ref': REF}
        self.rejects(p, 'base.ref', ready_task='C')

    def test_cross_repository_mutation_contract_gate(self):
        self.rejects(plan(task('A', 'basecamp', write=True), task('B', 'foundry', dependencies=['A'])), 'dependencies')

    def test_effort_intent_preserves_profile_floor(self):
        t = task()
        t['routing'].update(model_profile='critical', effort='low')
        self.rejects(plan(t), 'routing.effort')

    def test_independent_validator_assignment(self):
        a = completed(task('A', write=True))
        assignment(a)
        v = task('V', dependencies=['A'])
        v['type'] = 'validation'
        v['base'] = {'source': 'A', 'ref': OUTPUT}
        v['routing'].update(task_class='validation', model_profile='deep', effort='high')
        v['routing']['validation']['independent_session'] = True
        v['validation_sessions'] = {'implementation': 'impl-A', 'validation': 'fresh-validator'}
        assignment(v, 'validator')
        v['assignment']['session_ref'] = 'fresh-validator'
        v['assignment']['validation']['candidate'] = OUTPUT
        p = plan(a, v)
        p['work_item_binding'] = {'provider': 'github', 'repository': '2muni/nexus', 'issue_url': 'https://github.com/2muni/nexus/issues/5'}
        self.passes(p, ready_task='V', execution=True)
        v['assignment']['session_ref'] = 'impl-A'
        self.rejects(p, 'session_ref', ready_task='V', execution=True)

    def test_assignment_identity_and_writer_session_uniqueness(self):
        a, b = task('A', write=True), task('B', write=True)
        assignment(a)
        assignment(b)
        p = plan(a, b, waves=[{'id': 'W', 'tasks': ['A', 'B']}])
        b['assignment']['id'] = a['assignment']['id']
        self.rejects(p, 'assignment.id')
        b['assignment']['id'] = 'unique'
        b['assignment']['session_ref'] = a['assignment']['session_ref']
        self.rejects(p, 'session_ref')

    def test_resolved_cross_repository_gate(self):
        p = gated(False)
        for t, owner in zip(p['tasks'], ['basecamp', 'foundry', 'nexus', 'basecamp']):
            t['repository'] = owner
        p['repositories'] = ['nexus', 'basecamp', 'foundry']
        for owner in ['basecamp', 'foundry']:
            p['baselines'][owner] = copy.deepcopy(p['baselines']['nexus'])
        p['tasks'][2]['gate']['baselines'] = {'basecamp': OUTPUT, 'foundry': 'c' * 40}
        self.passes(p, ready_task='C')

    def test_gate_unknown_upstream_returns_diagnostics(self):
        p = gated(False)
        p['tasks'][2]['gate']['upstream'] = ['missing']
        self.rejects(p, 'gate.upstream')
        p = gated(False)
        p['tasks'][2]['result']['outcome'] = 'failed'
        self.rejects(p, 'gate.result')

    def test_transitive_manual_gate_hold(self):
        p = gated()
        completed(p['tasks'][3])
        d = task('D', dependencies=['C'])
        d['base'] = {'source': 'C', 'ref': OUTPUT}
        p['tasks'].append(d)
        p['waves'].append({'id': 'W4', 'tasks': ['D']})
        self.passes(p, ready_task='D')
        p['tasks'][2]['gate']['approval'].update(status='pending', evidence=None, scope=None)
        self.rejects(p, 'gate.approval', ready_task='D')

    def test_nested_adversarial_shapes(self):
        original = gated()
        def paths(value, path=()):
            yield path
            if type(value) is dict:
                for key, child in value.items():
                    yield from paths(child, path + (key,))
            elif type(value) is list:
                for key, child in enumerate(value):
                    yield from paths(child, path + (key,))
        for path in paths(original):
            for value in [None, True, 0, '', [], {}, [{}], {'odd': []}]:
                p = copy.deepcopy(original)
                if path:
                    target = p
                    for key in path[:-1]:
                        target = target[key]
                    target[path[-1]] = value
                else:
                    p = value
                result = self.check(p)
                self.assertIn(result['result'], ['PASS', 'NEEDS-WORK'])
                self.assertIs(False, result['dispatch_authority'])

    def test_adversarial_types_and_missing_fields(self):
        valid = plan()
        for value in [None, [], 1, True, 'plan']:
            self.rejects(value)
        for key in valid:
            p = copy.deepcopy(valid)
            del p[key]
            self.rejects(p)
        for key in valid['tasks'][0]:
            p = copy.deepcopy(valid)
            del p['tasks'][0][key]
            self.rejects(p)
        for path in [('version',), ('tasks', 0, 'parallelizable'), ('tasks', 0, 'architecture_sensitive'),
                     ('tasks', 0, 'routing', 'validation', 'required'), ('tasks', 0, 'routing', 'validation', 'independent_session')]:
            for value in [True, False, 0, 1, 'false', [], {}]:
                if (len(path) > 1 and type(value) is bool) or (path == ('version',) and type(value) is int and value == 1):
                    continue
                p = copy.deepcopy(valid)
                target = p
                for key in path[:-1]:
                    target = target[key]
                target[path[-1]] = value
                self.rejects(p)
        for value in [None, {}, ['nexus', {}], ['nexus', []], [True]]:
            p = copy.deepcopy(valid)
            p['repositories'] = value
            self.rejects(p)

    def test_unknown_ambiguous_fields(self):
        p = plan()
        p['tasks'][0]['routing']['validation']['required_ci'] = []
        self.rejects(p, 'required_ci')
        p = plan()
        p['dispatch_authority'] = True
        self.rejects(p, 'dispatch_authority')

    def test_supported_policy_revision_required(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in CHECKER['SUPPORTED']:
                destination = root / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes((ROOT / name).read_bytes())
            self.passes(plan(), root=root)
            for name in ['config/routing.yaml', 'config/review.yaml', 'config/planning.yaml', 'config/acceptance.json', 'config/repositories.yaml']:
                old = (root / name).read_text()
                (root / name).write_text(old + '\nunknown_policy: true\n')
                self.rejects(plan(), 'policy', root=root)
                (root / name).write_text(old)
            (root / 'config/review.yaml').unlink()
            self.rejects(plan(), 'policy', root=root)

    def test_cli_json_yaml_extension_and_unsupported_syntax(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'plan.yaml'
            for content, expected in [(json.dumps(plan()), 0), ('version: 1\ntasks: []\n', 1),
                                      ('{"version":1,"version":1}', 1), ('{"version":NaN}', 1),
                                      ('{"version":Infinity}', 1), ('[', 1)]:
                path.write_text(content)
                run = subprocess.run(['python3', '-B', str(ROOT / 'scripts/check-plan.py'), str(path)], capture_output=True, text=True)
                self.assertEqual(expected, run.returncode, run.stderr)
                result = json.loads(run.stdout)
                self.assertIs(False, result['dispatch_authority'])
            path.write_text(json.dumps(plan()))
            run = subprocess.run(['python3', '-B', str(ROOT / 'scripts/check-plan.py'), str(path), '--draft', '--execution-requested'], capture_output=True, text=True)
            self.assertEqual(1, run.returncode)
            self.assertEqual('NEEDS-WORK', json.loads(run.stdout)['result'])


if __name__ == '__main__':
    unittest.main()
