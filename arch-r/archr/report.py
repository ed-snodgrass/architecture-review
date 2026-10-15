"""Deterministic, standalone Markdown rendering of source-only findings."""

from collections import Counter
from collections.abc import Iterable

from .discovery import FeignClient, Operation
from .module import Module
from .findings import IntegrationFinding
from .queries import QueryEvidence
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


def _query_lines(query: QueryEvidence) -> list[str]:
    """Render only retained bounded evidence, never invocation source text.

    JDBC and repository findings share this path, including unresolved values.
    Escape after truncation: Markdown entities do not consume preview characters.
    """
    value = (_markdown(query.preview) if query.preview is not None
             else 'Unresolved query expression (not evaluated)')
    return [f'- **{_markdown(query.language)}:** {value}. '
            f'Evidence: {_evidence(query.source_path, query.line)}.']


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


def _integration_call_evidence(link: CallLink, finding: IntegrationFinding) -> str:
    """Endpoint citations identify declarations, not invented library source."""
    declaration = finding.declaration
    return (f'Invocation in {_markdown(link.caller_type + "." + link.caller_method.name)} '
            f'at {_evidence(link.invocation.source_path, link.invocation.line)}; '
            f'receiver {_markdown(link.receiver_field.name)} declared as '
            f'{_markdown(link.receiver_field.type_name)} at '
            f'{_evidence(link.receiver_field.source_path, link.receiver_field.line)}; '
            f'recognized operation {_markdown(link.target_type + "." + link.target_method.name)}. '
            f'Integration declaration: {_evidence(declaration.source_path, declaration.line)}. '
            'Library source and runtime execution were not inspected.')


def _client_chains(client: FeignClient | IntegrationFinding, usage: UsageTraversal):
    if isinstance(client, IntegrationFinding):
        return client.chains
    # Match declaration identity, not a simple name shared by different packages.
    return [chain for chain in usage.chains
            if chain.steps[0].link.target_method.source_path == client.source_path
            and chain.client_type.rsplit('.', 1)[-1] == client.interface_name]


def _relevant_diagnostics(client: FeignClient | IntegrationFinding, usage: UsageTraversal):
    methods = set()
    for chain in _client_chains(client, usage):
        for step in chain.steps:
            methods.update((step.link.caller_method, step.link.target_method))
            if step.interface_connection:
                methods.add(step.interface_connection.implementation_method)
    # A failed call is relevant only through its resolved field type or
    # candidate endpoints on this client's route. Sharing a caller method or
    # source file with the integration is not receiver/type evidence.
    def relevant_call(item):
        if item.receiver_field is None:
            return False
        if isinstance(client, IntegrationFinding):
            declaration = client.declaration
            matches = (item.receiver_field.type_name == declaration.type_name
                       and (declaration.field_name is None or
                            (item.caller_type == declaration.declaring_type and
                             item.receiver_field.name == declaration.field_name)))
        else:
            matches = item.receiver_field.type_name == client.qualified_name
        return matches or not methods.isdisjoint(item.candidates)

    def relevant_interface(item):
        if item.link.target_method in methods:
            return True
        # Ambiguous implementations are not traversed. A candidate's exact
        # implementing method on the route still connects this uncertainty to
        # the client; other methods in the same class do not.
        target = item.link.target_method
        return any(method in methods
                   and method.name == target.name
                   and method.parameter_count == target.parameter_count
                   for candidate in item.candidates for method in candidate.methods)

    diagnostics = tuple(item for item in usage.diagnostics if relevant_call(item))
    interfaces = tuple(item for item in usage.interface_diagnostics
                       if relevant_interface(item))
    return diagnostics, interfaces


def _diagnostic_lines(diagnostics, interface_diagnostics) -> list[str]:
    lines = []
    for diagnostic in diagnostics:
        invocation = diagnostic.invocation
        lines.append(f'- Unresolved connection ({_markdown(diagnostic.code)}) in '
                     f'{_markdown(diagnostic.caller_type + "." + diagnostic.caller_method.name)} '
                     f'at {_evidence(invocation.source_path, invocation.line)} '
                     f'({_markdown(invocation.receiver + "." + invocation.method_name)}): '
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


def _usage_lines(client: FeignClient | IntegrationFinding, usage: UsageTraversal) -> list[str]:
    chains = _client_chains(client, usage)
    integration = ('declared integration' if isinstance(client, IntegrationFinding)
                   else 'Feign integration point')
    lines = ['', '### How the code uses this connection', '',
             'Source calls show possible behavior, not proof of execution. '
             'Observed usage describes source invocations only; destination confidence '
             'is separate from usage certainty.',
             f'The applied traversal limit is {usage.max_depth} call steps; '
             'the external connection and interface resolution do not count as steps.', '']
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
        if isinstance(client, IntegrationFinding):
            declaration = client.declaration
            names[-1] = declaration.declaring_type + (
                '.' + declaration.field_name if declaration.field_name else '')
        label = 'Possible chain' if chain.certainty == 'possible' else 'Observed source chain'
        direct = chain.steps[0].link.caller_type
        lines.append(f'- Chain {number} — {label}: {_markdown(" → ".join(names))}. '
                     f'{_markdown(direct)} calls the {integration} directly.')
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
                         + (_integration_call_evidence(step.link, client)
                            if isinstance(client, IntegrationFinding) and step is chain.steps[0]
                            else _link_evidence(step.link)))
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
                     'additional routes to this integration:')
        lines.extend(_diagnostic_lines(diagnostics, interfaces))
    return lines


def _adapter_guidance_lines(client: FeignClient | IntegrationFinding,
                            usage: UsageTraversal) -> list[str]:
    """Suggest reviews only for supported arrangements, never architectural verdicts."""
    lines = ['', '### Where an adapter could fit', '']
    chains = _client_chains(client, usage)
    expanded = isinstance(client, IntegrationFinding)
    details = ('integration details' if expanded else 'HTTP details')
    dependency = ('declared integration' if expanded else 'Feign dependency')
    if not chains:
        lines.append('No supported caller was found within the analysis boundary. '
                     'No specific adapter placement recommendation can be made from '
                     f'this evidence; the {dependency} remains reported.')
        return lines

    # Repeated methods and call sites keep their evidence above, but need not
    # repeat identical placement advice. Preserve the traversal's stable order.
    suggestions = []
    for chain in chains:
        direct = _markdown(chain.steps[0].link.caller_type)
        if expanded:
            declaration = client.declaration
            client_name = _markdown(declaration.declaring_type + (
                '.' + declaration.field_name if declaration.field_name else ''))
        else:
            client_name = _markdown(chain.client_type)
        conditions = []
        for step in reversed(chain.steps):
            connection = step.interface_connection
            if connection:
                conditions.append(
                    f'verify that runtime wiring connects '
                    f'{_markdown(step.link.caller_type)} through '
                    f'{_markdown(connection.interface_type.qualified_name)} to '
                    f'{_markdown(connection.implementation_type.qualified_name)}')
        condition = ('First, ' + '; '.join(conditions) + '. '
                     'If this possible wiring is confirmed, the following review applies. '
                     if conditions else '')
        if len(chain.steps) > 1:
            upstream = _markdown(chain.steps[-1].link.caller_type)
            advice = (f'{direct}, between {upstream} and {client_name}, is a candidate '
                      'adapter location. Review whether its interface expresses the '
                      f'calling code\'s needs and keeps {details} out of calling code. '
                      'Wrapping an integration alone does not establish adequate isolation.')
        else:
            advice = (f'Review whether {direct}, which calls {client_name} directly, '
                      'also handles business decisions. If so, a domain-facing interface '
                      f'between that calling code and the {dependency} could isolate '
                      f'external-service and {details}. The direct caller may itself '
                      'serve as an adapter; direct use alone is not an architectural defect.')
        suggestion = '- **Suggestion:** ' + condition + advice
        if suggestion not in suggestions:
            suggestions.append(suggestion)
    lines.extend(suggestions)
    return lines


def _feign_labels(clients: list[FeignClient]) -> list[str]:
    """Retain short labels unless multiple declarations share that name."""
    counts = Counter(client.interface_name for client in clients)
    return [client.qualified_name or client.interface_name
            if counts[client.interface_name] > 1 else client.interface_name
            for client in clients]


def _usage_diagram_lines(module: Module, clients: list[FeignClient],
                         usage: UsageTraversal) -> list[str]:
    """Summarize only displayed method-level routes as shared class edges.

    Interface resolution redirects a possible edge to its candidate class;
    unresolved routes and proposed adapters never become diagram components.
    Evidence remains in the findings, independently of edge deduplication.
    """
    chains = [chain for client in clients for chain in _client_chains(client, usage)]
    feign_ids = {}
    for index, client in enumerate(clients, 1):
        for chain in _client_chains(client, usage):
            feign_ids[chain.client_type] = f'feign_{index}'

    class_names = set()
    relationships = {}
    for chain in chains:
        for step in chain.steps:
            link = step.link
            connection = step.interface_connection
            target = (connection.implementation_type.qualified_name
                      if connection else link.target_type)
            class_names.add(link.caller_type)
            if target not in feign_ids:
                class_names.add(target)
            label = (f'Possible connection through {connection.interface_type.qualified_name} '
                     '(runtime wiring unverified)' if connection else 'Observed call')
            relationships.setdefault((link.caller_type, target), set()).add(label)
    # A Feign declaration can itself contain calling code (for example a
    # default method); reuse its integration node rather than declaring it twice.
    class_names.difference_update(feign_ids)
    node_ids = {name: f'class_{index}'
                for index, name in enumerate(sorted(class_names), 1)}
    node_ids.update(feign_ids)

    lines = ['C4Context',
             f'    System(module, "{_diagram(module.name)}", "Analyzed Java/Spring module")',
             f'    System_Boundary(module_boundary, "{_diagram(module.name)}") {{']
    for name in sorted(class_names):
        lines.append(f'        Component({node_ids[name]}, "{_diagram(name)}", '
                     '"Java", "Calling code / intermediary")')
    for index, label in enumerate(_feign_labels(clients), 1):
        lines.append(f'        Container(feign_{index}, "{_diagram(label)}", '
                     '"OpenFeign", "HTTP integration point")')
    lines.append('    }')
    for index, client in enumerate(clients, 1):
        lines.append(f'    System_Ext(external_{index}, "{_diagram(_system_name(client))}", '
                     '"External HTTP system")')
    for (source, target), labels in sorted(relationships.items()):
        lines.append(f'    Rel({node_ids[source]}, {node_ids[target]}, '
                     f'"{_diagram("; ".join(sorted(labels)))}")')
    for index, _ in enumerate(clients, 1):
        lines.extend([f'    Rel(module, feign_{index}, "Declares HTTP integration")',
                      f'    Rel(feign_{index}, external_{index}, "Outbound HTTP")'])
    return lines


def _coverage_lines(usage: UsageTraversal, show_details: bool) -> list[str]:
    """Present retained module-wide gaps, independently of finding relevance."""
    sites = usage.untraced_sites
    lines = ['', '## Analysis coverage', '']
    count = len(sites)
    if not count:
        lines.append('No untraced call sites recorded within supported analysis.')
        return lines
    noun, verb = ('site', 'was') if count == 1 else ('sites', 'were')
    lines.append(f'{count} call {noun} {verb} not traced; external effects cannot be ruled out. '
                 'Use `--show-analysis-limitations` for details.')
    if show_details:
        lines.extend(['', '### Untraced call sites', ''])
        for site in sites:
            invocation, reasons = site.invocation, site.reasons
            offset = (f' (source offset {invocation.source_offset})'
                      if invocation.source_offset is not None else '')
            call = f'{invocation.receiver}.{invocation.method_name}({invocation.argument_count} arguments)'
            lines.append(f'- {_evidence(invocation.source_path, invocation.line)}{offset}: '
                         f'{_markdown(call)} — '
                         + ' '.join(_markdown(reason) for reason in reasons))
    return lines


def _integration_lines(number: int, finding: IntegrationFinding,
                       usage: UsageTraversal | None) -> list[str]:
    declaration = finding.declaration
    identity = declaration.declaring_type
    if declaration.field_name:
        identity += '.' + declaration.field_name
    descriptions = {
        'Spring Data JPA': 'JPA persistence access through a directly declared repository interface',
        'Spring JDBC': 'SQL access through a typed JdbcTemplate field',
        'Spring HTTP': 'HTTP access through a typed RestTemplate field',
        'Spring reactive HTTP': 'Reactive HTTP access through a typed WebClient field',
    }
    lines = ['', f'## Finding {number}: {_markdown(identity)}', '',
             f'- **Mechanism:** {_markdown(declaration.mechanism)} — '
             f'{descriptions[declaration.mechanism]}.',
             f'- **Status:** {finding.status_label}',
             f'- **Declaration evidence:** {_evidence(declaration.source_path, declaration.line)}',
             f'- **Destination:** {_markdown(finding.destination.label)}',
             'Declaration evidence, destination certainty, and usage certainty are separate. '
             'A source invocation does not prove runtime execution.']
    if declaration.category == 'database':
        lines.append('No particular database, database name, or JDBC URL is established. '
                     'A JPA repository does not establish direct JDBC calls; '
                     'SQL is not inferred from repository method names.')
    lines.extend(['', '### Operations and query evidence', ''])
    if not finding.operations:
        lines.append('No supported operation evidence was found; the declaration remains reported.')
    for operation in finding.operations:
        kind = ('Observed source operation call' if operation.has_supported_caller else
                'Request-builder configuration only — no observed request operation'
                if operation.invocation is not None else 'Declared query metadata')
        citations = '; '.join(_evidence(item.source_path, item.line)
                              for item in operation.evidence)
        lines.append(f'- **{kind}:** {_markdown(operation.method_name)}. Evidence: {citations}.')
        if declaration.category == 'HTTP':
            lines.append(f'  HTTP method: {_markdown(operation.http_method or "unresolved")}; '
                         f'{_markdown(operation.destination.label)}.')
            for item in operation.destination.evidence:
                lines.append(f'  Destination evidence: {_evidence(item.source_path, item.line)}.')
        if operation.query is not None:
            lines.extend(_query_lines(operation.query))
    if declaration.mechanism == 'Spring reactive HTTP':
        lines.append('A fluent request operation does not prove subscription or network execution. '
                     'Builder-only configuration does not establish a supported operation caller.')
    if usage is not None:
        lines.extend(_usage_lines(finding, usage))
        lines.extend(_adapter_guidance_lines(finding, usage))
    else:
        lines.extend(['', '### Where an adapter could fit', '',
                      'No usage traversal was supplied; no specific adapter placement '
                      'recommendation can be made from this evidence.'])
    return lines


def render_report(module: Module, clients: Iterable[FeignClient],
                  usage: UsageTraversal | None = None, *,
                  show_analysis_limitations: bool = False,
                  findings: Iterable[IntegrationFinding] = ()) -> str:
    """Render supplied source findings without writing or performing analysis."""
    ordered = sorted(clients, key=lambda c: (c.source_path, c.line, c.interface_name))
    expanded = sorted((f for f in findings if f.declaration.mechanism != 'OpenFeign'),
                      key=lambda f: (f.declaration.source_path, f.declaration.line,
                                     f.declaration.declaring_type,
                                     f.declaration.field_name or ''))
    name = _markdown(module.name)
    lines = [f'# Outbound dependencies: {name}', '',
             f'**Module:** {name}', f'**Module path:** {_markdown(str(module.path))}', '',
             '## Summary', '']
    total = len(ordered) + len(expanded)
    database = sum(f.declaration.category == 'database' for f in expanded)
    if total:
        lines.append(f'Found {total} integration declarations: '
                     f'{total - database} HTTP and {database} database. '
                     'These counts do not establish distinct external systems.')
    else:
        lines.append('No recognized integration declarations were found within supported scope. '
                     'External dependencies outside supported scope may still exist.')
    if ordered:
        count = len(ordered)
        noun = 'dependency' if count == 1 else 'dependencies'
        lines.append(f'Found {count} statically declared Feign outbound HTTP {noun}.')
    elif not expanded:
        lines.extend(['No statically declared Feign outbound HTTP dependencies were found.',
                      'This does not mean the module makes no outbound calls by other means.'])
    if usage is not None and total:
        lines.extend(['', 'An adapter is code that keeps the details of communicating '
                      'with an external service separate from the module\'s own work. '
                      'A domain-facing interface expresses what the calling code needs '
                      'without exposing HTTP client or persistence details. The guidance below is a '
                      'suggestion, not an observed fact or a required change.'])
    for index, client in enumerate(ordered, 1):
        system = _markdown(_system_name(client))
        destination, confidence, reason = _destination(client)
        lines.extend(['', f'## Finding {index}: {system}', '',
                      f'{name} makes an outbound HTTP connection to {system} '
                      f'through its {_markdown(client.interface_name)} Feign integration point.', '',
                      f'- **External system:** {system}',
                      f'- **Destination:** {_markdown(destination)}' +
                      (' — Destination unknown' if not client.url else ''),
                      f'- **Confidence:** {confidence}. {reason}',
                      f'- **Client declaration evidence:** {_evidence(client.source_path, client.line)}',
                      ('- **Status:** Declared integration — Supported source operation caller found'
                       if usage is not None and _client_chains(client, usage) else
                       '- **Status:** Declared integration — No supported caller found'),
                      'This is a source declaration, not proof of execution. Destination confidence '
                      'does not weaken declaration evidence or determine usage certainty.',
                      '', '### HTTP operations (supporting detail)', ''])
        if client.operations:
            for operation in client.operations:
                lines.extend(_operation_lines(operation))
        else:
            lines.append('No supported mapped HTTP operations were discovered in this interface; '
                         'this does not prove that it has no operations.')
        if usage is not None:
            lines.extend(_usage_lines(client, usage))
            lines.extend(_adapter_guidance_lines(client, usage))
    for index, finding in enumerate(expanded, len(ordered) + 1):
        lines.extend(_integration_lines(index, finding, usage))
    if any(operation.query and operation.query.language == 'JPQL'
           for finding in expanded for operation in finding.operations):
        lines.extend(['', 'JPQL queries Java persistence entities rather than database tables.'])
    if usage is not None:
        lines.extend(_coverage_lines(usage, show_analysis_limitations))
    lines.extend(['', '## Architectural connections', '', '```mermaid'])
    if usage is not None:
        lines.extend(_usage_diagram_lines(module, ordered, usage))
    else:
        lines.extend(['C4Context',
                      f'    System(module, "{_diagram(module.name)}", "Analyzed Java/Spring module")'])
        for index, (client, label) in enumerate(zip(ordered, _feign_labels(ordered)), 1):
            lines.extend([
                f'    Container(feign_{index}, "{_diagram(label)}", '
                '"OpenFeign", "HTTP integration point")',
                f'    System_Ext(external_{index}, "{_diagram(_system_name(client))}", "External HTTP system")',
                f'    Rel(module, feign_{index}, "Declares HTTP integration")',
                f'    Rel(feign_{index}, external_{index}, "Outbound HTTP")',
            ])
    lines.extend(['```', '', '## Limitations', '',
                  'ArchR analyzed Java source only within the targeted module\'s src/main/java; '
                  'it did not compile, run, or modify the module. Test sources, generated source '
                  'trees, and other modules are outside the analysis boundary. It did not resolve '
                  'configuration or property placeholders.', '',
                  ('No usage traversal was supplied for this declaration-only report; no '
                   'caller chains or applied call-step limit are available.' if usage is None else
                   f'The applied traversal limit is {usage.max_depth} call steps backward from '
                   'each recognized integration. The external connection and interface resolution '
                   'do not consume call steps. Reaching the limit means a chain may continue, '
                   'not that additional callers exist. Cycles stop traversal and are identified '
                   'in the supporting evidence.'), '',
                  'Supported usage forms are ordinary instance-method invocations through '
                  'explicitly typed fields, including constructor-injected fields, written as '
                  'field.method(...) or this.field.method(...). Types are resolved using packages, '
                  'explicit imports, and fully qualified names. Methods are matched by name and '
                  'argument count; indistinguishable overloads remain unresolved. Imports, field '
                  'declarations, constructor assignments, and annotations alone are not usage.', '',
                  'Ordinary non-generic interfaces with one direct local concrete implementation '
                  'can yield possible connections, not verified runtime wiring. Multiple '
                  'implementations remain ambiguous; no local implementation does not establish '
                  'that none exists elsewhere. Recognized library operations and Feign clients '
                  'are terminal integration points; library source is not required.', '',
                  'Local-variable and parameter receivers, chained or dynamically constructed '
                  'receivers, same-class helpers, inherited methods, generic method and interface '
                  'resolution, method references, lambdas, and reflection are outside supported '
                  'traversal, except for the specified repository operations and uninterrupted '
                  'field-rooted WebClient expressions. Split fluent chains are not reconstructed. '
                  'Relevant unresolved or unsupported connections remain beside findings with '
                  'evidence. Coverage summarizes recorded untraced invocations; optional details '
                  'list those sites, not a comprehensive inventory of unsupported syntax. '
                  'Unsupported or unresolved connections are not proof of absence of callers.', '',
                  'Usage is source-only: runtime wiring and execution were not verified. Bean '
                  'selection, qualifiers, profiles, factories, proxies, and runtime dispatch '
                  'are not resolved. Source calls do not prove execution or reachability, and '
                  'destination confidence is independent of usage certainty. ArchR does not '
                  'determine whether a separate domain-facing port or adapter is needed or issue '
                  'an architectural acceptance verdict. A Feign integration point is not assumed '
                  'to be a sufficient architectural adapter.', '',
                  'Recognized declarations are Spring OpenFeign interfaces, interfaces directly '
                  'extending Spring Data JpaRepository, and explicitly typed JdbcTemplate, '
                  'RestTemplate, and WebClient fields. Only the bounded supported operations '
                  'and uninterrupted field-rooted WebClient expressions are recognized. '
                  'Other HTTP and database libraries, indirect repository inheritance, custom client subclasses, '
                  'configuration resolution, and runtime behavior are outside this analysis.', ''])
    return '\n'.join(lines)
