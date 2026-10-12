"""Deterministic, standalone Markdown rendering of source-only findings."""

from collections.abc import Iterable

from .discovery import FeignClient, Operation
from .module import Module
from .resolution import CallLink
from .traversal import UsageTraversal


def _markdown(value: str) -> str:
    """Keep source text readable without allowing Markdown or HTML injection."""
    special = set('&<>`*_[]\\|"')
    return ''.join(f'&#{ord(char)};' if char in special or ord(char) < 32
                   or ord(char) == 127 else char for char in value)


def _diagram(value: str) -> str:
    """Mermaid numeric entities protect quoted labels and the enclosing fence."""
    return ''.join(char if char.isalnum() or char in ' ._/-:' else f'#{ord(char)};'
                   for char in value)


def _evidence(path: str, line: int) -> str:
    return _markdown(f'{path}:{line}')


def _system_name(client: FeignClient) -> str:
    if client.name:
        return client.name
    if client.name_expression:
        return f'External system name unresolved: {client.name_expression}'
    return 'External system name not specified'


def _destination(client: FeignClient) -> tuple[str, str, str]:
    if client.url and '${' in client.url:
        return (client.url + ' (destination unresolved)', 'Lower confidence',
                'The client declaration is visible, but the destination contains '
                'an unresolved property placeholder. Its value was not guessed or resolved.')
    if client.url:
        return (client.url, 'High confidence',
                'Both the client declaration and literal destination are visible in source.')
    if client.url_expression:
        return (client.url_expression + ' (destination unresolved)', 'Lower confidence',
                'The client declaration is visible, but the destination is an expression, '
                'not a literal URL. The expression was not evaluated.')
    return ('Not specified (destination unresolved)', 'Lower confidence',
            'The client declaration is visible, but no destination URL is specified. '
            'No destination was invented or resolved from configuration.')


def _operation_lines(operation: Operation) -> list[str]:
    methods = operation.methods or ('HTTP method unspecified',)
    paths = operation.paths or ('path unspecified',)
    evidence = '; '.join(_evidence(item.source_path, item.line)
                         for item in operation.evidence)
    return [f'- {_markdown(method + " " + path)} '
            f'(declared operation: {_markdown(operation.method_name)}). '
            f'Evidence: {evidence}.'
            for method in methods for path in paths]


def _link_evidence(link: CallLink) -> str:
    target = link.target_method
    method_name_line = target.declaration_line or target.line
    return (f'Invocation in {_markdown(link.caller_type + "." + link.caller_method.name)} '
            f'at {_evidence(link.invocation.source_path, link.invocation.line)}; '
            f'receiver {_markdown(link.receiver_field.name)} declared as '
            f'{_markdown(link.receiver_field.type_name)} at '
            f'{_evidence(link.receiver_field.source_path, link.receiver_field.line)}; '
            f'target method {_markdown(link.target_type + "." + link.target_method.name)} '
            f'at {_evidence(link.target_method.source_path, link.target_method.line)}; '
            f'method name at {_evidence(target.source_path, method_name_line)}.')


def _client_chains(client: FeignClient, usage: UsageTraversal):
    # Match declaration identity, not a simple name shared by different packages.
    return [chain for chain in usage.chains
            if chain.steps[0].link.target_method.source_path == client.source_path
            and chain.client_type.rsplit('.', 1)[-1] == client.interface_name]


def _relevant_diagnostics(client: FeignClient, usage: UsageTraversal):
    methods = set()
    for chain in _client_chains(client, usage):
        for step in chain.steps:
            methods.update((step.link.caller_method, step.link.target_method))
            if step.interface_connection:
                methods.add(step.interface_connection.implementation_method)
    diagnostics = tuple(item for item in usage.diagnostics
                        if item.caller_method in methods
                        or any(method in methods or method.source_path == client.source_path
                               for method in item.candidates))
    interfaces = tuple(item for item in usage.interface_diagnostics
                       if item.link.caller_method in methods
                       or item.link.target_method in methods
                       or any(method in methods
                              and method.name == item.link.target_method.name
                              and method.parameter_count == item.link.target_method.parameter_count
                              for candidate in item.candidates for method in candidate.methods))
    return diagnostics, interfaces


def _diagnostic_lines(diagnostics, interface_diagnostics) -> list[str]:
    lines = []
    for diagnostic in diagnostics:
        invocation = diagnostic.invocation
        lines.append(f'- Unresolved connection ({_markdown(diagnostic.code)}) in '
                     f'{_markdown(diagnostic.caller_type + "." + diagnostic.caller_method.name)} '
                     f'at {_evidence(invocation.source_path, invocation.line)}: '
                     f'{_markdown(diagnostic.message)}')
        for method in diagnostic.candidates:
            lines.append(f'  - Candidate method {_markdown(method.name)}: '
                         f'{_evidence(method.source_path, method.line)}.')
    for diagnostic in interface_diagnostics:
        lines.append(f'- Unresolved interface connection ({_markdown(diagnostic.code)}): '
                     + _link_evidence(diagnostic.link)
                     + ' ' + _markdown(diagnostic.message))
        for candidate in diagnostic.candidates:
            lines.append(f'  - Candidate {_markdown(candidate.qualified_name)} declaration: '
                         f'{_evidence(candidate.source_path, candidate.line)}.')
    return lines


def _usage_lines(client: FeignClient, usage: UsageTraversal) -> list[str]:
    chains = _client_chains(client, usage)
    lines = ['', '### How the code uses this connection', '',
             'Source calls show possible behavior, not proof of execution. '
             'Observed usage describes source invocations only; destination confidence '
             'is separate from usage certainty.',
             f'The applied traversal limit is {usage.max_depth} call steps; '
             'the outbound HTTP connection and interface resolution do not count as steps.', '']
    if not chains:
        lines.append('No supported caller was found within the analyzed module and supported '
                     'call forms. This does not establish that the client is unused.')
    for number, chain in enumerate(chains, 1):
        steps = tuple(reversed(chain.steps))
        names = [steps[0].link.caller_type]
        for step in steps:
            connection = step.interface_connection
            names.append(connection.implementation_type.qualified_name if connection
                         else step.link.target_type)
        label = 'Possible chain' if chain.certainty == 'possible' else 'Observed source chain'
        direct = chain.steps[0].link.caller_type
        lines.append(f'- Chain {number} — {label}: {_markdown(" → ".join(names))}. '
                     f'{_markdown(direct)} calls the Feign integration point directly.')
        if len(steps) > 1:
            lines.append(f'  {_markdown(direct)} is an intermediary between the upstream '
                         'calling code and this client; this describes the observed '
                         'relationship, not a business responsibility inferred from its name.')
        for step in steps:
            if step.interface_connection:
                connection = step.interface_connection
                lines.append(f'  Possible connection through '
                             f'{_markdown(connection.interface_type.qualified_name)} to '
                             f'{_markdown(connection.implementation_type.qualified_name)}: '
                             f'{_markdown(connection.reason)} The entire chain remains possible.')
    lines.extend(['', '### Evidence and uncertainty', ''])
    if not chains:
        lines.append('No supported invocation evidence establishes a caller chain for this '
                     'client within the analysis boundary. Declarations alone are not usage.')
    for number, chain in enumerate(chains, 1):
        lines.append(f'- Chain {number}:')
        for step in reversed(chain.steps):
            lines.append(f'  - {"Possible connection" if step.certainty == "possible" else "Observed call"}: '
                         + _link_evidence(step.link))
            if step.interface_connection:
                connection = step.interface_connection
                implementation = connection.implementation_type
                method = connection.implementation_method
                lines.append(f'    Interface declaration: '
                             f'{_evidence(connection.interface_type.source_path, connection.interface_type.line)}; '
                             f'implementation declaration {_markdown(implementation.qualified_name)}: '
                             f'{_evidence(implementation.source_path, implementation.line)}; '
                             f'implementing method {_markdown(method.name)}: '
                             f'{_evidence(method.source_path, method.declaration_line or method.line)}. Runtime wiring is unverified.')
        if chain.boundary:
            lines.append('  - ' + _markdown(chain.boundary_reason))
        if chain.cycle_link:
            lines.append('  - Cycle cutoff invocation: ' + _link_evidence(chain.cycle_link))

    diagnostics, interfaces = _relevant_diagnostics(client, usage)
    if diagnostics or interfaces:
        lines.append('Relevant unresolved connections follow; these do not establish '
                     'additional routes to this Feign client:')
        lines.extend(_diagnostic_lines(diagnostics, interfaces))
    return lines


def render_report(module: Module, clients: Iterable[FeignClient],
                  usage: UsageTraversal | None = None) -> str:
    """Render supplied source findings without writing or performing analysis."""
    ordered = sorted(clients, key=lambda c: (c.source_path, c.line, c.interface_name))
    name = _markdown(module.name)
    lines = [f'# Outbound HTTP dependencies: {name}', '',
             f'**Module:** {name}', f'**Module path:** {_markdown(str(module.path))}', '',
             '## Summary', '']
    if ordered:
        count = len(ordered)
        noun = 'dependency' if count == 1 else 'dependencies'
        lines.append(f'Found {count} statically declared Feign outbound HTTP {noun}.')
    else:
        lines.extend(['No statically declared Feign outbound HTTP dependencies were found.',
                      'This does not mean the module makes no outbound calls by other means.'])
    for index, client in enumerate(ordered, 1):
        system = _markdown(_system_name(client))
        destination, confidence, reason = _destination(client)
        lines.extend(['', f'## Finding {index}: {system}', '',
                      f'{name} makes an outbound HTTP connection to {system} '
                      f'through its {_markdown(client.interface_name)} Feign integration point.', '',
                      f'- **External system:** {system}',
                      f'- **Destination:** {_markdown(destination)}',
                      f'- **Confidence:** {confidence}. {reason}',
                      f'- **Client declaration evidence:** {_evidence(client.source_path, client.line)}',
                      '', '### HTTP operations (supporting detail)', ''])
        if client.operations:
            for operation in client.operations:
                lines.extend(_operation_lines(operation))
        else:
            lines.append('No supported mapped HTTP operations were discovered in this interface; '
                         'this does not prove that it has no operations.')
        if usage is not None:
            lines.extend(_usage_lines(client, usage))
    if usage is not None:
        relevant = [_relevant_diagnostics(client, usage) for client in ordered]
        diagnostics = tuple(item for item in usage.diagnostics
                            if not any(item in group[0] for group in relevant))
        interfaces = tuple(item for item in usage.interface_diagnostics
                           if not any(item in group[1] for group in relevant))
        if diagnostics or interfaces:
            lines.extend(['', '## Module-wide unresolved connections', '',
                          'These diagnostics are module context, not established routes '
                          'to any reported Feign client.', ''])
            lines.extend(_diagnostic_lines(diagnostics, interfaces))
    lines.extend(['', '## Architectural connections', '', '```mermaid', 'C4Context',
                  f'    System(module, "{_diagram(module.name)}", "Analyzed Java/Spring module")'])
    for index, client in enumerate(ordered, 1):
        lines.extend([
            f'    Container(feign_{index}, "{_diagram(client.interface_name)}", '
            '"OpenFeign", "HTTP integration point")',
            f'    System_Ext(external_{index}, "{_diagram(_system_name(client))}", "External HTTP system")',
            f'    Rel(module, feign_{index}, "Declares HTTP integration")',
            f'    Rel(feign_{index}, external_{index}, "Outbound HTTP")',
        ])
    lines.extend(['```', '', '## Limitations', '',
                  'ArchR analyzed Java source declarations only; it did not compile, run, or '
                  'modify the module. It did not resolve configuration or property placeholders.', '',
                  ('ArchR did not inspect callers and therefore did not determine whether a '
                   'separate domain-facing port or adapter is needed. A Feign integration point '
                   'is not assumed to be a sufficient architectural adapter.' if usage is None else
                   'Usage is source-only: runtime wiring and execution were not verified. '
                   'A Feign integration point is not assumed to be a sufficient architectural adapter.'), '',
                  'Only supported Spring OpenFeign declarations and mapping annotations are '
                  'reported. Other outbound HTTP mechanisms, messaging, databases, inherited '
                  'operations, and runtime behavior are outside this analysis.', ''])
    return '\n'.join(lines)
