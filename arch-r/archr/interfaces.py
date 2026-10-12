"""Declaration-only interface candidates, never verified runtime dispatch."""

from dataclasses import dataclass

from .indexing import JavaType, Method, SourceIndex, index_module
from .module import Module
from .resolution import CallLink, resolve_index


@dataclass(frozen=True)
class InterfaceConnection:
    link: CallLink
    interface_type: JavaType
    implementation_type: JavaType
    implementation_method: Method
    certainty: str = 'possible'
    reason: str = 'A unique direct local implementation is visible; runtime wiring is unverified.'


@dataclass(frozen=True)
class InterfaceDiagnostic:
    link: CallLink
    code: str
    message: str
    candidates: tuple[JavaType, ...] = ()


@dataclass(frozen=True)
class InterfaceResolution:
    connections: tuple[InterfaceConnection, ...]
    diagnostics: tuple[InterfaceDiagnostic, ...]


def resolve_interface_index(index: SourceIndex) -> InterfaceResolution:
    """Follow ordinary interfaces without consuming an additional call step.

    Existing source links retain their declared endpoints. Multiple candidates
    are never filtered by method availability to manufacture unique wiring.
    Feign declarations are terminal, regardless of visible implementations.
    """
    types = {java_type.qualified_name: java_type for java_type in index.types}
    # Build declaration candidates once. Method availability cannot narrow this
    # set: doing so would guess runtime wiring when several implementors exist.
    implementations: dict[str, list[JavaType]] = {}
    for java_type in sorted(index.types, key=lambda item: (
            item.qualified_name, item.source_path, item.line)):
        if java_type.kind != 'class' or java_type.abstract or java_type.generic:
            continue
        for interface_name in set(java_type.implements):
            implementations.setdefault(interface_name, []).append(java_type)

    connections, diagnostics = [], []
    for link in resolve_index(index).links:
        interface = types[link.target_type]
        if interface.kind != 'interface' or interface.feign:
            continue

        def diagnostic(code, message, candidates=()):
            diagnostics.append(InterfaceDiagnostic(link, code, message, candidates))

        if interface.generic:
            diagnostic('unsupported-interface',
                       f'Generic interface {interface.qualified_name} is outside the '
                       'supported ordinary non-generic interface analysis.')
            continue
        candidates = tuple(implementations.get(interface.qualified_name, ()))
        if not candidates:
            diagnostic('no-local-implementation',
                       f'No supported direct concrete implementation of {interface.qualified_name} '
                       'was found within the analyzed module src/main/java boundary. '
                       'This does not establish absence elsewhere or resolve inherited or generic wiring.')
        elif len(candidates) > 1:
            names = ', '.join(f'{candidate.qualified_name} '
                              f'({candidate.source_path}:{candidate.line})' for candidate in candidates)
            diagnostic('ambiguous-implementation',
                       f'Multiple direct concrete implementations of {interface.qualified_name}: '
                       f'{names}. No route selected; runtime wiring is unverified.', candidates)
        else:
            implementation = candidates[0]
            methods = tuple(method for method in implementation.methods
                            if method.name == link.target_method.name
                            and method.parameter_count == link.target_method.parameter_count)
            if not methods:
                diagnostic('unresolved-implementation-method',
                           f'No directly declared method {implementation.qualified_name}.'
                           f'{link.target_method.name} with {link.target_method.parameter_count} '
                           'arguments was found; inherited methods are not resolved.', candidates)
            elif len(methods) > 1:
                evidence = ', '.join(f'{method.source_path}:{method.line}' for method in methods)
                diagnostic('ambiguous-implementation-method',
                           f'Multiple methods in {implementation.qualified_name} match '
                           f'{link.target_method.name} by name and argument count ({evidence}); '
                           'argument types are not used to select an overload.', candidates)
            else:
                connections.append(InterfaceConnection(link, interface, implementation, methods[0]))
    return InterfaceResolution(tuple(connections), tuple(diagnostics))


def resolve_interfaces(module: Module) -> InterfaceResolution:
    """Read only production Java sources; do not compile or inspect runtime wiring."""
    return resolve_interface_index(index_module(module))
