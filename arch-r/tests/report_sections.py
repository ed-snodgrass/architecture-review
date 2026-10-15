"""Iteration 005 section selectors shared by older semantic regression tests."""
import re


def section(report, heading):
    return report.split('## ' + heading + '\n', 1)[1].split('\n## ', 1)[0]


def findings(report):
    """Join each card to its own guidance and evidence, not other findings."""
    def parts(heading):
        content = re.sub(r'^<a id="finding-\d+-(?:guidance|evidence)"></a>\n',
                         '', section(report, heading), flags=re.M)
        return re.findall(r'^### Finding (\d+): ([^\n]+)\n(.*?)(?=^### Finding |\Z)',
                          content, re.M | re.S)
    cards = parts('Findings')
    guidance = {n: body for n, _, body in parts('Adapter Review Guidance')}
    evidence = {n: body for n, _, body in parts('Findings with Evidence')}
    return [f'{n}: {title}\n{body}\n{guidance[n]}\n{evidence[n]}'
            for n, title, body in cards]


def finding(report, identity):
    matches = [body for body in findings(report)
               if body.split('\n', 1)[0].split(': ', 1)[1] == identity
               or f'**External system:** {identity}\n' in body]
    if len(matches) != 1:
        raise AssertionError(f'Expected one finding for {identity}: {matches}')
    return matches[0]
