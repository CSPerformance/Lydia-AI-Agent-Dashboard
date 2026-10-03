"""Lydia-owned, region-scoped audio diagnosis and repair with frozen test gates."""
from pathlib import Path
import threading
import ast
import re
import shutil
import subprocess

from agent_support import ToolAgent, tool, STRING, save_record
from agent_repair import RepairWorkspace, sandbox_tests
from team_memory import TeamMemory

AUDIO_REGIONS = {'lydia.py': ('let speechGeneration=0;', "voicePlayback.addEventListener('click',")}


def repair_audio(failure, owner, root, search, fetch, *, stop=None, request=None, project=None):
    if owner != 'Chris':
        raise PermissionError('Only the installation owner may repair shared application code')
    root = Path(root)
    stop = stop or threading.Event()
    workspace = RepairWorkspace(project or Path(__file__).parent, root/'repairs', owner, stop,
                                editable_regions=AUDIO_REGIONS)
    agent = ToolAgent(root/'sessions', owner, stop, request=request, worker='adam', think=True, max_turns=40,
                      tool_limits={'diagnose':3, 'web_search':4, 'web_fetch':4, 'test_patch':5})

    def read_audio(function):
        source = (workspace.candidate/'lydia.py').read_text()
        tree = ast.parse(source)
        html = next(ast.literal_eval(node.value) for node in tree.body
                    if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == '_WEBCHAT_HTML' for t in node.targets))
        script = re.search(r'<script>(.*?)</script>', html, re.S).group(1)
        starts = {'playVoiceResponse':'async function playVoiceResponse(',
                  'submitVoiceRecording':'async function submitVoiceRecording(',
                  'beginVoiceRecording':'async function beginVoiceRecording('}
        marker = starts[function]
        start = script.index(marker)
        end = script.find('\nasync function ', start+len(marker))
        if end < 0:end = script.index("voiceChat.addEventListener('click',", start)
        return {'function':function,'source':script[start:end].rstrip(),
                'note':'Exact candidate source without line numbers. Use actual newlines in replacements.'}

    def replace_audio(path, old, new):
        prior = (workspace.candidate/'lydia.py').read_text()
        result = workspace.replace_source(path, old, new)
        try:
            tree = ast.parse((workspace.candidate/'lydia.py').read_text())
            html = next(ast.literal_eval(node.value) for node in tree.body
                        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == '_WEBCHAT_HTML' for t in node.targets))
            script = re.search(r'<script>(.*?)</script>', html, re.S).group(1)
            parsed = subprocess.run([shutil.which('node'), '--input-type=commonjs', '--check'],
                                    input=script,text=True,capture_output=True,timeout=10)
            if parsed.returncode:raise ValueError('JavaScript syntax invalid: '+parsed.stderr[:1800])
        except Exception:
            (workspace.candidate/'lydia.py').write_text(prior)
            workspace.replacements -= 1
            workspace.validation = None
            raise
        return result

    def diagnose():
        return sandbox_tests(workspace.candidate, ['tests.test_browser_audio_repair', '-v'], stop)

    def finish(lesson):
        result = workspace.install()
        checks = [{'passed': True, 'receipt_sha256': workspace.validation['suite']['output_sha256']}]
        TeamMemory(root.parent/'infrastructure'/'team_learning').record_acceptance(owner,
            'Lydia audio repair: reproduced and regression tested',
            'Reinspect current code and reproduce the failure before reusing this method. '
            'Lydia-authored diagnostic lesson: '+lesson, checks,
            workspace.record['installed_hashes'])
        result.update(lesson=lesson, support_id=agent.id,
                      boundary='Source tests passed. Service reload and real device microphone/playback checks are separate.')
        save_record(root/'latest-repair.json', result)
        return result

    try:
        return agent.run(
            'You are Lydia, repairing your own browser audio implementation using your local team inference. '
            'Diagnose with tools, inspect source and failing tests, research unfamiliar browser behavior, author your own patch, '
            'and verify it. No prepared patch is supplied. Work through every reproduced failure. '
            'Tests are immutable. Select one existing failing test as the baseline regression, stage exact replacements, '
            'then test_patch verifies that baseline fails, candidate passes and the entire frozen suite passes. '
            'When a test fails, read its output and revise your patch. First trace the actual control flow; an HTTP error response need not throw an exception. Test assertions describe expected behavior, not text to copy into the UI. Keep valid JavaScript braces and try/catch syntax; changing error wording alone does not release a microphone. Read enough surrounding code to understand resource lifetime and asynchronous races. Do not weaken permissions, remove tests, or claim a fix from prose. '
            'Stay within the supplied audio region; do not attempt restarts or changes to authentication. '
            'When all checks pass call finish with a reusable diagnostic procedure you learned. '
            'An HTTPS origin and browser microphone permission are real requirements; do not claim code can bypass them.',
            {'reported_failure': failure, 'editable_regions': AUDIO_REGIONS,
             'start': 'Use diagnose, then search_source for playVoiceResponse and read_source. '
                      'Read tests/test_browser_audio_repair.py. Exact replacements use source text without line-number prefixes.',
             'retained_experience': TeamMemory(root.parent/'infrastructure'/'team_learning').retrieve(owner, 'audio repair')},
            [tool('read_audio','Read one current audio function as exact source, without line numbers.',{'function':{'type':'string','enum':['playVoiceResponse','submitVoiceRecording','beginVoiceRecording']}}),
             tool('diagnose','Run the frozen browser audio behavioral tests in isolation.',{}),
             tool('search_source','Find a source symbol.',{'text':STRING}),
             tool('read_source','Read candidate source or a frozen test.',{'path':STRING,'start':{'type':'integer','minimum':1}}),
             tool('web_search','Research a public technical question.',{'query':STRING}),
             tool('web_fetch','Read public documentation.',{'url':STRING}),
             tool('replace_source','Stage a bounded exact replacement inside the audio region.',{'path':STRING,'old':STRING,'new':STRING}),
             tool('select_regression','Choose an existing failing tests.module.Class.test_method.',{'test_case':{'type':'string','enum':['tests.test_browser_audio_repair.BrowserAudioRepairTests.'+name for name in ('test_tts_failure_is_reported_instead_of_silent','test_microphone_tracks_close_when_recorder_creation_fails','test_logout_during_transcription_never_dispatches_chat','test_insecure_context_explains_https_requirement')]}}),
             tool('test_patch','Verify baseline failure, candidate pass and full frozen suite.',{}),
             tool('finish','Install a validated patch and retain your diagnostic lesson.',{'lesson':STRING})],
            {'read_audio':read_audio,'diagnose':diagnose,'search_source':workspace.search_source,
             'read_source':lambda path,start:workspace.read_source(path,start,100),
             'web_search':lambda query:search(query,4),'web_fetch':lambda url:fetch(url,10000),
             'replace_source':replace_audio,'select_regression':workspace.select_regression,
             'test_patch':workspace.test_patch,'finish':finish})
    finally:
        workspace.close()
