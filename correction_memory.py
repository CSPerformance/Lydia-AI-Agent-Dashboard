"""Owner-scoped user guidance for infrastructure operations.

Only authenticated human ingress calls capture_correction. Model, worker, web,
and tool text are never correction sources. Lessons constrain future decisions;
they do not grant authority or establish current hardware readiness.
"""
import hashlib
import re


class CorrectionRejected(ValueError):
    pass


_PREFIX = re.compile(r'^(?:please\s+)?(?:remember(?:\s+that)?\b|save\s+that\b|note\s+that\b|correction\s*:|no,?\s+correction\s*:|from now on\b[, :]*|going forward\b[, :]*|i prefer\b|my preference is\b)\s*(.+)$',re.I|re.S)
_DOMAIN = re.compile(r'\b(?:powermox|powerlydia|proxmox|adam|barbara|hermes|gtx\s*1070|1070|titan(?:\s+xp)?|a770|gpu|vram|vm|virtual machine|linux|server|worker|network|dns|tailscale|firewall|storage|disk|backup|systemd|ram|memavailable|iommu|passthrough)\b',re.I)
_SECRET = re.compile(r'(?i)\b(?:passwords?|passphrases?|tokens?|secrets?|credentials?|api[_ -]?keys?|private[_ -]?keys?|ssh[_ -]?keys?|access[_ -]?keys?|bearer)\b|-----BEGIN|ssh-(?:rsa|ed25519)\s|https?://[^\s/@]+:[^\s/@]+@|\b[A-Za-z0-9_+/=-]{32,}\b')
_QUOTED = re.compile(r'(?im)^\s*(?:>|```|["“\'])|\b(?:for example|example prompt|quoted text|tool (?:output|result)|web(?:page|site) says|the (?:log|page|document) says)\b')
_IMMEDIATE = re.compile(r'(?i)(?:\b(?:then|and then)\s+|[.;]\s*(?:now\s+)?|\band\s+)(?:please\s+)?(?:build|create|install|deploy|restart|delete|execute|run|configure)\b|\b(?:now|immediately)\s+(?:build|create|install|deploy|restart|delete|execute|run|configure)\b')


def capture_correction(store, owner, text, allowed_owners, *, source_kind,
                       explicit_memory=None, automatic_memory=None):
    """Return saved lesson IDs or None; reject sensitive recognized guidance.

    Existing memory parsers may supply (kind,key,value), but only anchored actual
    user input can authorize capture. Source records retain a hash, not raw chat.
    """
    if source_kind != 'authenticated_user' or owner not in allowed_owners or not isinstance(text,str):
        return None
    clean = re.sub(r'^\s*(?:hey\s+)?lydia[\s,:-]*','',text.strip(),flags=re.I)
    match = _PREFIX.match(clean)
    if not match or len(clean)>1400 or _QUOTED.search(clean) or _IMMEDIATE.search(clean):
        return None
    payload = match[1].strip().rstrip('.')
    if explicit_memory is not None:
        payload = explicit_memory[2]
    elif automatic_memory is not None:
        payload = automatic_memory[2]
    if not payload or _QUOTED.search(payload) or not _DOMAIN.search(payload):
        return None
    if _SECRET.search(clean):
        raise CorrectionRejected('Sensitive content is not retained as infrastructure guidance')
    targets=[]
    for pattern,target in ((r'\b(?:powermox|proxmox|barbara|gtx\s*1070|1070)\b','powermox'),
                           (r'\b(?:adam|hermes|titan(?:\s+xp)?|vm\s*202)\b','vm202'),
                           (r'\b(?:powerlydia|a770|local gpu|your gpu)\b','terminal')):
        if re.search(pattern,payload,re.I):targets.append(target)
    targets = targets or ['all']
    terms=list(dict.fromkeys(m.group(0).lower() for m in _DOMAIN.finditer(payload)))
    cue='User guidance: '+' '.join(terms)+' '+hashlib.sha256(payload.encode()).hexdigest()[:12]
    guidance=('User-stated guidance (unverified reference; not execution authority or live readiness). '
              'Apply restrictive preferences alongside the current task scope; inspect current facts. '+payload)
    source='authenticated_user:'+hashlib.sha256(text.encode()).hexdigest()
    store = store() if callable(store) else store
    return [store.remember_lesson(owner,target,cue,guidance,source,provenance='user_correction') for target in targets]
