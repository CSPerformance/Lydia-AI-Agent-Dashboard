"""Lydia's bounded research repair: reproduce, patch, test, install, retain.

The model cannot edit the main tool broker, credentials, authority boundaries,
existing tests, or arbitrary files. Code runs only in the existing networkless
repair sandbox before controller-owned installation.
"""
import importlib
import hashlib
import json
from pathlib import Path
import threading

from agent_support import ToolAgent, tool, STRING, save_record
from agent_repair import RepairWorkspace
from research_workflows import context
from team_memory import TeamMemory

RESEARCH_FILES={'research_workflows.py','web_research.py','team_research.py'}


def repair_research(failure, owner, root, search, fetch, *, worker='adam', stop=None, request=None, project=None):
    root=Path(root)
    stop=stop or threading.Event()
    workspace=RepairWorkspace(project or Path(__file__).parent,root/'repairs',owner,stop)
    agent=ToolAgent(root/'repair_workers'/worker,owner,stop,worker=worker,request=request,
                    max_turns=14,tool_limits={'web_search':3,'web_fetch':3,'test_patch':2})
    def read_source(path, start):
        if path not in RESEARCH_FILES and not path.startswith('tests/'):
            raise ValueError('Read research helpers or regression tests only')
        return workspace.read_source(path,int(start),100)
    def replace_source(path, old, new):
        if path not in RESEARCH_FILES:raise ValueError('Only the research helper modules may be repaired')
        return workspace.replace_source(path,old,new)
    def finish(lesson):
        if not workspace.validation:raise ValueError('A baseline-failing regression and passing complete suite are required')
        result=workspace.install()
        # These helpers are looked up dynamically by Lydia's broker. Loading
        # the tested modules makes subsequent requests use the repair.
        for filename in sorted(RESEARCH_FILES):
            importlib.reload(importlib.import_module(filename[:-3]))
        checks=[{'passed':True,'receipt_sha256':workspace.validation['suite']['output_sha256']}]
        hashes={filename:hashlib.sha256((workspace.project/filename).read_bytes()).hexdigest() for filename in RESEARCH_FILES if filename in workspace.before}
        save_record(root/'approved-repair.json',{'hashes':hashes,'repair':result})
        TeamMemory(root.parent/'infrastructure'/'team_learning').record_acceptance(owner,
            'Verified research recovery regression',
            'A reproducible research defect was repaired. Reuse the stored regression and verify current behavior; the worker lesson remains a candidate: '+lesson,
            checks,hashes)
        return {'repair':result,'worker_lesson_candidate':lesson,'support_id':agent.id,'verified_regression':workspace.validation}
    try:
        return agent.run('You are assisting Lydia with a demonstrated research defect. Inspect relevant source and evidence. '
            'Use public research if the method is unknown. Stage a small general repair, then a regression reproducing the real defect. '
            'The unchanged regression must fail on baseline and pass on candidate; the frozen full suite must pass. '
            'Never weaken evidence checks, change the task, skip tests, or claim success from prose. '
            'Use finish only after test_patch returns passed. If the defect cannot be repaired within your tools, report incomplete honestly.',
            {'failure_evidence':failure,'workflow':context(root,str(failure)[:1000]),'repairable_files':sorted(RESEARCH_FILES)},
            [tool('read_source','Read source or a frozen test.',{'path':STRING,'start':{'type':'integer'}}),
             tool('web_search','Research a sanitized public error or unfamiliar method.',{'query':STRING}),
             tool('web_fetch','Read public technical documentation.',{'url':STRING}),
             tool('replace_source','Stage a bounded exact replacement in a research helper.',{'path':STRING,'old':STRING,'new':STRING}),
             tool('write_regression','Write a regression that demonstrates this defect.',{'source':STRING}),
             tool('test_patch','Run baseline, candidate and frozen full suite in isolation.',{}),
             tool('finish','Install only a fully validated repair and retain its lesson.',{'lesson':STRING})],
            {'read_source':read_source,'web_search':lambda query:search(query,4),'web_fetch':lambda url:fetch(url,12000),
             'replace_source':replace_source,'write_regression':workspace.write_regression,
             'test_patch':workspace.test_patch,'finish':finish})
    finally:
        workspace.close()


_RELOAD_LOCK=threading.Lock()
_LOADED_RECEIPT=None


def refresh_verified_helpers(root):
    """Let Lydia adopt a tested helper repair on the next request without restart."""
    global _LOADED_RECEIPT
    path=Path(root)/'approved-repair.json'
    if not path.is_file():return False
    with _RELOAD_LOCK:
        try:
            raw=path.read_bytes()
            digest=hashlib.sha256(raw).hexdigest()
            if digest==_LOADED_RECEIPT:return False
            record=json.loads(raw)
            hashes=record['hashes']
            project=Path(__file__).parent
            if not isinstance(hashes,dict) or not hashes or set(hashes)-RESEARCH_FILES:return False
            if any(hashlib.sha256((project/name).read_bytes()).hexdigest()!=value for name,value in hashes.items()):return False
            for filename in sorted(hashes):importlib.reload(importlib.import_module(filename[:-3]))
            _LOADED_RECEIPT=digest
            return True
        except (OSError,ValueError,KeyError,TypeError):
            return False
