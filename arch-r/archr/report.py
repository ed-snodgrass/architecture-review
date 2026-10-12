"""Deterministic, standalone Markdown rendering of source-only findings."""

from collections.abc import Iterable

from .discovery import FeignClient, Operation
from .module import Module


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


def render_report(module: Module, clients: Iterable[FeignClient]) -> str:
    """Render without writing files, resolving configuration, or inspecting callers."""
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
                  'ArchR did not inspect callers and therefore did not determine whether a '
                  'separate domain-facing port or adapter is needed. A Feign integration point '
                  'is not assumed to be a sufficient architectural adapter.', '',
                  'Only supported Spring OpenFeign declarations and mapping annotations are '
                  'reported. Other outbound HTTP mechanisms, messaging, databases, inherited '
                  'operations, and runtime behavior are outside this analysis.', ''])
    return '\n'.join(lines)
