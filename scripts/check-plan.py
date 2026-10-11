#!/usr/bin/env python3
"""One-shot development check of JSON Execution Plans; grants no authority."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
# Reviewed policy syntax/semantics at e41e615; hashes exclude blank/full-comment lines.
# Unsupported revisions HOLD rather than silently guessing new policy semantics.
SUPPORTED = {
    'config/planning.yaml': '4071363a303ae0ff8b923835c5407c7edea9df91aba38ca28982257e130fad63',
    'config/routing.yaml': 'dc1abfd6accd0b3c900b9f166e46db8507bd7f07eb1a1fe9343d12524a3d298c',
    'config/review.yaml': '8dbe71e6ddeb73bd6c950b42c5229b6a2a179af04f9d2b64acc05437250efc6a',
    'config/repositories.yaml': '996a1c7a5d97d55fb646beaa6f47bef6704174d3f25b25f9823c7b8f26c626e4',
    'schemas/execution-plan.yaml': 'c3741796c149764965d09c11b6aa851584cb1560fa43b36fbe1d027445d09cee',
    'schemas/agent-assignment.yaml': 'd23463c881603de4bf9397468fe857c7f1616798f0f341aa8947b66ceb1e745f',
    'config/execution-backends.yaml': '62967798a1f207fdda98eb012a6455df087243c9bb72cb4569d6e003cdae1f1f',
    'config/acceptance.json': '3c4d2a5fc28333022f794b8a038ff161677169e661a01268d8c495c28dcbf8f8',
}


def fingerprint(text):
    return hashlib.sha256('\n'.join(line for line in text.splitlines()
                                   if line.strip() and not line.lstrip().startswith('#')).encode()).hexdigest()


def load_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('duplicate JSON key: ' + key)
            result[key] = value
        return result
    return json.loads(text, object_pairs_hook=pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError('non-JSON constant: ' + value)))


def section(text, name, indent=0):
    match = re.search(r'^' + ' ' * indent + re.escape(name) + r':\n((?:(?:' + ' ' * (indent + 1) + r'[^\n]*|)\n)*)', text, re.M)
    if not match:
        raise ValueError('unsupported policy section: ' + name)
    return match[1]


def keys(text, indent):
    return re.findall(r'^' + ' ' * indent + r'([a-z][a-z0-9_-]*):', text, re.M)


def inline(value):
    # Only the reviewed routing-rule inline maps; not a YAML parser.
    value = re.sub(r'([A-Za-z_][\w-]*)(?=\s*:)', r'"\1"', value)
    value = re.sub(r'(?<![\w"-])([A-Za-z][\w-]*)(?![\w"-])',
                   lambda m: m[0] if m[0] in ('true', 'false', 'null') else json.dumps(m[0]), value)
    return load_json(value)


def policies(root):
    texts = {}
    for name, expected in SUPPORTED.items():
        text = (root / name).read_text()
        if fingerprint(text) != expected:
            raise ValueError('unsupported policy revision: ' + name)
        texts[name] = text
    routing = texts['config/routing.yaml']
    classes = {}
    blocks = section(routing, 'task_classes', 2)
    for name in keys(blocks, 4):
        block = section(blocks, name, 4)
        classes[name] = dict(re.findall(r'^      ([\w_]+): ([\w-]+)$', block, re.M))
    rules = [(inline(a), inline(b)) for a, b in re.findall(
        r'^  - when: (\{[^\n]+\})\n    override: (\{[^\n]+\})$', routing, re.M)]
    order = re.search(r'^  profile_order: \[([^]]+)\]', routing, re.M)[1].split(', ')
    schema = texts['schemas/execution-plan.yaml']
    def contract_list(field, indent):
        return re.search(r'^' + ' ' * indent + field + r': \[([^]]+)\]', schema, re.M)[1].split(', ')
    return {'repositories': keys(section(texts['config/repositories.yaml'], 'repositories'), 2),
            'agents': keys(section(routing, 'agent_catalog'), 2), 'classes': classes,
            'profiles': order, 'reasoning': dict(re.findall(r'^  ([a-z]+):\n    reasoning: ([a-z]+)$', section(routing, 'model_profiles'), re.M)), 'rules': rules, 'plan_required': contract_list('required', 2),
            'task_required': contract_list('required', 4),
            'enums': {k: contract_list(k, 4) for k in ('type', 'complexity', 'risk', 'context_size')},
            'backends': keys(section(texts['config/execution-backends.yaml'], 'backends'), 2),
            'provenance': {name: fingerprint(text) for name, text in texts.items()}}


class Check:
    def __init__(self, policy):
        self.policy = policy
        self.diagnostics = []

    def error(self, field, message, task=None):
        self.diagnostics.append({'task': task, 'field': field, 'message': message})

    def obj(self, value, field, required, optional=(), task=None):
        if type(value) is not dict:
            self.error(field, 'expected object', task)
            return {}
        for key in required:
            if key not in value:
                self.error(field + '.' + key, 'required field missing', task)
        for key in value:
            if key not in set(required) | set(optional):
                self.error(field + '.' + key, 'unsupported/ambiguous field', task)
        return value

    def string(self, value, field, task=None, choices=None):
        valid = type(value) is str and bool(value.strip())
        if not valid or (choices is not None and value not in choices):
            self.error(field, 'expected nonempty string' if choices is None else 'expected one of ' + ', '.join(choices), task)
            return False
        return True

    def boolean(self, value, field, task=None):
        if type(value) is not bool:
            self.error(field, 'expected strict boolean', task)

    def strings(self, value, field, task=None, nonempty=True):
        if type(value) is not list:
            self.error(field, 'expected array of strings', task)
            return []
        if nonempty and not value:
            self.error(field, 'must not be empty', task)
        for item in value:
            self.string(item, field, task)
        if all(type(x) is str for x in value) and len(set(value)) != len(value):
            self.error(field, 'duplicate entries', task)
        return [x for x in value if type(x) is str and x.strip()]

    def ref(self, value, field, task=None, pending=False):
        if value is None and pending:
            return
        if type(value) is not str or not re.fullmatch(r'(?:[0-9a-f]{40}|[0-9a-f]{64}|sha256:[0-9a-f]{64})', value):
            self.error(field, 'expected full immutable Git revision or SHA256 patch digest' + (' (null allowed for future draft task)' if pending else ''), task)

    def shape(self, plan):
        p = self.policy
        plan = self.obj(plan, 'plan', p['plan_required'], ('work_item_binding', 'cross_repository_reasoning'))
        if type(plan.get('version')) is not int or plan.get('version') != 1:
            self.error('version', 'expected integer version 1')
        self.string(plan.get('objective'), 'objective')
        self.string(plan.get('mode'), 'mode', choices=('DIRECT', 'ORCHESTRATED'))
        repos = self.strings(plan.get('repositories'), 'repositories')
        for repo in repos:
            if repo not in p['repositories']:
                self.error('repositories', 'unknown owner registry key: ' + str(repo))
        self.strings(plan.get('requirements'), 'requirements')
        self.string(plan.get('final_gate'), 'final_gate', choices=('human-review-required',))
        if 'cross_repository_reasoning' in plan:
            self.boolean(plan['cross_repository_reasoning'], 'cross_repository_reasoning')
        baselines = self.obj(plan.get('baselines'), 'baselines', repos)
        for repo, baseline in baselines.items():
            b = self.obj(baseline, 'baselines.' + repo, ('ref', 'scope', 'dirty_state'))
            self.ref(b.get('ref'), 'baselines.' + repo + '.ref')
            for field in ('scope', 'dirty_state'):
                self.string(b.get(field), 'baselines.' + repo + '.' + field)
        if 'work_item_binding' in plan:
            item = self.obj(plan['work_item_binding'], 'work_item_binding', ('provider', 'repository', 'issue_url'))
            self.string(item.get('provider'), 'work_item_binding.provider', choices=('github',))
            self.string(item.get('repository'), 'work_item_binding.repository')
            if type(item.get('issue_url')) is not str or not re.fullmatch(r'https://github\.com/[^/\s]+/[^/\s]+/issues/[1-9][0-9]*', item['issue_url']):
                self.error('work_item_binding.issue_url', 'expected canonical GitHub Issue URL')
            elif item.get('repository') != item['issue_url'].split('github.com/', 1)[1].split('/issues/', 1)[0]:
                self.error('work_item_binding.repository', 'provider repository must match canonical Issue URL')
        tasks = plan.get('tasks')
        if type(tasks) is not list or not tasks:
            self.error('tasks', 'expected nonempty task array')
            tasks = []
        for task in tasks:
            t = self.obj(task, 'task', p['task_required'], ('severity', 'upstream_mutations', 'gate', 'assignment', 'result', 'validation_sessions'))
            tid = t.get('id') if type(t.get('id')) is str else None
            for field in ('id', 'title', 'repository'):
                self.string(t.get(field), field, tid)
            for field, choices in p['enums'].items():
                self.string(t.get(field), field, tid, choices)
            for field in ('parallelizable', 'architecture_sensitive'):
                self.boolean(t.get(field), field, tid)
            if 'severity' in t:
                self.string(t['severity'], 'severity', tid, ('P0', 'P1', 'P2', 'P3'))
            self.strings(t.get('dependencies'), 'dependencies', tid, False)
            self.strings(t.get('acceptance'), 'acceptance', tid)
            scope = self.obj(t.get('mutation_scope'), 'mutation_scope', ('mode', 'targets', 'do_not_touch'), task=tid)
            self.string(scope.get('mode'), 'mutation_scope.mode', tid, ('read-only', 'write'))
            targets = self.strings(scope.get('targets'), 'mutation_scope.targets', tid)
            for target in targets:
                if literal_path(target) is None:
                    self.error('mutation_scope.targets', 'supported scope is a literal bounded repository-relative path; component/glob/escape is ambiguous', tid)
            self.strings(scope.get('do_not_touch'), 'mutation_scope.do_not_touch', tid)
            base = self.obj(t.get('base'), 'base', ('source', 'ref'), task=tid)
            self.string(base.get('source'), 'base.source', tid)
            self.ref(base.get('ref'), 'base.ref', tid, True)
            r = self.obj(t.get('routing'), 'routing', ('task_class', 'agent', 'fallback_agent', 'model_profile', 'effort', 'reasons', 'validation', 'resolution'), task=tid)
            for field, choices in [('task_class', p['classes']), ('agent', p['agents']), ('model_profile', p['profiles'])]:
                self.string(r.get(field), 'routing.' + field, tid, choices)
            if r.get('fallback_agent') is not None:
                self.string(r['fallback_agent'], 'routing.fallback_agent', tid, p['agents'])
            self.string(r.get('effort'), 'routing.effort', tid, ('low', 'medium', 'high', 'maximum'))
            self.strings(r.get('reasons'), 'routing.reasons', tid)
            v = self.obj(r.get('validation'), 'routing.validation', ('required', 'independent_session', 'preferred_agent'), task=tid)
            for field in ('required', 'independent_session'):
                self.boolean(v.get(field), 'routing.validation.' + field, tid)
            self.string(v.get('preferred_agent'), 'routing.validation.preferred_agent', tid, p['agents'])
            res = self.obj(r.get('resolution'), 'routing.resolution', ('status', 'model', 'effort'), task=tid)
            self.string(res.get('status'), 'routing.resolution.status', tid, ('pending', 'verified', 'inherit-with-uncertainty', 'blocked'))
            for field in ('model', 'effort'):
                if res.get(field) is not None:
                    self.string(res[field], 'routing.resolution.' + field, tid)
            if 'upstream_mutations' in t:
                self.strings(t['upstream_mutations'], 'upstream_mutations', tid)
            if 'validation_sessions' in t:
                sessions = self.obj(t['validation_sessions'], 'validation_sessions', ('implementation', 'validation'), task=tid)
                for field in ('implementation', 'validation'):
                    self.string(sessions.get(field), 'validation_sessions.' + field, tid)
            if 'result' in t:
                result = self.obj(t['result'], 'result', ('outcome', 'ref', 'evidence'), task=tid)
                self.string(result.get('outcome'), 'result.outcome', tid, ('succeeded', 'failed'))
                self.ref(result.get('ref'), 'result.ref', tid)
                self.strings(result.get('evidence'), 'result.evidence', tid)
            if 'gate' in t:
                self.gate_shape(t)
            if 'assignment' in t:
                self.assignment_shape(t)
        waves = plan.get('waves')
        if type(waves) is not list or not waves:
            self.error('waves', 'expected nonempty wave array')
            waves = []
        for wave in waves:
            w = self.obj(wave, 'wave', ('id', 'tasks'))
            self.string(w.get('id'), 'wave.id')
            self.strings(w.get('tasks'), 'wave.tasks')
        return plan

    def gate_shape(self, t):
        tid = t.get('id')
        g = self.obj(t['gate'], 'gate', ('kind', 'upstream', 'result', 'evidence', 'baselines', 'manual_review_required', 'approval'), task=tid)
        self.string(g.get('kind'), 'gate.kind', tid, ('integration',))
        self.strings(g.get('upstream'), 'gate.upstream', tid)
        self.string(g.get('result'), 'gate.result', tid, ('pending', 'PASS', 'FAIL', 'NEEDS-WORK'))
        self.strings(g.get('evidence'), 'gate.evidence', tid, g.get('result') == 'PASS')
        self.boolean(g.get('manual_review_required'), 'gate.manual_review_required', tid)
        baselines = g.get('baselines')
        if type(baselines) is not dict or not baselines:
            self.error('gate.baselines', 'expected nonempty repository/ref object', tid)
        else:
            for repo, ref in baselines.items():
                self.string(repo, 'gate.baselines.repository', tid, self.policy['repositories'])
                self.ref(ref, 'gate.baselines.' + repo, tid, g.get('result') == 'pending')
        a = self.obj(g.get('approval'), 'gate.approval', ('status', 'evidence', 'scope'), task=tid)
        self.string(a.get('status'), 'gate.approval.status', tid, ('not-required', 'pending', 'approved', 'rejected'))
        if a.get('evidence') is not None:
            self.string(a['evidence'], 'gate.approval.evidence', tid)
        if a.get('scope') is not None:
            s = self.obj(a['scope'], 'gate.approval.scope', ('gate_id', 'upstream', 'baselines'), task=tid)
            self.string(s.get('gate_id'), 'gate.approval.scope.gate_id', tid)
            for field in ('upstream', 'baselines'):
                if type(s.get(field)) is not dict:
                    self.error('gate.approval.scope.' + field, 'expected exact ID/ref map', tid)
                else:
                    for key, ref in s[field].items():
                        self.ref(ref, 'gate.approval.scope.' + field + '.' + key, tid)

    def assignment_shape(self, t):
        tid = t.get('id')
        required = ('id', 'work_item_id', 'task_id', 'repository', 'role', 'agent', 'model_profile', 'effort_intent', 'session_ref', 'backend', 'requested', 'effective', 'evidence', 'validation')
        a = self.obj(t['assignment'], 'assignment', required, task=tid)
        for field in ('id', 'work_item_id', 'task_id', 'repository', 'session_ref', 'effort_intent'):
            self.string(a.get(field), 'assignment.' + field, tid)
        for field, choices in [('role', ('implementer', 'reviewer', 'validator', 'planner')), ('agent', self.policy['agents']), ('model_profile', self.policy['profiles']), ('backend', self.policy['backends'])]:
            self.string(a.get(field), 'assignment.' + field, tid, choices)
        self.strings(a.get('evidence'), 'assignment.evidence', tid)
        for field in ('requested', 'effective'):
            receipt = self.obj(a.get(field), 'assignment.' + field, ('agent', 'model_profile', 'model', 'effort', 'status'), task=tid)
            self.string(receipt.get('agent'), 'assignment.' + field + '.agent', tid, self.policy['agents'])
            self.string(receipt.get('model_profile'), 'assignment.' + field + '.model_profile', tid, self.policy['profiles'])
            self.string(receipt.get('status'), 'assignment.' + field + '.status', tid, ('verified', 'inherit-with-uncertainty'))
            for key in ('model', 'effort'):
                if receipt.get(key) is not None:
                    self.string(receipt[key], 'assignment.' + field + '.' + key, tid)
        v = self.obj(a.get('validation'), 'assignment.validation', ('required', 'independent_session', 'candidate'), task=tid)
        self.boolean(v.get('required'), 'assignment.validation.required', tid)
        self.boolean(v.get('independent_session'), 'assignment.validation.independent_session', tid)
        if v.get('candidate') is not None:
            self.ref(v['candidate'], 'assignment.validation.candidate', tid)

    def semantics(self, plan, draft=False, ready_task=None, ready_wave=None, execution=False):
        tasks = {t['id']: t for t in plan['tasks']}
        if len(tasks) != len(plan['tasks']):
            self.error('tasks.id', 'duplicate task IDs')
        wave_ids = [w['id'] for w in plan['waves']]
        if len(set(wave_ids)) != len(wave_ids):
            self.error('waves.id', 'duplicate wave IDs')
        placement = {}
        for index, wave in enumerate(plan['waves']):
            for tid in wave['tasks']:
                if tid not in tasks:
                    self.error('waves.tasks', 'unknown task: ' + tid)
                if tid in placement:
                    self.error('waves.tasks', 'task appears more than once: ' + tid, tid)
                placement[tid] = index
        for tid in tasks:
            if tid not in placement:
                self.error('waves.tasks', 'task must appear exactly once', tid)
        for tid, t in tasks.items():
            if t['repository'] not in plan['repositories']:
                self.error('repository', 'owner not declared by plan', tid)
            for dep in t['dependencies']:
                if dep not in tasks or dep == tid:
                    self.error('dependencies', 'unknown/self dependency: ' + dep, tid)
                elif placement.get(dep, -1) >= placement.get(tid, -1):
                    self.error('dependencies', 'dependency must precede consumer wave', tid)
        # Iterative reachability: no recursion on adversarial deep graphs.
        ancestors = {tid: set() for tid in tasks}
        for _ in range(len(tasks)):
            changed = False
            for tid, t in tasks.items():
                expanded = set(t['dependencies']) & tasks.keys()
                for dep in list(expanded):
                    expanded |= ancestors[dep]
                if expanded != ancestors[tid]:
                    ancestors[tid] = expanded
                    changed = True
            if not changed:
                break
        for tid in tasks:
            if tid in ancestors[tid]:
                self.error('dependencies', 'cycle detected', tid)
        if self.diagnostics:
            return
        selected = set(tasks) if not draft and not ready_task and not ready_wave else set()
        if ready_task:
            if ready_task not in tasks:
                self.error('selection', 'unknown ready task: ' + ready_task)
            else:
                selected.add(ready_task)
        if ready_wave:
            if ready_wave not in wave_ids:
                self.error('selection', 'unknown ready wave: ' + ready_wave)
            else:
                selected.update(plan['waves'][wave_ids.index(ready_wave)]['tasks'])
        for wave in plan['waves']:
            members = [tasks[x] for x in wave['tasks']]
            if len(members) > 1:
                for t in members:
                    if not t['parallelizable']:
                        self.error('parallelizable', 'same-wave task must declare independence', t['id'])
            for i, a in enumerate(members):
                for b in members[i + 1:]:
                    if a['repository'] == b['repository'] and (a['mutation_scope']['mode'] == 'write' or b['mutation_scope']['mode'] == 'write'):
                        if any(overlap(x, y) for x in a['mutation_scope']['targets'] for y in b['mutation_scope']['targets']):
                            self.error('mutation_scope.targets', 'same-wave conflict with ' + b['id'], a['id'])
        assignment_ids = [t['assignment']['id'] for t in tasks.values() if 'assignment' in t]
        if len(set(assignment_ids)) != len(assignment_ids):
            self.error('assignment.id', 'duplicate logical assignment IDs')
        for wave in plan['waves']:
            writers = [tasks[x] for x in wave['tasks'] if tasks[x]['mutation_scope']['mode'] == 'write' and 'assignment' in tasks[x]]
            sessions = [t['assignment']['session_ref'] for t in writers]
            if len(set(sessions)) != len(sessions):
                self.error('assignment.session_ref', 'same-wave writers must declare distinct owner sessions')
        for tid, t in tasks.items():
            mutable = {x for x in ancestors[tid] if tasks[x]['mutation_scope']['mode'] == 'write'}
            # The reviewed rule counts contributing inputs, including through gates.
            if 'upstream_mutations' in t and set(t['upstream_mutations']) != mutable:
                self.error('upstream_mutations', 'must equal distinct mutable dependency ancestors', tid)
            if t['type'] == 'integration' and t['mutation_scope']['mode'] == 'write' and len(mutable) >= 2 and 'upstream_mutations' not in t:
                self.error('upstream_mutations', 'required for multi-input mutable integration', tid)
            self.route(t, len(mutable), tid in selected)
            source = t['base']['source']
            if tid in selected:
                self.ref(t['base']['ref'], 'base.ref', tid)
            if source == 'initial':
                if t['base']['ref'] is not None and t['base']['ref'] != plan['baselines'][t['repository']]['ref']:
                    self.error('base.ref', 'initial base must match owner baseline', tid)
            elif source not in ancestors[tid]:
                self.error('base.source', 'must be initial or dependency ancestor', tid)
            elif t['base']['ref'] is not None:
                producer = tasks[source]
                expected = producer.get('gate', {}).get('baselines', {}).get(t['repository']) if 'gate' in producer else producer.get('result', {}).get('ref')
                if expected != t['base']['ref'] or (not producer.get('gate') and producer.get('result', {}).get('outcome') != 'succeeded'):
                    self.error('base.ref', 'missing/stale completed dependency or gate baseline', tid)
            if (ready_task or ready_wave) and tid in selected:
                for dep in t['dependencies']:
                    if tasks[dep].get('result', {}).get('outcome') != 'succeeded':
                        self.error('dependencies', 'selected task needs explicit succeeded prerequisite: ' + dep, tid)
            if 'gate' in t:
                self.gate(t, tasks, ancestors, selected)
            for dep in ancestors[tid]:
                if 'gate' in tasks[dep] and tid in selected:
                    self.require_gate(tasks[dep], tid)
                    baseline = tasks[dep]['gate']['baselines'].get(t['repository'])
                    if baseline is not None and source != dep and dep not in ancestors.get(source, set()) and t['base']['ref'] != baseline:
                        self.error('base.ref', 'consumer base bypasses selected gate baseline: ' + dep, tid)
            foreign = {x for x in mutable if tasks[x]['repository'] != t['repository']}
            if foreign and 'gate' not in t:
                covered = set()
                for g in ancestors[tid]:
                    if 'gate' in tasks[g]:
                        for u in tasks[g]['gate']['upstream']:
                            covered.add(u)
                            covered |= ancestors.get(u, set())
                if not foreign <= covered:
                    self.error('dependencies', 'cross-repository mutation contract requires compatibility gate', tid)
            # Shared consumers of parallel writers need a gate covering both writers.
            writers = sorted(mutable)
            for i, a in enumerate(writers):
                for b in writers[i + 1:]:
                    parallel = placement[a] == placement[b]
                    cross = tasks[a]['repository'] != tasks[b]['repository']
                    if (parallel or cross) and 'gate' not in t:
                        gates = [tasks[g]['gate'] for g in ancestors[tid] if 'gate' in tasks[g]]
                        if not any({a, b} <= set(g['upstream']) | set().union(*(ancestors.get(u, set()) for u in g['upstream'])) for g in gates):
                            self.error('dependencies', 'shared parallel/cross-repository mutation consumer requires compatibility gate', tid)
            if execution and tid in selected:
                self.assignment(t, plan, tasks, ancestors)
        if plan['mode'] == 'DIRECT':
            eligible = len(tasks) == 1 and len(plan['repositories']) == 1 and not plan.get('cross_repository_reasoning', False)
            for t in tasks.values():
                eligible &= t['risk'] == 'low' and not t['dependencies'] and t['type'] not in ('architecture', 'integration') and not t['architecture_sensitive'] and not t['routing']['validation']['required'] and not t['routing']['validation']['independent_session']
            if not eligible:
                self.error('mode', 'DIRECT requires exactly one low-risk task, no dependencies, architecture/cross-repository reasoning or independent validation')

    def route(self, t, upstream_count, selected):
        p, r, tid = self.policy, t['routing'], t['id']
        cls = p['classes'][r['task_class']]
        expected_class = {'mechanical': 'implementation-mechanical', 'review': 'independent-review'}.get(t['type'], t['type'])
        if not (r['task_class'].startswith('implementation-') if t['type'] == 'implementation' else r['task_class'] == expected_class):
            self.error('routing.task_class', 'task class does not match declared task type', tid)
        profiles = [cls['model_profile']]
        required = cls.get('independent_validation') == 'true'
        independent = cls.get('independent_session') == 'true' or t['type'] == 'validation'
        if t['type'] in ('review', 'validation') and t['mutation_scope']['mode'] != 'read-only':
            self.error('mutation_scope.mode', 'review/validation tasks must remain read-only', tid)
        facts = dict(t, mutation_mode=t['mutation_scope']['mode'], minimum_upstream_mutations=upstream_count)
        for when, override in p['rules']:
            matches = all(facts.get(k, 0) >= v if k == 'minimum_upstream_mutations' else
                          facts.get(k) in v if type(v) is list else facts.get(k) == v for k, v in when.items())
            if matches:
                profiles.append(override['model_profile'])
                required |= override.get('independent_validation', False)
        floor = max(p['profiles'].index(x) for x in profiles)
        if p['profiles'].index(r['model_profile']) < floor:
            self.error('routing.model_profile', 'below maximum matching policy floor: ' + p['profiles'][floor], tid)
        effort_order = ('low', 'medium', 'high', 'maximum')
        if effort_order.index(r['effort']) < effort_order.index(p['reasoning'][r['model_profile']]):
            self.error('routing.effort', 'abstract effort intent below selected policy profile', tid)
        compatible = {cls['preferred_agent'], cls['fallback_agent']}
        if r['agent'] not in compatible or (r['fallback_agent'] is not None and r['fallback_agent'] not in compatible):
            self.error('routing.agent', 'agent/fallback outside configured task-class pair', tid)
        v = r['validation']
        if required and not v['required']:
            self.error('routing.validation.required', 'mandatory matching validation rule cannot be lowered', tid)
        if (required or independent or v['required']) and not v['independent_session']:
            self.error('routing.validation.independent_session', 'fresh independent session required', tid)
        if v['required'] or independent:
            s = t.get('validation_sessions', {})
            if not s or s['implementation'] == s['validation']:
                self.error('validation_sessions', 'declare distinct implementation and validation sessions', tid)
        res = r['resolution']
        if selected and res['status'] not in ('verified', 'inherit-with-uncertainty'):
            self.error('routing.resolution.status', 'ready check needs resolved routing intent', tid)
        if selected and (t['risk'] == 'high' or t['complexity'] == 'critical') and res['status'] != 'verified':
            self.error('routing.resolution.status', 'high-risk/critical capability claims require verified receipt; static checker cannot verify host', tid)
        if res['status'] == 'verified' and (res['model'] is None or res['effort'] is None):
            self.error('routing.resolution', 'verified claim requires model and effort values', tid)

    def gate(self, t, tasks, ancestors, selected):
        g, tid = t['gate'], t['id']
        if t['type'] != 'integration' or t['mutation_scope']['mode'] != 'read-only':
            self.error('gate', 'compatibility gate must be read-only integration task', tid)
        if set(g['upstream']) != set(t['dependencies']):
            self.error('gate.upstream', 'must exactly name direct dependency inputs', tid)
        inputs = set(g['upstream'])
        for upstream in g['upstream']:
            inputs |= {x for x in ancestors.get(upstream, set()) if tasks[x]['mutation_scope']['mode'] == 'write'}
        repos = {tasks[x]['repository'] for x in inputs if x in tasks}
        if set(g['baselines']) != repos:
            self.error('gate.baselines', 'must cover exactly upstream repositories', tid)
        if g['result'] == 'PASS':
            if 'result' in t and t['result']['outcome'] != 'succeeded':
                self.error('gate.result', 'PASS contradicts failed gate task outcome', tid)
            for upstream in g['upstream']:
                if upstream not in tasks or tasks[upstream].get('result', {}).get('outcome') != 'succeeded':
                    self.error('gate.upstream', 'PASS needs succeeded input and exact artifact: ' + upstream, tid)
            for repo, ref in g['baselines'].items():
                self.ref(ref, 'gate.baselines.' + repo, tid)
        a = g['approval']
        if not g['manual_review_required']:
            if a != {'status': 'not-required', 'evidence': None, 'scope': None}:
                self.error('gate.approval', 'nonmanual gate requires not-required/null evidence/null scope', tid)
        elif a['status'] == 'approved':
            expected = {'gate_id': tid, 'upstream': {x: tasks[x].get('result', {}).get('ref') for x in g['upstream'] if x in tasks}, 'baselines': g['baselines']}
            if not a['evidence'] or a['scope'] != expected or g['result'] != 'PASS':
                self.error('gate.approval.scope', 'approval must bind exact PASS gate, input artifacts and selected baselines', tid)
        elif a['status'] == 'not-required':
            self.error('gate.approval.status', 'manual gate cannot waive approval', tid)

    def require_gate(self, producer, consumer):
        g = producer['gate']
        if g['result'] != 'PASS':
            self.error('gate.result', 'consumer held by unresolved/non-PASS gate ' + producer['id'], consumer)
        if g['manual_review_required'] and g['approval']['status'] != 'approved':
            self.error('gate.approval.status', 'consumer held pending exact human approval for ' + producer['id'], consumer)

    def assignment(self, t, plan, tasks, ancestors):
        tid, a, r = t['id'], t.get('assignment'), t['routing']
        if not a:
            self.error('assignment', 'required when execution is requested', tid)
            return
        item = plan.get('work_item_binding')
        if not item or a['work_item_id'] != item['issue_url']:
            self.error('assignment.work_item_id', 'execution check supports canonical GitHub binding only', tid)
        for field, expected in [('task_id', tid), ('repository', t['repository']), ('agent', r['agent']), ('model_profile', r['model_profile']), ('effort_intent', r['effort'])]:
            if a[field] != expected:
                self.error('assignment.' + field, 'must match logical task/routing', tid)
        role = a['role']
        if (t['mutation_scope']['mode'] == 'write' and role != 'implementer') or (role in ('reviewer', 'validator', 'planner') and t['mutation_scope']['mode'] != 'read-only'):
            self.error('assignment.role', 'role conflicts with mutation scope', tid)
        if t['type'] == 'validation' and role != 'validator' or t['type'] == 'review' and role != 'reviewer':
            self.error('assignment.role', 'role must match read-only task purpose', tid)
        for field in ('required', 'independent_session'):
            if r['validation'][field] and not a['validation'][field]:
                self.error('assignment.validation.' + field, 'cannot lower routing validation floor', tid)
        for field in ('requested', 'effective'):
            receipt = a[field]
            if receipt['agent'] != r['agent'] or self.policy['profiles'].index(receipt['model_profile']) < self.policy['profiles'].index(r['model_profile']):
                self.error('assignment.' + field, 'receipt lowers or disagrees with routing', tid)
            if receipt['status'] == 'verified' and (receipt['model'] is None or receipt['effort'] is None):
                self.error('assignment.' + field, 'verified claim needs concrete model/effort', tid)
        if a['effective']['status'] != r['resolution']['status'] or any(a['effective'][k] != r['resolution'][k] for k in ('model', 'effort')):
            self.error('assignment.effective', 'must match supplied routing resolution receipt', tid)
        session_role = 'validation' if role == 'validator' else 'implementation'
        if 'validation_sessions' in t and a['session_ref'] != t['validation_sessions'][session_role]:
            self.error('assignment.session_ref', 'must match declared implementation session', tid)
        if role == 'validator':
            if a['validation']['candidate'] != t['base']['ref']:
                self.error('assignment.validation.candidate', 'validator must bind exact task candidate', tid)
            for dep in ancestors[tid]:
                producer = tasks[dep]
                if producer['mutation_scope']['mode'] == 'write':
                    session = producer.get('assignment', {}).get('session_ref')
                    if not session or session == a['session_ref']:
                        self.error('assignment.session_ref', 'validator needs evidenced separate implementation session', tid)


def literal_path(value):
    if not re.fullmatch(r'[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*/?', value):
        return None
    parts = value.rstrip('/').split('/')
    return None if any(x in ('.', '..') for x in parts) else parts


def overlap(a, b):
    # Parent/child reads conflict with writes too. Aliases/symlinks need human review.
    x, y = literal_path(a), literal_path(b)
    return x is None or y is None or x[:len(y)] == y or y[:len(x)] == x


def check(plan, root=ROOT, draft=False, ready_task=None, ready_wave=None, execution=False):
    try:
        policy = policies(root)
    except (OSError, ValueError, TypeError, IndexError) as exc:
        return {'result': 'NEEDS-WORK', 'dispatch_authority': False, 'diagnostics': [{'task': None, 'field': 'policy', 'message': str(exc)}]}
    c = Check(policy)
    if draft and (ready_task or ready_wave or execution):
        c.error('selection', 'draft validity cannot be combined with readiness/execution')
    parsed = c.shape(plan)
    if not c.diagnostics:
        c.semantics(parsed, draft, ready_task, ready_wave, execution)
    return {'result': 'NEEDS-WORK' if c.diagnostics else 'PASS', 'kind': 'draft' if draft else 'selected-ready' if ready_task or ready_wave else 'resolved-plan',
            'dispatch_authority': False, 'policy_provenance': policy['provenance'], 'diagnostics': c.diagnostics}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('plan', type=Path, help='JSON object, including JSON stored with .yaml extension')
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument('--draft', action='store_true', help='allow null future task refs and pending routing/gates; never readiness')
    selection.add_argument('--ready-task')
    selection.add_argument('--ready-wave')
    parser.add_argument('--execution-requested', action='store_true', help='also check selected assignment claims; grants no execution permission')
    args = parser.parse_args()
    try:
        plan = load_json(args.plan.read_text())
        result = check(plan, draft=args.draft, ready_task=args.ready_task, ready_wave=args.ready_wave, execution=args.execution_requested)
    except (OSError, ValueError, RecursionError) as exc:
        result = {'result': 'NEEDS-WORK', 'dispatch_authority': False, 'diagnostics': [{'task': None, 'field': 'input', 'message': 'JSON only; unsupported syntax or unreadable input: ' + str(exc)}]}
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result['result'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
