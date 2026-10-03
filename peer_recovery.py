"""Ask a tool-using local colleague to recover a failed controller action."""
import copy
import json
from pathlib import Path
import tempfile

from agent_support import ToolAgent, STRING, tool
from agent_repair import RepairWorkspace, REPAIR_FILES


def recover_action(context, rejected, error, *, owner, stop, root, research, request=None,
                   project=None, allow_install=True):
    from operator_runtime import (Operation, OperationStore, native_operator_action,
                                  verification_command, read_command_allowed, operator_action_schema)
    project = Path(project or Path(__file__).parent)
    from team_memory import reference
    context = {**context, 'team_procedures':reference(Path(root).parent / 'infrastructure' / 'team_learning', owner, context.get('goal_contract', {}).get('objective', 'planner recovery'))}
    if request is None:
        from planner_capacity import remote_inference
        request = lambda payload: remote_inference(payload, stop, workers=('Barbara', 'Adam'))
    workspace = RepairWorkspace(project, Path(root) / 'repairs', owner, stop)
    agent = ToolAgent(Path(root) / 'calls', owner, stop, request=request, max_turns=10, think=True,
                     tool_limits={'read_source': 3, 'search_source': 2, 'research': 2})
    action_spec = operator_action_schema([{'content': json.dumps(context)}])
    inspected, validated = set(), {}
    builtin_plan_used = False
    protocol_fast_path = bool(context.get('protocol_recovery_contract'))
    inspection_calls = 0
    def budget_inspection():
        nonlocal inspection_calls
        inspection_calls += 1
        if inspection_calls > 6:
            raise ValueError('Source inspection budget reached. Use validate_action for a correction, stage a demonstrated source repair, or finish with a validated concrete blocked action.')
    def read_source(path, start=1, lines=100):
        budget_inspection()
        result = workspace.read_source(path, start, lines)
        inspected.add(path)
        return result
    def search_source(text):
        budget_inspection()
        return workspace.search_source(text)
    def validate_action(action):
        if isinstance(action, str):
            action = json.loads(action)
        normalized = json.loads(native_operator_action({'content': json.dumps(action)}))
        name = normalized['action']
        if name not in context['allowed_actions']:
            raise ValueError('Use a currently allowed action: ' + ', '.join(context['allowed_actions']))
        if name == 'plan':
            with tempfile.TemporaryDirectory() as folder:
                op = Operation(OperationStore(folder), context['goal_contract'], owner)
                op.state = copy.deepcopy(context['state'])
                op.plan(normalized['steps'], normalized['decisions'])
        elif name == 'amend':
            verification_command(normalized)
        elif name == 'read':
            if normalized['target'] not in context['execution_targets'] or not read_command_allowed(normalized['command']):
                raise ValueError('Read action exceeds available observation tools')
        elif 'step' in normalized and normalized['step'] not in {s['id'] for s in context['state']['plan']}:
            raise ValueError('Rejected plans do not create executable steps')
        key = json.dumps(normalized, sort_keys=True)
        validated[key] = normalized
        return {'valid': True, 'action': normalized, 'execution_performed': False}
    def finish(action, lesson):
        if not inspected and not builtin_plan_used and not protocol_fast_path:
            raise ValueError('Inspect relevant source with read_source before concluding')
        if isinstance(action, str):
            action = json.loads(action)
        key = json.dumps(action, sort_keys=True)
        if key not in validated:
            raise ValueError('Use validate_action on the exact proposed action before finishing')
        result = {'action': validated[key], 'lesson_candidate': str(lesson)[:2000],
                  'support_id': agent.id, 'source_inspected': sorted(inspected)}
        if workspace.validation:
            if not allow_install:
                result['source_repair'] = {'passed': True, 'installed': False}
            else:
                result['source_repair'] = workspace.install()
        return result
    def plan_worker_observation(outcome):
        nonlocal builtin_plan_used
        worker = context['goal_contract'].get('requested_worker')
        if not context['goal_contract'].get('read_only') or worker not in {'adam', 'barbara'} or 'plan' not in context['allowed_actions']:
            raise ValueError('This helper is only available for an explicitly named read-only worker investigation')
        if not isinstance(outcome, str) or not outcome.strip():
            raise ValueError('Describe the original requested observation')
        value = validate_action({'action': 'plan', 'decisions': 'Delegate bounded observation tools and independently verify their report',
            'steps': [{'id': 'observe', 'target': 'vm202' if worker == 'adam' else 'powermox',
                       'outcome': context['goal_contract']['objective'],
                       'check': {'kind': 'json_file', 'path': 'report.json',
                                 'required_keys': ['observations', 'summary', 'limitations']}}]})
        builtin_plan_used = True
        return value
    tools = [
        tool('search_source', 'Find a symbol or exact error in source/tests before reading line ranges.', {'text': STRING}),
        tool('read_source', 'Read actual controller source or tests with line numbers.',
             {'path': STRING, 'start': {'type': 'integer'}, 'lines': {'type': 'integer'}}, ['path']),
        tool('research', 'Search public documentation or fetch an official documentation URL. Use relevant sources, not guesses.', {'query': STRING}),
        tool('validate_action', 'Dry-check a corrected action against the actual controller, without executing it.', {'action': action_spec}),
        tool('replace_source', 'Only if source is defective: stage one minimal exact-text replacement. Never weaken evidence or authorization checks.',
             {'path': STRING, 'old': STRING, 'new': STRING}),
        tool('write_regression', 'Write a unittest exposing the source defect, failing by assertion on baseline and passing after the repair.', {'source': STRING}),
        tool('select_regression', 'Reuse an existing regression instead of writing a duplicate. Supply tests.module.TestClass.test_method; it must fail baseline and pass the candidate.', {'test_case': STRING}),
        tool('test_patch', 'Run the identical regression before/after and the immutable existing suite in a networkless source-readonly sandbox.', {}),
        tool('finish', 'Return a validated next action and a lesson candidate. Source changes install only with passing controller-owned test receipts; lessons remain unverified until the operation verifies.',
             {'action': action_spec, 'lesson': STRING})]
    if context['goal_contract'].get('read_only') and context['goal_contract'].get('requested_worker') and 'plan' in context['allowed_actions']:
        tools.insert(0, tool('plan_worker_observation',
            'Recover a read-only worker investigation using the controller-owned report schema. Prefer this helper for rejected nmap/scan verification plans; no hand-written JSON check is needed.',
            {'outcome': STRING}))
    def complete_correction(name, value):
        if (
            name in {'validate_action', 'plan_worker_observation'}
            and value.get('valid')
            and (inspected or builtin_plan_used or protocol_fast_path)
            and not workspace.replacements
        ):
            # The usable artifact is the controller-validated action itself.
            # Do not require a redundant model narration turn to retain it.
            return finish(value['action'], 'A rejected planner action was corrected after source inspection and controller validation: ' + error[:500])
        return None
    try:
        recovery_instruction = (
            'The controller supplied an authoritative protocol_recovery_contract. '
            'This is an action-shape repair, not a source-debugging task. Do not '
            'search/read/patch source or research documentation unless validate_action '
            'demonstrates a genuine controller defect. Use the accepted_steps and exact '
            'action schema in that contract, construct the smallest corrected action, '
            'call validate_action once, and finish immediately if valid. Never invent '
            'expected evidence or additional fields. '
            if protocol_fast_path else
            'Read the relevant source, research documentation when needed, and validate '
            'a minimal corrected action. '
        )
        return agent.run('You are a local recovery engineer supporting Lydia. Diagnose the actual rejected action with tools. '
            + recovery_instruction +
            'Prefer correcting the action when the validator is correct. Repair source only for a demonstrated bug, '
            'with a real regression and full suite. Never remove guards, broaden original authority, fabricate '
            'expected output or substitute an easier outcome. If a required capability is absent, return an honest blocked action. '
            'For a rejected read-only worker scan plan, use plan_worker_observation directly: its schema is controller-owned and already validated. '
            'Repairable modules: ' + ', '.join(REPAIR_FILES) + '. Read-only delegation uses report.json with observations, summary, limitations.',
            {'controller': context, 'rejected_action': rejected, 'validation_error': error,
             'source_hints': {'operator_runtime.py': ['verification_command', 'run_operation'],
                              'operator_model.py': ['NativePlanner']},
             'source_index': {p: len((project / p).read_text().splitlines()) for p in REPAIR_FILES}},
            tools, {'search_source': search_source, 'read_source': read_source, 'research': lambda query: research({'query': query})[:14000],
                    'plan_worker_observation': plan_worker_observation,
                    'validate_action': validate_action, 'replace_source': workspace.replace_source,
                    'write_regression': workspace.write_regression, 'select_regression': workspace.select_regression,
                    'test_patch': workspace.test_patch, 'finish': finish}, complete_when=complete_correction)
    finally:
        workspace.close()
