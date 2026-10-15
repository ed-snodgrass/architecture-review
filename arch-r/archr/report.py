"""Deterministic, standalone Markdown rendering of source-only findings."""

from collections import Counter
from collections.abc import Iterable

from .discovery import FeignClient, Operation
from .module import Module
from .findings import DestinationCertainty, IntegrationFinding
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


def _query_lines(query: QueryEvidence, *, cite: bool = True) -> list[str]:
    """Render only retained bounded evidence, never invocation source text.

    JDBC and repository findings share this path, including unresolved values.
    Escape after truncation: Markdown entities do not consume preview characters.
    """
    value = (_markdown(query.preview) if query.preview is not None
             else 'Unresolved query expression (not evaluated)')
    citation = f' Evidence: {_evidence(query.source_path, query.line)}.' if cite else ''
    return [f'- **{_markdown(query.language)}:** {value}.{citation}']


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
    # Discovery retains the shared type mapping first and the method mapping last.
    # Cite the method mapping so sibling operations point to their own declarations.
    location = operation.evidence[-1] if operation.evidence else None
    evidence = (_evidence(location.source_path, location.line) if location
                else 'No supported source location observed')
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
        link = diagnostic.link
        lines.append(f'- Unresolved interface connection ({_markdown(diagnostic.code)}): '
                     f'{_markdown(link.caller_type + "." + link.caller_method.name)} → '
                     f'{_markdown(link.target_type + "." + link.target_method.name)} '
                     f'at {_evidence(link.invocation.source_path, link.invocation.line)}. '
                     + _markdown(diagnostic.message))
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
                            usage: UsageTraversal | None) -> list[str]:
    """Explain conditional reviews, without inferring behavior or adapter shape."""
    lines = ['', '### Review conditions', '']
    if usage is None:
        return [*lines, 'No usage traversal was supplied, so ArchR cannot identify '
                'code to review. No recommendation or example is provided.']
    chains = _client_chains(client, usage)
    if not chains:
        diagnostics, interfaces = _relevant_diagnostics(client, usage)
        reason = ('The caller connection is unresolved; no supported caller was '
                  'established within the analysis boundary.' if diagnostics or interfaces
                  else 'No supported caller was found within the analysis boundary.')
        return [*lines, reason + ' ArchR cannot identify code to review, so no '
                'recommendation or example is provided.']

    database = (isinstance(client, IntegrationFinding)
                and client.declaration.category == 'database')
    # Keep distinct possible routes conditional, but do not repeat the same
    # direct method's educational examples for every upstream path/operation.
    seen = set()
    for chain in chains:
        link = chain.steps[0].link
        connections = tuple(step.interface_connection for step in reversed(chain.steps)
                            if step.interface_connection)
        key = (link.caller_type, link.caller_method, chain.certainty, connections)
        if key in seen:
            continue
        seen.add(key)
        caller = _markdown(link.caller_type + '.' + link.caller_method.name)
        target = _markdown(link.target_type + '.' + link.target_method.name)
        lines.extend(['', f'#### Review {caller}', ''])
        if chain.certainty == 'possible':
            lines.append('This route is possible, not confirmed; the following review '
                         'applies only if the connection is verified.')
        for connection in connections:
            lines.append('First verify that runtime wiring connects '
                         f'{_markdown(connection.interface_type.qualified_name)} to '
                         f'{_markdown(connection.implementation_type.qualified_name)}; '
                         'this interface connection remains possible.')
        lines.append(f'Inspect {caller}, the observed direct caller of {target}, '
                     'for the following conditions; ArchR has not established '
                     'that any of them occurs.')
        if database:
            conditions = [
                ('Interpreting persistence results',
                 'Check whether this method translates stored fields or query results '
                 'into meaning used by this module.',
                 ['boolean eligible = storedStatus.equals("ACTIVE");']),
                ('Handling integration-specific failures',
                 'Check whether this method directly reacts to SQL errors, '
                 'persistence-library exceptions, or persistence retry rules.',
                 ['if (sqlState.equals("40001")) {', '    retry = true;', '}']),
                ('Mixing integration details with business decisions',
                 'Check whether the same method both communicates with the database '
                 'and decides what the module should do.',
                 ['// After the persistence call in this method:',
                  'if (storedQuantity > requestedQuantity) {',
                  '    orderAccepted = true;', '}']),
            ]
        else:
            conditions = [
                ('Interpreting a client response',
                 'Check whether this method translates external fields, statuses, '
                 'or representations into meaning used by this module.',
                 ['boolean available = externalStatus.equals("AVAILABLE");']),
                ('Handling integration-specific failures',
                 'Check whether this method directly reacts to HTTP status codes, '
                 'timeouts, client-library exceptions, or retry rules.',
                 ['if (httpStatus == 503) {', '    retry = true;', '}']),
                ('Mixing integration details with business decisions',
                 'Check whether the same method both communicates with the '
                 'dependency and decides what the module should do.',
                 ['// After the client call in this method:',
                  'if (externalQuantity > requestedQuantity) {',
                  '    orderAccepted = true;', '}']),
            ]
        for title, explanation, example in conditions:
            lines.extend(['', f'**{title}**', '', explanation, '',
                          f'Illustrative only — if your code looks like this in {caller}: '
                          'ArchR did not establish this behavior. These Java statements '
                          'use hypothetical local values, not a reconstruction of source.',
                          '', '```java', *example, '```'])
    return lines


def _feign_labels(clients: list[FeignClient]) -> list[str]:
    """Retain short labels unless multiple declarations share that name."""
    counts = Counter(client.interface_name for client in clients)
    return [client.qualified_name or client.interface_name
            if counts[client.interface_name] > 1 else client.interface_name
            for client in clients]


def _usage_diagram_lines(module: Module, clients: list[FeignClient],
                         usage: UsageTraversal | None,
                         findings: list[IntegrationFinding]) -> list[str]:
    """Summarize only displayed method-level routes as shared class edges.

    Interface resolution redirects a possible edge to its candidate class;
    unresolved routes and proposed adapters never become diagram components.
    Evidence remains in the findings, independently of edge deduplication.
    """
    chains = [(chain, f'feign_{index}')
              for index, client in enumerate(clients, 1)
              for chain in (_client_chains(client, usage) if usage else ())]
    chains.extend((chain, f'integration_{index}')
                  for index, finding in enumerate(findings, 1)
                  for chain in finding.chains if usage is not None)
    feign_ids = {}
    for index, client in enumerate(clients, 1):
        for chain in (_client_chains(client, usage) if usage else ()):
            feign_ids[chain.client_type] = f'feign_{index}'
    for index, finding in enumerate(findings, 1):
        if finding.declaration.field_name is None:
            feign_ids[finding.declaration.declaring_type] = f'integration_{index}'

    class_names = set()
    relationships = {}
    integration_ids = {endpoint for _, endpoint in chains}
    for chain, endpoint in chains:
        for depth, step in enumerate(chain.steps):
            link = step.link
            connection = step.interface_connection
            target = (endpoint if depth == 0 else
                      connection.implementation_type.qualified_name
                      if connection else link.target_type)
            class_names.add(link.caller_type)
            if target not in feign_ids and target not in integration_ids:
                class_names.add(target)
            label = (f'Possible connection through {connection.interface_type.qualified_name} '
                     '(runtime wiring unverified)' if connection else 'Observed source call')
            relationships.setdefault((link.caller_type, target), set()).add(label)
    # A Feign declaration can itself contain calling code (for example a
    # default method); reuse its integration node rather than declaring it twice.
    class_names.difference_update(feign_ids)
    node_ids = {name: f'class_{index}'
                for index, name in enumerate(sorted(class_names), 1)}
    node_ids.update(feign_ids)
    node_ids.update({endpoint: endpoint for endpoint in integration_ids})

    lines = ['C4Context',
             f'    System(module, "{_diagram(module.name)}", "Analyzed Java/Spring module")',
             f'    System_Boundary(module_boundary, "{_diagram(module.name)}") {{']
    for name in sorted(class_names):
        lines.append(f'        Component({node_ids[name]}, "{_diagram(name)}", '
                     '"Java", "Calling code / intermediary")')
    for index, label in enumerate(_feign_labels(clients), 1):
        lines.append(f'        Container(feign_{index}, "{_diagram(label)}", '
                     '"OpenFeign", "HTTP integration point")')
    for index, finding in enumerate(findings, 1):
        declaration = finding.declaration
        identity = declaration.declaring_type
        if declaration.field_name:
            identity += '.' + declaration.field_name
        lines.append(f'        Container(integration_{index}, "{_diagram(identity)}", '
                     f'"{_diagram(declaration.mechanism)}", "Declared integration")')
    lines.append('    }')
    # Literal destinations are source evidence, not verified runtime systems.
    # Relative paths and placeholders cannot establish an external destination.
    destinations = []
    for finding in findings:
        literals = {operation.destination.value for operation in finding.operations
                    if operation.destination.certainty == DestinationCertainty.LITERAL
                    and operation.destination.value is not None}
        unknown = (not finding.operations or any(
            operation.destination.certainty != DestinationCertainty.LITERAL
            for operation in finding.operations))
        destinations.append((sorted(literals), unknown))
    literal_ids = {value: f'literal_{index}' for index, value in enumerate(
        sorted({value for values, _ in destinations for value in values}), 1)}
    for value, node in literal_ids.items():
        lines.append(f'    System_Ext({node}, "{_diagram(value)}", '
                     '"Literal HTTP destination in source; runtime unverified")')
    # Shared unknown nodes deliberately do not claim distinct real systems.
    categories = sorted({f.declaration.category
                         for f, (_, unknown) in zip(findings, destinations) if unknown})
    for category in categories:
        lines.append(f'    System_Ext(unknown_{category}, '
                     f'"Destination unknown: {category}", '
                     '"Unresolved destinations; not a count of distinct systems")')
    for index, client in enumerate(clients, 1):
        certainty = ('Literal destination in source; runtime unverified'
                     if client.url and '${' not in client.url else 'Destination unknown')
        lines.append(f'    System_Ext(external_{index}, "{_diagram(_system_name(client))}", '
                     f'"External HTTP system; {certainty}")')
    for (source, target), labels in sorted(relationships.items()):
        lines.append(f'    Rel({node_ids[source]}, {node_ids[target]}, '
                     f'"{_diagram("; ".join(sorted(labels)))}")')
    for index, _ in enumerate(clients, 1):
        lines.extend([f'    Rel(module, feign_{index}, "Declares HTTP integration")',
                      f'    Rel(feign_{index}, external_{index}, '
                      '"Declared HTTP destination; runtime traffic unverified")'])
    for index, (finding, (values, unknown)) in enumerate(zip(findings, destinations), 1):
        category = finding.declaration.category
        lines.append(f'    Rel(module, integration_{index}, "Declares {category} integration")')
        if unknown:
            lines.append(f'    Rel(integration_{index}, unknown_{category}, '
                         '"Declared integration; destination unknown; not runtime traffic")')
        for value in values:
            lines.append(f'    Rel(integration_{index}, {literal_ids[value]}, '
                         '"Literal destination in source; not runtime traffic")')
    return lines


def _coverage_lines(usage: UsageTraversal, show_details: bool) -> list[str]:
    """Present retained module-wide gaps, independently of finding relevance."""
    sites = usage.untraced_sites
    lines = ['', '### Analysis coverage', '']
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


def _brief_card(number: int, identity: str, client: FeignClient | IntegrationFinding,
                usage: UsageTraversal | None) -> list[str]:
    """Summarize integration identity without leaking supporting evidence into cards."""
    chains = _client_chains(client, usage) if usage is not None else ()
    supported = bool(chains) or (isinstance(client, IntegrationFinding)
                                 and client.has_supported_caller)
    unresolved = (any(_relevant_diagnostics(client, usage))
                  if usage is not None else False)
    status = ('Caller found' if supported else
              'Caller unresolved' if unresolved else 'No caller found')
    if isinstance(client, FeignClient):
        value = client.url or client.url_expression
        destination = (_destination(client)[0] if value else 'Unknown')
        system = (client.name or (f'Unresolved: {client.name_expression}'
                                 if client.name_expression else 'Unknown'))
        mechanism = 'OpenFeign HTTP client'
    else:
        destination = ('Unknown' if client.destination.certainty == DestinationCertainty.UNKNOWN
                       else client.destination.label)
        # A repository or a client field does not identify an external system.
        system = 'Unknown'
        mechanism = client.declaration.mechanism
    if chains:
        direct = chains[0].steps[0].link
        observed = _markdown(direct.caller_type + '.' + direct.caller_method.name)
        recommendation = (f'Inspect {observed} to determine whether it handles '
                          'integration-specific failures or mixes integration details '
                          'with module decisions.')
    elif usage is None:
        recommendation = ('No recommendation: no usage traversal was supplied, '
                          'so ArchR cannot identify code to inspect.')
    elif unresolved:
        recommendation = ('No recommendation: the caller connection is unresolved, '
                          'so ArchR cannot identify supported caller code to inspect.')
    else:
        recommendation = ('No recommendation: no supported caller was found, '
                          'so ArchR cannot identify code to inspect.')
    return ['', f'### Finding {number}: {_markdown(identity)}', '',
            f'- **Destination:** {_markdown(destination)}',
            f'- **Status:** {status}',
            f'- **External system:** {_markdown(system)}',
            f'- **Mechanism:** {_markdown(mechanism)}',
            f'- **Adapter Recommendation:** {recommendation} '
            f'[Review guidance](#finding-{number}-guidance)',
            f'[Evidence](#finding-{number}-evidence)', '']


def _method_identity(type_name, method):
    """Distinguish overloads and declarations without depending on call sites."""
    return (type_name, method.source_path, method.declaration_line or method.line,
            method.name, method.parameter_count)


def _connection_identity(connection):
    if connection is None:
        return None
    return (connection.interface_type.qualified_name,
            connection.interface_type.source_path, connection.interface_type.line,
            _method_identity(connection.implementation_type.qualified_name,
                             connection.implementation_method),
            connection.certainty, connection.reason)


def _compact_call_lines(chains) -> list[str]:
    """Group semantic paths, not invocation sites; leave operation citations separate.

    Only terminal methods may differ within a group. Certainty, interface routes,
    receiver identity, and cutoff behavior remain part of the grouping key.
    Insertion order retains the traversal's deterministic finding/path order.
    """
    groups = {}
    for chain in chains:
        steps = tuple(reversed(chain.steps))
        upstream = tuple((
            _method_identity(step.link.caller_type, step.link.caller_method),
            _method_identity(step.link.target_type, step.link.target_method),
            step.link.receiver_field, step.certainty,
            _connection_identity(step.interface_connection)) for step in steps[:-1])
        terminal = steps[-1]
        cycle = chain.cycle_link
        cycle_identity = ((_method_identity(cycle.caller_type, cycle.caller_method),
                           _method_identity(cycle.target_type, cycle.target_method),
                           cycle.receiver_field) if cycle else None)
        key = (upstream,
               _method_identity(terminal.link.caller_type, terminal.link.caller_method),
               terminal.link.receiver_field, terminal.certainty,
               _connection_identity(terminal.interface_connection),
               chain.certainty, chain.boundary, chain.boundary_reason, cycle_identity)
        if key not in groups:
            groups[key] = (chain, {})
        endpoints = groups[key][1]
        endpoint = _method_identity(terminal.link.target_type, terminal.link.target_method)
        endpoints.setdefault(endpoint, terminal.link)

    lines = []
    for chain, endpoints in groups.values():
        steps = tuple(reversed(chain.steps))
        names = [step.link.caller_type + '.' + step.link.caller_method.name
                 for step in steps]
        label = 'Possible chain' if chain.certainty == 'possible' else 'Observed source chain'
        targets = [link.target_type + '.' + link.target_method.name
                   for link in endpoints.values()]
        if len(targets) == 1:
            lines.append(f'- {label}: {_markdown(" → ".join([*names, targets[0]]))}.')
        else:
            lines.append(f'- {label}: {_markdown(" → ".join(names))}')
            lines.extend(f'  - → {_markdown(target)}' for target in targets)
        for step in steps:
            connection = step.interface_connection
            if connection:
                lines.append('  - Possible interface connection: '
                             f'{_markdown(connection.interface_type.qualified_name)} → '
                             f'{_markdown(connection.implementation_type.qualified_name + "." + connection.implementation_method.name)}. '
                             f'{_markdown(connection.reason)}')
        if chain.boundary:
            lines.append('  - ' + _markdown(chain.boundary_reason))
        if chain.cycle_link:
            link = chain.cycle_link
            lines.append('  - Cycle cutoff: '
                         f'{_markdown(link.caller_type + "." + link.caller_method.name)} → '
                         f'{_markdown(link.target_type + "." + link.target_method.name)}.')
    return lines


def _observed_call_lines(client: FeignClient | IntegrationFinding,
                         usage: UsageTraversal | None) -> list[str]:
    """Keep call evidence in its fixed subsection, including declaration-only reports."""
    lines = ['', '#### Observed Call Chains', '']
    if usage is None:
        return lines + ['No supported call chains observed; no usage traversal was supplied.']
    if not _client_chains(client, usage):
        lines.append('No supported call chains observed within the supported analysis.')
        diagnostics, interfaces = _relevant_diagnostics(client, usage)
        lines.extend(_diagnostic_lines(diagnostics, interfaces))
        return lines
    lines.extend(_compact_call_lines(_client_chains(client, usage)))
    diagnostics, interfaces = _relevant_diagnostics(client, usage)
    lines.extend(_diagnostic_lines(diagnostics, interfaces))
    return lines


def _integration_sections(number: int, finding: IntegrationFinding,
                          usage: UsageTraversal | None
                          ) -> tuple[list[str], list[str], list[str]]:
    declaration = finding.declaration
    identity = declaration.declaring_type
    if declaration.field_name:
        identity += '.' + declaration.field_name
    heading = ['', f'### Finding {number}: {_markdown(identity)}', '']
    brief = _brief_card(number, identity, finding, usage)
    lines = [f'<a id="finding-{number}-evidence"></a>',
             *heading,
             '#### Declaration', '',
             f'Declaration evidence: {_evidence(declaration.source_path, declaration.line)}',
             '', '#### Operations', '']
    if declaration.category == 'database':
        lines.append('No particular database, database name, or JDBC URL is established. '
                     'A JPA repository does not establish direct JDBC calls; '
                     'SQL is not inferred from repository method names.')
    if not finding.operations:
        lines.append('No supported operations observed within the supported analysis.')
    for operation in finding.operations:
        kind = ('Observed source operation call' if operation.has_supported_caller else
                'Request-builder configuration only — no observed request operation'
                if operation.invocation is not None else 'Declared query metadata')
        # Prefer the invocation for calls, or the query annotation for metadata.
        location = operation.invocation or operation.query or next(iter(operation.evidence), None)
        citation = (_evidence(location.source_path, location.line) if location
                    else 'No supported source location observed')
        lines.append(f'- **{kind}:** {_markdown(operation.method_name)}. Evidence: {citation}.')
        if declaration.category == 'HTTP':
            lines.append(f'  HTTP method: {_markdown(operation.http_method or "unresolved")}; '
                         f'{_markdown(operation.destination.label)}.')
        if operation.query is not None:
            lines.extend(_query_lines(operation.query, cite=False))
    if declaration.mechanism == 'Spring reactive HTTP':
        lines.append('A fluent request operation does not prove subscription or network execution. '
                     'Builder-only configuration does not establish a supported operation caller.')
    lines.extend(_observed_call_lines(finding, usage))
    guidance = [f'<a id="finding-{number}-guidance"></a>',
                *heading, *_nested_finding_lines(_adapter_guidance_lines(finding, usage))]
    return brief, guidance, lines


def _nested_finding_lines(lines: list[str]) -> list[str]:
    """Keep supporting headings below their finding subsection."""
    return ['#' + line if line.startswith('### ') else line for line in lines]


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
    brief_sections: list[str] = []
    guidance_sections: list[str] = []
    evidence_sections: list[str] = []
    if usage is not None and total:
        guidance_sections.extend(['', 'An adapter is code that keeps the details of communicating '
                      'with an external service separate from the module\'s own work. '
                      'The guidance below identifies conditions to inspect, not observed '
                      'behavior, a required change, or a proposed implementation.'])
    for index, (client, identity) in enumerate(zip(ordered, _feign_labels(ordered)), 1):
        heading = ['', f'### Finding {index}: {_markdown(identity)}', '']
        brief_sections.extend(_brief_card(index, identity, client, usage))
        _, confidence, reason = _destination(client)
        evidence_sections.extend([f'<a id="finding-{index}-evidence"></a>',
                                  *heading,
                                  '#### Declaration', '',
                                  f'Client declaration evidence: {_evidence(client.source_path, client.line)}',
                                  f'Destination confidence: {confidence}. {reason}',
                                  '', '#### Operations', ''])
        if client.operations:
            for operation in client.operations:
                evidence_sections.extend(_operation_lines(operation))
        else:
            evidence_sections.append('No supported operations observed within the supported analysis.')
        evidence_sections.extend(_observed_call_lines(client, usage))
        guidance_sections.extend([
            f'<a id="finding-{index}-guidance"></a>',
            *heading, *_nested_finding_lines(_adapter_guidance_lines(client, usage))])
    for index, finding in enumerate(expanded, len(ordered) + 1):
        brief, guidance, evidence = _integration_sections(index, finding, usage)
        brief_sections.extend(brief)
        guidance_sections.extend(guidance)
        evidence_sections.extend(evidence)
    if any(operation.query and operation.query.language == 'JPQL'
           for finding in expanded for operation in finding.operations):
        evidence_sections.extend(['', 'JPQL queries Java persistence entities rather than database tables.'])
    lines.extend(['', '## Architectural Connections', '', '```mermaid'])
    if usage is not None or expanded:
        lines.extend(_usage_diagram_lines(module, ordered, usage, expanded))
    else:
        lines.extend(['C4Context',
                      f'    System(module, "{_diagram(module.name)}", "Analyzed Java/Spring module")'])
        for index, (client, label) in enumerate(zip(ordered, _feign_labels(ordered)), 1):
            lines.extend([
                f'    Container(feign_{index}, "{_diagram(label)}", '
                '"OpenFeign", "HTTP integration point")',
                f'    System_Ext(external_{index}, "{_diagram(_system_name(client))}", '
                '"External HTTP system; runtime destination unverified")',
                f'    Rel(module, feign_{index}, "Declares HTTP integration")',
                f'    Rel(feign_{index}, external_{index}, '
                '"Declared HTTP destination; runtime traffic unverified")',
            ])
    lines.extend(['```', '', '## Findings', *brief_sections,
                  '', '## Adapter Review Guidance', *guidance_sections,
                  '', '## Findings with Evidence', *evidence_sections,
                  '', '## Limitations', '',
                  'ArchR analyzed Java source only within the targeted module\'s src/main/java; '
                  'it did not compile, run, or modify the module. Other source trees and modules '
                  'are outside this boundary. Declarations and source calls do not prove runtime '
                  'wiring, execution, or reachability. Destination confidence is independent of '
                  'caller certainty.', '',
                  ('No usage traversal was supplied for this declaration-only report; no '
                   'caller chains or applied call-step limit are available.' if usage is None else
                   f'The applied traversal limit is {usage.max_depth} call steps backward from '
                   'each integration; interface resolution and the external connection do not '
                   'consume steps. Library source is not required for terminal operations.'), '',
                  '**Caller found** means a supported source caller chain was established. '
                  '**No caller found** means no supported caller or relevant unresolved caller '
                  'was recorded within this boundary. **Caller unresolved** means evidence '
                  'connects a possible caller to the integration, but analysis cannot resolve '
                  'that connection. Unsupported or unresolved connections are not proof of '
                  'absence of callers.', '',
                  'Supported mechanisms are OpenFeign, direct Spring Data JpaRepository '
                  'interfaces, and typed JdbcTemplate, RestTemplate, and WebClient fields. '
                  'Supported calls use explicitly typed fields (including constructor-injected '
                  'fields): field.method(...) or this.field.method(...), plus bounded repository '
                  'operations and uninterrupted field-rooted WebClient requests. Local interface '
                  'connections may be possible rather than certain. Other HTTP and database '
                  'mechanisms are outside scope.', '',
                  'Configuration and property placeholders are not resolved; unknown or '
                  'unresolved destinations retain their source uncertainty in the evidence. '
                  'Finding-specific query, interface, and path uncertainty is recorded there, '
                  'not repeated here. Coverage counts recorded untraced calls, not every '
                  'unsupported Java construct.', ''])
    if usage is not None:
        lines.extend(_coverage_lines(usage, show_analysis_limitations))
        lines.append('')
    return '\n'.join(lines)
