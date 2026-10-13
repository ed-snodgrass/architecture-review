"""Resolve ordinary field calls to exact source method endpoints.

Links describe source invocations, not execution or transitive relationships.
Interface methods are endpoints here; selecting implementations and traversing
backward are separate analysis steps.
"""

from dataclasses import dataclass

from .indexing import Field, Invocation, Method, SourceIndex, index_module
from .module import Module


@dataclass(frozen=True)
class CallLink:
    caller_type: str
    caller_method: Method
    receiver_field: Field
    target_type: str
    target_method: Method
    invocation: Invocation


@dataclass(frozen=True)
class Diagnostic:
    caller_type: str
    caller_method: Method
    invocation: Invocation
    code: str
    message: str
    candidates: tuple[Method, ...] = ()
    # Only unshadowed field evidence may connect a gap to a finding.
    receiver_field: Field | None = None


@dataclass(frozen=True)
class Resolution:
    links: tuple[CallLink, ...]
    diagnostics: tuple[Diagnostic, ...]


def resolve_index(index: SourceIndex) -> Resolution:
    """Match name and arity only; never guess between same-arity overloads."""
    types = {}
    for java_type in index.types:
        types.setdefault(java_type.qualified_name, []).append(java_type)
    links, diagnostics = [], []
    for caller in index.types:
        fields = {field.name: field for field in caller.fields}
        for method in caller.methods:
            for invocation in method.invocations:
                receiver = invocation.receiver
                # Same-class helpers are deliberately not followed.
                if receiver == 'this':
                    continue
                field = fields.get(receiver.removeprefix('this.'))

                def unresolved(code, message, candidates=()):
                    diagnostics.append(Diagnostic(caller.qualified_name, method,
                                                  invocation, code, message, candidates,
                                                  field if invocation.field_receiver else None))

                if invocation.explicit_type_arguments:
                    unresolved('unsupported-syntax',
                               f'Invocation {receiver}.{invocation.method_name} uses explicit '
                               'generic type arguments; generic method resolution is not supported.')
                    continue
                if not invocation.field_receiver or field is None:
                    unresolved('unsupported-receiver',
                               f'Receiver {receiver} is not an unshadowed explicitly typed field; '
                               'local, parameter and other receiver forms are not followed.')
                    continue
                targets = types.get(field.type_name, [])
                if len(targets) != 1:
                    unresolved('unresolved-type',
                               f'Type {field.type_name} has no unique declaration within '
                               'the analyzed module src/main/java boundary.')
                    continue
                candidates = tuple(m for m in targets[0].methods
                                   if m.name == invocation.method_name and
                                   m.parameter_count == invocation.argument_count)
                if not candidates:
                    unresolved('unresolved-method',
                               f'No declared method {field.type_name}.{invocation.method_name} '
                               f'with {invocation.argument_count} arguments was found; '
                               'inherited methods and same-class helpers are not resolved.')
                elif len(candidates) > 1:
                    unresolved('ambiguous-overload',
                               f'Multiple declarations of {field.type_name}.{invocation.method_name} '
                               f'match {invocation.argument_count} arguments; argument types '
                               'are not used to select an overload.', candidates)
                else:
                    links.append(CallLink(caller.qualified_name, method, field,
                                          targets[0].qualified_name, candidates[0], invocation))
    return Resolution(tuple(links), tuple(diagnostics))


def resolve_calls(module: Module) -> Resolution:
    """Read only Java production sources; do not compile or execute the module."""
    return resolve_index(index_module(module))
