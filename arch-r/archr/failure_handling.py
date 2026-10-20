"""Source observations of integration-specific catch structure.

These records describe syntax only: they do not establish that a call throws,
that a handler executes, or that an application needs another adapter. Detection
and presentation are separate consumers of this immutable evidence model.
"""

from dataclasses import dataclass

from .discovery import Token, _balanced_end, tokenize
from .indexing import SourceIndex, _statement_end
from .integrations import IntegrationDeclaration, declarations_from_index
from .resolution import CallLink, Resolution


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


def _imports_named(tokens: list[Token], simple_name: str) -> set[str]:
    imports = set()
    for i, token in enumerate(tokens):
        if token.text != 'import':
            continue
        end = i + 1
        while end < len(tokens) and tokens[end].text != ';':
            end += 1
        name = ''.join(t.text for t in tokens[i + 1:end])
        if name.rsplit('.', 1)[-1] == simple_name:
            imports.add(name)
    return imports


def _type_shadow(tokens: list[Token], name: str) -> bool:
    # Deliberately conservative across the compilation unit, including local
    # types and method type parameters. Uncertain identity is not evidence.
    for i, token in enumerate(tokens[:-1]):
        if (token.text in ('class', 'interface', 'enum', 'record', '<', ',')
                and tokens[i + 1].text == name):
            return True
    return False


def _try_sites(tokens: list[Token]):
    """Yield plain try bodies and single-type catch headers, never handler bodies."""
    for i, token in enumerate(tokens):
        if token.text != 'try' or i + 1 >= len(tokens):
            continue
        opening = i + 1
        if tokens[opening].text != '{':
            continue
        end = _balanced_end(tokens, opening)
        if end is None:
            continue
        catches = []
        cursor = end + 1
        while cursor + 1 < len(tokens) and tokens[cursor].text == 'catch':
            if tokens[cursor + 1].text != '(':
                break
            header_end = _balanced_end(tokens, cursor + 1)
            if header_end is None:
                break
            header = tokens[cursor + 2:header_end]
            if header and header[0].text == 'final':
                header = header[1:]
            # Exact token shapes exclude multi-catch, annotations and arrays.
            shape = [t.text for t in header[:-1]]
            if shape in (['FeignException'], ['feign', '.', 'FeignException']):
                catches.append((tokens[cursor], len(shape) == 1))
            body = header_end + 1
            if body >= len(tokens) or tokens[body].text != '{':
                break
            body_end = _balanced_end(tokens, body)
            if body_end is None:
                break
            cursor = body_end + 1
        yield opening, end, catches


def _try_ranges(tokens: list[Token]) -> dict[int, int]:
    """Full try extents, including resources, catch bodies and finally bodies.

    A nested try in a handler is still nested syntax. Retaining the whole
    statement prevents either it or its enclosing try from acquiring evidence.
    """
    ranges = {}
    for i, token in enumerate(tokens):
        if token.text != 'try' or i + 1 >= len(tokens):
            continue
        body = i + 1
        if tokens[body].text == '(':
            resources_end = _balanced_end(tokens, body)
            if resources_end is None:
                continue
            body = resources_end + 1
        if body >= len(tokens) or tokens[body].text != '{':
            continue
        end = _balanced_end(tokens, body)
        if end is None:
            continue
        cursor = end + 1
        while cursor < len(tokens) and tokens[cursor].text in ('catch', 'finally'):
            body = cursor + 1
            if tokens[cursor].text == 'catch':
                if body >= len(tokens) or tokens[body].text != '(':
                    break
                header_end = _balanced_end(tokens, body)
                if header_end is None:
                    break
                body = header_end + 1
            if body >= len(tokens) or tokens[body].text != '{':
                break
            body_end = _balanced_end(tokens, body)
            if body_end is None:
                break
            end = body_end
            cursor = end + 1
        ranges[i] = end
    return ranges


def _blocked_ranges(tokens: list[Token]) -> list[tuple[int, int]]:
    """Boundaries that cannot be crossed when associating a call and handler.

    The invocation index already omits local/anonymous type bodies. Include
    them here too so that a try inside such a body cannot become evidence even
    if a caller supplies a manually constructed resolved link.
    """
    blocked = []
    for i, token in enumerate(tokens):
        if (token.text == '-' and i + 1 < len(tokens)
                and tokens[i + 1].text == '>'):
            end = min(_statement_end(tokens, i + 2), len(tokens) - 1)
            blocked.append((token.start, tokens[end].end))
        if (token.text in ('class', 'interface', 'enum', 'record')
                and (i == 0 or tokens[i - 1].text != '.')):
            opening = i + 1
            while opening < len(tokens) and tokens[opening].text != '{':
                opening += 1
            if opening < len(tokens):
                end = _balanced_end(tokens, opening)
                if end is not None:
                    blocked.append((token.start, tokens[end].end))
        if token.text == 'new':
            opening = i + 1
            while opening < len(tokens) and tokens[opening].text not in ('(', ';', '{'):
                opening += 1
            if opening < len(tokens) and tokens[opening].text == '(':
                end = _balanced_end(tokens, opening)
                if (end is not None and end + 1 < len(tokens)
                        and tokens[end + 1].text == '{'):
                    body_end = _balanced_end(tokens, end + 1)
                    if body_end is not None:
                        blocked.append((tokens[end + 1].start, tokens[body_end].end))
    return blocked


def _caller_body(unit: list[Token], call: CallLink) -> list[Token]:
    """Recover the indexed method's body without changing call graph records."""
    method = call.caller_method
    offset = call.invocation.source_offset
    for i, token in enumerate(unit[:-1]):
        if (token.text != method.name
                or token.line != (method.declaration_line or method.line)
                or unit[i + 1].text != '('):
            continue
        end = _balanced_end(unit, i + 1)
        if end is None:
            continue
        opening = end + 1
        # Only a throws clause may intervene before the body.
        if opening < len(unit) and unit[opening].text == 'throws':
            while opening < len(unit) and unit[opening].text not in ('{', ';'):
                opening += 1
        if opening >= len(unit) or unit[opening].text != '{':
            continue
        closing = _balanced_end(unit, opening)
        if (closing is not None and offset is not None
                and unit[opening].start < offset < unit[closing].start):
            return unit[opening:closing + 1]
    return []


def detect_failure_handling(
        index: SourceIndex, resolution: Resolution,
) -> tuple[FailureHandlingObservation, ...]:
    """Observe resolved direct Feign calls inside bounded plain try bodies.

    This does not resolve new calls, inspect handler behavior or infer exception
    flow. Missing source/offsets or uncertain exception identity yield no claim.
    It is independent of upstream traversal and report presentation.
    """
    declarations = {d.declaring_type: d for d in declarations_from_index(index)
                    if d.mechanism == 'OpenFeign'}
    sources = {path: tokenize(source) for path, source in index.sources}
    types = {t.qualified_name: t for t in index.types}
    source_types = set(index.declared_type_names) | set(types)
    if 'feign.FeignException' in source_types:
        return ()
    observations = {}
    for call in resolution.links:
        integration = declarations.get(call.target_type)
        method = call.caller_method
        offset = call.invocation.source_offset
        if integration is None or offset is None:
            continue
        unit = sources.get(method.source_path, [])
        tokens = _caller_body(unit, call)
        if not tokens or not any(t.start == offset for t in tokens):
            continue
        blocked = _blocked_ranges(tokens)
        if any(start <= offset < end for start, end in blocked):
            continue
        # A fully qualified name can itself be shadowed by a source type or
        # type parameter named `feign`. Do not guess in that situation.
        caller = types.get(call.caller_type)
        package = call.caller_type.rpartition('.')[0]
        if (_type_shadow(unit, 'feign')
                or (package + '.feign' if package else 'feign') in source_types
                or _imports_named(unit, 'feign')):
            continue
        simple_known = (_imports_named(unit, 'FeignException') == {'feign.FeignException'}
                        and not _type_shadow(unit, 'FeignException')
                        and caller is not None and not caller.extends
                        and not caller.implements)
        try_ranges = _try_ranges(tokens)
        for opening, end, catches in _try_sites(tokens):
            if not tokens[opening].start < offset < tokens[end].start:
                continue
            # Reject both sides of nested syntax, including nesting in a
            # catch/finally body or inside a try-with-resources statement.
            start = opening - 1
            statement_end = try_ranges.get(start, end)
            if any(start < other < statement_end or other < start < other_end
                   for other, other_end in try_ranges.items()):
                continue
            for catch, simple in catches:
                if simple and not simple_known:
                    continue
                observation = FailureHandlingObservation(
                    integration, call, method.source_path, catch.line, catch.start)
                observations.setdefault(observation.identity, observation)
    return tuple(sorted(observations.values(), key=lambda o: (
        o.call.invocation.source_path, o.call.invocation.source_offset,
        o.catch_source_offset, o.integration.identity)))
