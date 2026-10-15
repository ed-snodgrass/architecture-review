"""Resolve ordinary field calls to exact source method endpoints.

Links describe source invocations, not execution or transitive relationships.
Interface methods are endpoints here; selecting implementations and traversing
backward are separate analysis steps. Direct Spring Data JPA repositories and
explicit JdbcTemplate fields expose bounded library endpoints without library
source; other inherited operations remain outside scope.
"""

from dataclasses import dataclass

from .indexing import Field, Invocation, Method, SourceIndex, index_module
from .module import Module
from .discovery import tokenize
from .webclient import webclient_expression
from .integrations import declarations_from_index, repository_types_from_index


REPOSITORY_OPERATIONS = frozenset({
    'save', 'saveAll', 'findById', 'findAll', 'existsById', 'count',
    'delete', 'deleteById', 'deleteAll',
})
JDBC_OPERATIONS = frozenset({
    'query', 'queryForObject', 'queryForList', 'update', 'execute', 'batchUpdate',
})
REST_OPERATIONS = {
    'getForObject': 'GET', 'getForEntity': 'GET',
    'postForObject': 'POST', 'postForEntity': 'POST', 'put': 'PUT',
    'patchForObject': 'PATCH', 'delete': 'DELETE',
    'headForHeaders': 'HEAD', 'optionsForAllow': 'OPTIONS', 'exchange': None,
}
OBJECT_METHODS = frozenset({'toString', 'equals', 'hashCode'})


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
    """Match source methods by name/arity; recognize bounded library operations.

    Known JdbcTemplate and inherited repository endpoints preserve the observed
    arity without claiming to resolve a library overload or validate arguments.
    Never guess between same-arity source overloads.
    """
    types = {}
    for java_type in index.types:
        types.setdefault(java_type.qualified_name, []).append(java_type)
    repositories = repository_types_from_index(index)
    library_fields = {(d.declaring_type, d.field_name): d.mechanism
                      for d in declarations_from_index(index)
                      if d.mechanism in ('Spring JDBC', 'Spring HTTP', 'Spring reactive HTTP')}
    sources = dict(index.sources)
    tokens = {}
    links, diagnostics = [], []
    for caller in index.types:
        fields = {field.name: field for field in caller.fields}
        for method in caller.methods:
            expressions = {}
            segments = set()
            for invocation in method.invocations:
                field_name = invocation.receiver.removeprefix('this.')
                if (invocation.field_receiver and not invocation.explicit_type_arguments and
                        library_fields.get((caller.qualified_name, field_name)) == 'Spring reactive HTTP' and
                        invocation.source_path in sources):
                    path = invocation.source_path
                    if path not in tokens:
                        tokens[path] = tokenize(sources[path])
                    expression = webclient_expression(sources[path], invocation, tokens[path])
                    if expression is not None:
                        expressions[invocation.site_identity] = expression
                        segments.update(expression.segment_offsets)
            for invocation in method.invocations:
                if (invocation.receiver == '<chained expression>' and
                        invocation.source_offset in segments):
                    continue
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
                mechanism = library_fields.get((caller.qualified_name, field.name))
                if mechanism == 'Spring reactive HTTP':
                    expression = expressions.get(invocation.site_identity)
                    if expression is not None:
                        if expression.request_operation is not None:
                            endpoint = Method(expression.request_operation, invocation.argument_count,
                                              field.source_path, field.line)
                            links.append(CallLink(caller.qualified_name, method, field,
                                                  field.type_name, endpoint, invocation))
                        # Configuration is not a request caller or a resolution gap.
                        continue
                    unresolved('unsupported-operation',
                               f'{invocation.method_name} is not a supported WebClient expression root.')
                    continue
                if mechanism is not None:
                    supported = (JDBC_OPERATIONS if mechanism == 'Spring JDBC'
                                 else REST_OPERATIONS)
                    if invocation.method_name in supported:
                        # A bounded library endpoint, cited at the typed field;
                        # no library source or overload/type inference required.
                        endpoint = Method(invocation.method_name, invocation.argument_count,
                                          field.source_path, field.line)
                        links.append(CallLink(caller.qualified_name, method, field,
                                              field.type_name, endpoint, invocation))
                    else:
                        unresolved('unsupported-operation',
                                   f'{invocation.method_name} is not a supported {mechanism} operation.')
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
                if field.type_name in repositories:
                    if invocation.method_name in OBJECT_METHODS:
                        unresolved('unsupported-operation',
                                   f'{invocation.method_name} is not a persistence operation.')
                        continue
                    if not candidates and invocation.method_name in REPOSITORY_OPERATIONS:
                        # Known inherited library endpoint: no implementation or
                        # library source is required. The citation identifies the
                        # repository declaration, not a fabricated library method.
                        repository = targets[0]
                        candidates = (Method(invocation.method_name,
                                             invocation.argument_count,
                                             repository.source_path, repository.line),)
                if not candidates:
                    excluded = ('inherited methods outside the supported repository operations'
                                if field.type_name in repositories else 'inherited methods')
                    unresolved('unresolved-method',
                               f'No declared method {field.type_name}.{invocation.method_name} '
                               f'with {invocation.argument_count} arguments was found; '
                               f'{excluded} and same-class helpers are not resolved.')
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
