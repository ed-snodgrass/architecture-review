"""Bounded backward source-call paths, not proof of runtime execution."""

from dataclasses import dataclass

from .indexing import Invocation, Method, index_module
from .interfaces import (InterfaceConnection, InterfaceDiagnostic,
                         resolve_interface_index)
from .module import Module
from .integrations import declarations_from_index, repository_types_from_index
from .resolution import CallLink, Diagnostic, resolve_index


DEFAULT_MAX_CALL_STEPS = 2


@dataclass(frozen=True)
class UsageStep:
    link: CallLink
    certainty: str = 'observed'
    interface_connection: InterfaceConnection | None = None


@dataclass(frozen=True)
class UsageChain:
    client_type: str
    # Nearest integration first; each entry is one source invocation, not
    # proof of an HTTP hop or database execution.
    steps: tuple[UsageStep, ...]
    certainty: str
    boundary: str | None = None
    boundary_reason: str = ''
    cycle_link: CallLink | None = None


@dataclass(frozen=True)
class UntracedSite:
    invocation: Invocation
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class UsageTraversal:
    max_depth: int
    chains: tuple[UsageChain, ...]
    diagnostics: tuple[Diagnostic, ...] = ()
    interface_diagnostics: tuple[InterfaceDiagnostic, ...] = ()

    @property
    def untraced_sites(self) -> tuple[UntracedSite, ...]:
        """Distinct recorded gaps, including those outside any client chain.

        Preserve raw diagnostics above. Only failed call resolution and failed
        interface routes contribute sites: destination uncertainty, followed
        possible links and traversal boundaries are not untraced invocations.
        """
        sites = {}
        records = [(item.invocation, item.message) for item in self.diagnostics]
        records.extend((item.link.invocation, item.message)
                       for item in self.interface_diagnostics)
        for invocation, reason in records:
            key = invocation.site_identity
            if key not in sites:
                sites[key] = (invocation, set())
            sites[key][1].add(reason)
        ordered = sorted(sites.values(), key=lambda site: (
            site[0].source_path, site[0].line,
            site[0].source_offset if site[0].source_offset is not None else -1,
            site[0].receiver, site[0].method_name, site[0].argument_count))
        return tuple(UntracedSite(invocation, tuple(sorted(reasons)))
                     for invocation, reasons in ordered)


def _endpoint(type_name: str, method: Method):
    # Use the declaration, not just the class or method name: distinct methods
    # in one class may legitimately appear along a single backward path.
    return type_name, method


def _step_key(step: UsageStep):
    link = step.link
    return (link.caller_type, link.caller_method.source_path,
            link.caller_method.line, link.caller_method.name,
            link.caller_method.parameter_count, link.invocation.source_path,
            link.invocation.line,
            link.invocation.source_offset if link.invocation.source_offset is not None else -1,
            link.invocation.receiver,
            link.target_type, link.target_method.source_path,
            link.target_method.line, link.target_method.name,
            link.target_method.parameter_count)


def trace_usage(module: Module,
                max_depth: int = DEFAULT_MAX_CALL_STEPS) -> UsageTraversal:
    """Return maximal per-call-site paths within the production-source boundary.

    Interface candidates redirect the target endpoint without adding a step.
    Ambiguous or missing implementation routes never enter the graph. Preserve
    resolver diagnostics separately so unresolved syntax is not proof of absence.
    """
    if isinstance(max_depth, bool) or not isinstance(max_depth, int) or max_depth < 1:
        raise ValueError('max_depth must be a positive integer')

    index = index_module(module)
    resolution = resolve_index(index)
    interfaces = resolve_interface_index(index)
    connections = {connection.link: connection for connection in interfaces.connections}
    repositories = repository_types_from_index(index)
    interface_types = {item.qualified_name for item in index.types
                       if item.kind == 'interface' and not item.feign
                       and item.qualified_name not in repositories}
    clients = {item.qualified_name for item in index.types if item.feign} | repositories
    library_fields = {(d.declaring_type, d.field_name)
                      for d in declarations_from_index(index)
                      if d.mechanism in ('Spring JDBC', 'Spring HTTP')}
    incoming = {}
    roots = []
    for link in resolution.links:
        connection = connections.get(link)
        if link.target_type in interface_types:
            if connection is None:
                continue
            target = _endpoint(connection.implementation_type.qualified_name,
                               connection.implementation_method)
            step = UsageStep(link, 'possible', connection)
        else:
            target = _endpoint(link.target_type, link.target_method)
            step = UsageStep(link)
        incoming.setdefault(target, []).append(step)
        if (link.target_type in clients or
                (link.caller_type, link.receiver_field.name) in library_fields):
            roots.append(step)
    for steps in incoming.values():
        steps.sort(key=_step_key)
    roots.sort(key=lambda step: (step.link.target_type, _step_key(step)))

    chains = []

    def finish(client, steps, boundary=None, reason='', cycle_link=None):
        certainty = ('possible' if any(step.certainty == 'possible' for step in steps)
                     else 'observed')
        chains.append(UsageChain(client, steps, certainty, boundary, reason, cycle_link))

    for root in roots:
        client = root.link.target_type
        endpoint = _endpoint(root.link.caller_type, root.link.caller_method)
        # An explicit stack also allows larger future limits without depending
        # on Python's recursion limit. Visited declarations are path-local.
        pending = [((root,), frozenset((endpoint,)))]
        while pending:
            steps, visited = pending.pop()
            if len(steps) == max_depth:
                finish(client, steps, 'depth',
                       f'The {max_depth}-call-step boundary was reached; the chain '
                       'may continue. This does not establish that more callers exist.')
                continue
            last = steps[-1].link
            upstream = incoming.get(_endpoint(last.caller_type, last.caller_method), ())
            if not upstream:
                finish(client, steps)
                continue
            for step in reversed(upstream):
                caller = _endpoint(step.link.caller_type, step.link.caller_method)
                if caller in visited:
                    finish(client, steps, 'cycle',
                           f'A cycle would repeat {step.link.caller_type}.'
                           f'{step.link.caller_method.name} '
                           f'({step.link.caller_method.source_path}:'
                           f'{step.link.caller_method.line}); traversal stopped before '
                           'repeating that method.', step.link)
                else:
                    pending.append((steps + (step,), visited | {caller}))

    # Cycle branches are finished immediately, whereas ordinary branches use
    # the stack; sort the final output independently of that processing order.
    chains.sort(key=lambda chain: (
        chain.client_type, tuple(_step_key(step) for step in chain.steps),
        chain.boundary or '',
        _step_key(UsageStep(chain.cycle_link)) if chain.cycle_link else ()))
    return UsageTraversal(max_depth, tuple(chains), resolution.diagnostics,
                          interfaces.diagnostics)
