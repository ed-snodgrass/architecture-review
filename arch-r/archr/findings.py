"""Source-only integration findings with independent evidence dimensions.

A declaration is sufficient for a finding. Neither a destination nor a mapped
operation proves a caller; even an observed invocation does not prove execution.
Operation recognizers and report rendering consume this model separately.
"""

from dataclasses import dataclass
from enum import Enum

from .discovery import read_java_sources, tokenize
from .indexing import Invocation, index_module
from .webclient import webclient_expression
from .queries import JPA_QUERY, QueryEvidence, jdbc_query, repository_queries
from .http import rest_facts, destination_kind
from .integrations import IntegrationDeclaration, discover_declarations
from .module import Module
from .traversal import UsageChain, trace_usage


@dataclass(frozen=True)
class SourceEvidence:
    source_path: str
    line: int


class DestinationCertainty(str, Enum):
    UNKNOWN = 'unknown'
    LITERAL = 'literal'
    PATH = 'path (host unknown)'
    UNRESOLVED = 'unresolved'


@dataclass(frozen=True)
class DestinationEvidence:
    """Visible destination facts, not inferred database or runtime identity.

    LITERAL describes source text only, not a verified network destination.
    PATH and UNRESOLVED retain visible text without asserting a known host.
    UNKNOWN is deliberately the default for every declaration.
    """

    certainty: DestinationCertainty = DestinationCertainty.UNKNOWN
    value: str | None = None
    evidence: tuple[SourceEvidence, ...] = ()

    @property
    def label(self) -> str:
        if self.certainty == DestinationCertainty.UNKNOWN:
            return 'Destination unknown'
        if self.certainty == DestinationCertainty.PATH:
            return f'Path: {self.value} — Host unknown'
        if self.certainty == DestinationCertainty.UNRESOLVED:
            return f'Destination unresolved: {self.value or "nonliteral expression (not evaluated)"}'
        return f'Literal destination: {self.value}'


@dataclass(frozen=True)
class OperationEvidence:
    """A declared operation, source invocation, or builder configuration.

    An annotation may describe an operation without any invocation. WebClient
    builder configuration may have an invocation without a request operation.
    Neither constitutes a supported operation caller. Destinations are local to
    each operation so conflicting or unresolved calls do not overwrite others.
    """

    method_name: str
    evidence: tuple[SourceEvidence, ...]
    invocation: Invocation | None = None
    is_request_operation: bool = True
    http_method: str | None = None
    destination: DestinationEvidence = DestinationEvidence()
    query: QueryEvidence | None = None

    @property
    def has_supported_caller(self) -> bool:
        return self.invocation is not None and self.is_request_operation


class UsageCertainty(str, Enum):
    NO_SUPPORTED_CALLER = 'no supported caller found'
    OBSERVED = 'observed source call'
    POSSIBLE = 'possible source chain'


@dataclass(frozen=True)
class IntegrationFinding:
    declaration: IntegrationDeclaration
    operations: tuple[OperationEvidence, ...] = ()
    destination: DestinationEvidence = DestinationEvidence()
    chains: tuple[UsageChain, ...] = ()

    @property
    def declaration_evidence(self) -> SourceEvidence:
        return SourceEvidence(self.declaration.source_path, self.declaration.line)

    @property
    def supported_call_evidence(self) -> tuple[SourceEvidence, ...]:
        """Citations of direct supported source calls, independent of destinations.

        Operation annotations and builder-only invocations are not usage facts.
        A nonempty backward chain supplies its integration-facing invocation;
        upstream steps describe continuity, not additional integration calls.
        Deduplicate citations shared by operation evidence and traced chains.
        """
        invocations = [operation.invocation for operation in self.operations
                       if operation.has_supported_caller]
        invocations.extend(chain.steps[0].link.invocation for chain in self.chains
                           if chain.steps)
        citations = {SourceEvidence(invocation.source_path, invocation.line)
                     for invocation in invocations if invocation is not None}
        return tuple(sorted(citations, key=lambda item: (item.source_path, item.line)))

    @property
    def has_supported_caller(self) -> bool:
        return bool(self.supported_call_evidence)

    @property
    def usage_certainty(self) -> UsageCertainty:
        if not self.has_supported_caller:
            return UsageCertainty.NO_SUPPORTED_CALLER
        if any(chain.steps and chain.certainty == 'possible' for chain in self.chains):
            return UsageCertainty.POSSIBLE
        return UsageCertainty.OBSERVED

    @property
    def status_label(self) -> str:
        if not self.has_supported_caller:
            return 'Declared integration — No supported caller found'
        return 'Declared integration — Supported source operation caller found'


def discover_findings(module: Module) -> tuple[IntegrationFinding, ...]:
    """Retain declarations and attach supported integration source calls.

    All fields of a repository type contribute to its one declaration finding.
    JDBC, RestTemplate and WebClient calls belong to their declaring field.
    WebClient configuration alone does not establish a supported caller.
    """
    declarations = discover_declarations(module)
    # Feign and repositories are shared interface endpoints; library clients
    # are field endpoints. All mechanisms consume the same bounded traversal.
    usage = trace_usage(module) if declarations else None
    sources = None
    query_tokens = {}

    def source_for(invocation: Invocation):
        nonlocal sources
        if sources is None:
            sources = dict(read_java_sources(module))
        path = invocation.source_path
        if path not in query_tokens:
            query_tokens[path] = tokenize(sources[path])
        return sources[path], query_tokens[path]

    def rest_operation(invocation: Invocation) -> OperationEvidence:
        source, tokens = source_for(invocation)
        verb, value, line = rest_facts(source, invocation, tokens=tokens)
        citation = SourceEvidence(invocation.source_path, invocation.line)
        destination = DestinationEvidence(
            DestinationCertainty(destination_kind(value)), value,
            (SourceEvidence(invocation.source_path, line),))
        return OperationEvidence(invocation.method_name, (citation,),
                                 invocation=invocation, http_method=verb,
                                 destination=destination)

    def web_operation(invocation: Invocation) -> OperationEvidence:
        source, tokens = source_for(invocation)
        expression = webclient_expression(source, invocation, tokens)
        return OperationEvidence(
            expression.request_operation or invocation.method_name,
            tuple(dict.fromkeys(SourceEvidence(invocation.source_path, line)
                                for line in (invocation.line, expression.request_line)
                                if line is not None)),
            invocation=invocation,
            is_request_operation=expression.request_operation is not None,
            http_method=expression.http_method,
            destination=DestinationEvidence(
                DestinationCertainty(destination_kind(expression.destination)),
                expression.destination,
                (SourceEvidence(invocation.source_path, expression.destination_line),)))

    # Builder-only expressions retain configuration facts without becoming callers.
    web_invocations = {}
    if any(d.mechanism == 'Spring reactive HTTP' for d in declarations):
        index = index_module(module)
        for declaration in declarations:
            if declaration.mechanism != 'Spring reactive HTTP':
                continue
            calls = []
            for owner in index.types:
                if owner.qualified_name != declaration.declaring_type:
                    continue
                for method in owner.methods:
                    for invocation in method.invocations:
                        if (invocation.field_receiver and not invocation.explicit_type_arguments and
                                invocation.receiver.removeprefix('this.') == declaration.field_name):
                            source, tokens = source_for(invocation)
                            if webclient_expression(source, invocation, tokens) is not None:
                                calls.append(invocation)
            web_invocations[(declaration.declaring_type, declaration.field_name)] = calls

    def query_for(invocation: Invocation) -> QueryEvidence:
        # Tokenize only files with supported JDBC calls, once per source file.
        # Declaration-only fields and unrelated production sources need no SQL
        # inspection; unknown overloads still retain their operation evidence.
        source, tokens = source_for(invocation)
        return jdbc_query(source, invocation, tokens=tokens)

    endpoint_chains: dict[str, list[UsageChain]] = {}
    field_chains: dict[tuple[str, str, str], list[UsageChain]] = {}
    if usage is not None:
        for chain in usage.chains:
            endpoint_chains.setdefault(chain.client_type, []).append(chain)
            if chain.steps:
                link = chain.steps[0].link
                field_chains.setdefault((link.caller_type, link.receiver_field.name,
                                         link.target_type), []).append(chain)
    repository_operations = {}
    if any(d.mechanism == 'Spring Data JPA' for d in declarations):
        index = index_module(module)
        # A locally declared annotation is not Spring query metadata.
        if JPA_QUERY not in index.declared_type_names:
            for owner in index.types:
                repository_operations[owner.qualified_name] = tuple(
                    OperationEvidence(
                        method.name, (SourceEvidence(query.source_path, query.line),),
                        query=query)
                    for method in owner.methods for query in repository_queries(method))
    findings = []
    for declaration in declarations:
        chains = (tuple(endpoint_chains.get(declaration.declaring_type, ()))
                  if declaration.mechanism in ('OpenFeign', 'Spring Data JPA') else
                  tuple(field_chains.get((declaration.declaring_type,
                                          declaration.field_name,
                                          declaration.type_name), ()))
                  if declaration.mechanism in ('Spring JDBC', 'Spring HTTP', 'Spring reactive HTTP') else ())
        # Upstream branches can share one integration call. Identify that call
        # by its source site, not by the route or the synthetic library endpoint.
        invocations = {chain.steps[0].link.invocation.site_identity:
                       chain.steps[0].link.invocation
                       for chain in chains if chain.steps}
        for invocation in web_invocations.get((declaration.declaring_type, declaration.field_name), ()):
            invocations[invocation.site_identity] = invocation
        operations = tuple(web_operation(invocation)
                           if declaration.mechanism == 'Spring reactive HTTP' else rest_operation(invocation)
                           if declaration.mechanism == 'Spring HTTP' else OperationEvidence(
            invocation.method_name,
            (SourceEvidence(invocation.source_path, invocation.line),),
            invocation=invocation,
            query=(query_for(invocation)
                   if declaration.mechanism == 'Spring JDBC' else None)
        ) for invocation in sorted(invocations.values(), key=lambda i: (
                i.source_path, i.line, i.source_offset if i.source_offset is not None else -1,
                i.receiver, i.method_name, i.argument_count)))
        if declaration.mechanism == 'Spring Data JPA':
            operations = repository_operations.get(declaration.declaring_type, ()) + operations
        findings.append(IntegrationFinding(declaration, operations=operations, chains=chains))
    return tuple(findings)
