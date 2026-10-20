"""Source observations of integration-specific catch structure.

These records describe syntax only: they do not establish that a call throws,
that a handler executes, or that an application needs another adapter. Detection
and presentation are separate consumers of this immutable evidence model.
"""

from dataclasses import dataclass

from .integrations import IntegrationDeclaration
from .resolution import CallLink


@dataclass(frozen=True)
class FailureHandlingObservation:
    """One resolved direct integration call associated with one catch site.

    Retain the resolved link rather than a caller display name: it identifies
    the actual caller declaration and target operation, including overloads.
    Call offsets come from the indexed invocation; the catch offset identifies
    the catch keyword in the retained source, even for handlers on one line.
    No upstream traversal path is part of an observation's identity.
    """

    integration: IntegrationDeclaration
    call: CallLink
    catch_source_path: str
    catch_line: int
    catch_source_offset: int
    exception_type: str = 'feign.FeignException'

    @property
    def identity(self) -> tuple:
        """Deduplicate routes, not distinct call/catch sites or integrations."""
        caller = self.call.caller_method
        target = self.call.target_method
        return (
            self.integration.identity,
            (self.call.caller_type, caller.source_path, caller.line,
             caller.name, caller.parameter_count),
            (self.call.target_type, target.source_path, target.line,
             target.name, target.parameter_count),
            self.call.invocation.site_identity,
            (self.catch_source_path, self.catch_source_offset),
            self.exception_type,
        )
