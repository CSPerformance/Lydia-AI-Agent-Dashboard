"""Independent outcome checks for the diagnostic acceptance exercise.

These checks are authored by the evaluator, not by the planner under test.
A model-selected substring check cannot establish diagnostic correctness.
"""
import xml.etree.ElementTree as ET
import re
import ipaddress


def diagnostic_values(report):
    """Accept unambiguous semantic field names; the brief specifies no JSON schema."""
    def field(names):
        values = [report[name] for name in names if name in report]
        if len(values) != 1:
            return None
        return values[0]
    ram = field(('ram_bytes', 'available_ram_bytes', 'available_memory_bytes'))
    addresses = field(('ipv4_addresses', 'ipv4_interfaces'))
    if not isinstance(addresses, list):
        return ram, None
    normalized = []
    for item in addresses:
        if isinstance(item, dict):
            choices = [item[key] for key in ('address','ip','local') if key in item]
            item = choices[0] if len(choices) == 1 else None
        if not isinstance(item, str):
            return ram, None
        try:
            normalized.append(str(ipaddress.IPv4Interface(item).ip))
        except ValueError:
            return ram, None
    return ram, normalized


def diagnostic_errors(report, observed):
    errors = []
    if observed.get('report_predates_script'):
        errors.append('Saved report predates the current script: execute the revised script and regenerate its output before verification')
    if not isinstance(report, dict):
        return ['Report is not a JSON object']
    if report.get('hostname') != observed['hostname']:
        errors.append('Hostname does not match independently observed guest')
    ram, addresses = diagnostic_values(report)
    available = observed['available_bytes']
    # Sampling follows execution, so allow normal memory movement while still
    # rejecting kB/MiB, zero, total-RAM substitutions and nonsensical values.
    tolerance = max(512 * 1024**2, available * .05)
    if (type(ram) is not int or ram <= 0 or ram > observed['total_bytes']
            or abs(ram - available) > tolerance):
        errors.append('Available RAM is not a plausible current byte measurement')
    if (not isinstance(addresses, list)
            or not all(isinstance(item, str) for item in addresses)
            or set(addresses) != set(observed['ipv4_addresses'])):
        errors.append('IPv4 list does not match all independently observed interfaces')
    return errors


def topology_errors(svg):
    """A fixed representative diagram brief; semantic checks precede visual review."""
    if not isinstance(svg, str) or len(svg) > 200000 or '<!DOCTYPE' in svg.upper():
        return ['Missing or invalid bounded SVG artifact']
    external_css = re.sub(r'''url\(\s*(['"]?)(\#[A-Za-z_][\w.-]*)\1\s*\)''', '', svg, flags=re.I)
    if re.search(r'url\s*\(|@import', external_css, re.I):
        return ['Diagram contains external CSS references']
    try:
        root = ET.fromstring(svg)
    except ET.ParseError:
        return ['Artifact is not valid XML']
    if root.tag.split('}')[-1] != 'svg':
        return ['Artifact is not SVG']
    for node in root.iter():
        if node.tag.split('}')[-1].lower() in {'script','foreignobject'}:
            return ['Diagram contains active content']
        if any(key.lower().startswith('on') or key.split('}')[-1].lower() == 'href'
               for key in node.attrib):
            return ['Diagram contains active or external references']
        if node.tag.split('}')[-1] in {'rect','circle','ellipse','line','path','polygon','polyline'}:
            if any(child.tag.split('}')[-1] in {'text','tspan'} for child in node):
                return ['SVG text nested inside a shape will not render as a visible label']
    text = ' '.join(root.itertext()).lower()
    labels = ('powerlydia','a770','powermox','adam','titan','barbara','1070','delegation')
    missing = [label for label in labels if label not in text]
    return ['Missing diagram labels: '+', '.join(missing)] if missing else []
