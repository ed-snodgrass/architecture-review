"""Source-only integration findings with independent evidence dimensions.

A declaration is sufficient for a finding. Neither a destination nor a mapped
operation proves a caller; even an observed invocation does not prove execution.
Operation recognizers and report rendering consume this model separately.
"""

from dataclasses import dataclass
from enum import Enum

from .indexing import Invocation
from .integrations import IntegrationDeclaration, discover_declarations
from .module import Module
from .traversal import UsageChain


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
            return f'Destination unresolved: {self.value}'
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
    """Retain all declarations, even before operation evidence is available.

    This declaration inventory does not perform operation recognition or tracing.
    Later analysis can attach those facts without changing declaration identity.
    """
    return tuple(IntegrationFinding(declaration)
                 for declaration in discover_declarations(module))
