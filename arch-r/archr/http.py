"""Literal RestTemplate facts, independent of library operation resolution."""
from bisect import bisect_left
from urllib.parse import urlsplit

from .discovery import _balanced_end, _literal, tokenize
from .indexing import index_source
from .resolution import REST_OPERATIONS

HTTP_METHOD = 'org.springframework.http.HttpMethod'
VERBS = frozenset({'GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS', 'TRACE'})


def rest_facts(source, invocation, *, tokens=None):
    """Return verb, literal destination, and its line; never evaluate expressions.

    A variable URL or verb leaves only that fact unresolved, not the operation.
    Only explicit type imports, the Spring package, or canonical names qualify
    HttpMethod; static/wildcard imports and same-name source types do not.
    """
    tokens = tokenize(source) if tokens is None else tokens
    verb = REST_OPERATIONS[invocation.method_name]
    if invocation.source_offset is None:
        return verb, None, invocation.line
    start = bisect_left(tokens, invocation.source_offset, key=lambda t: t.start)
    if start == len(tokens) or tokens[start].start != invocation.source_offset:
        return verb, None, invocation.line
    opening = start
    while opening < len(tokens) and tokens[opening].text != '(':
        opening += 1
    closing = _balanced_end(tokens, opening) if opening < len(tokens) else None
    if closing is None:
        return verb, None, invocation.line
    args = [[]]
    depth = 0
    for token in tokens[opening + 1:closing]:
        if token.text == ',' and depth == 0:
            args.append([])
            continue
        args[-1].append(token)
        if token.text in ('(', '[', '{'):
            depth += 1
        elif token.text in (')', ']', '}'):
            depth -= 1
    destination = _literal(args[0])
    line = args[0][0].line if args[0] else invocation.line
    if invocation.method_name == 'exchange' and len(args) > 1:
        verb = explicit_http_method(source, invocation, args[1], tokens=tokens)
    return verb, destination, line


def explicit_http_method(source, invocation, argument, *, tokens=None):
    """Resolve only explicit, unshadowed Spring HttpMethod constants."""
    tokens = tokenize(source) if tokens is None else tokens
    if argument:
        parts = ''.join(t.text for t in argument).split('.')
        if parts[-1] in VERBS and len(parts) > 1:
            name = '.'.join(parts[:-1])
            imports = set()
            package = ''
            for i, token in enumerate(tokens):
                if token.text in ('import', 'package'):
                    end = i + 1
                    while end < len(tokens) and tokens[end].text != ';':
                        end += 1
                    value = ''.join(t.text for t in tokens[i + 1:end])
                    if token.text == 'import':
                        imports.add(value)
                    else:
                        package = value
            index = index_source(source, invocation.source_path)
            source_types = index.declared_type_names
            # Java expression names take precedence over a type name here:
            # HttpMethod.GET or org.springframework.http.HttpMethod.GET may
            # read instance fields through a visible value rather than denote
            # the imported or fully qualified Spring constant.
            value_names = set(invocation.value_names)
            for owner in index.types:
                if any(call.site_identity == invocation.site_identity
                       for method in owner.methods for call in method.invocations):
                    value_names.update(field.name for field in owner.fields)
            local_http_method = any(n.rsplit('.', 1)[-1] == 'HttpMethod'
                                    for n in source_types)
            # A source type can also shadow the leading package identifier:
            # org.springframework... may denote nested types on a local org,
            # not the canonical Spring enum. Do not invent a verb in that case.
            package_shadowed = any(n.rsplit('.', 1)[-1] == 'org'
                                   for n in source_types)
            conflicts = any(n.endswith('.HttpMethod') and n != HTTP_METHOD for n in imports)
            if (HTTP_METHOD not in source_types and
                    ((name == HTTP_METHOD and parts[0] not in value_names
                      and not package_shadowed) or
                     (name == 'HttpMethod' and 'HttpMethod' not in value_names and
                      not local_http_method and not conflicts and
                      (HTTP_METHOD in imports or package == 'org.springframework.http')))):
                return parts[-1]
    return None


def destination_kind(value):
    """Classify visible source text without resolving placeholders or hosts."""
    if value is None or '${' in value or '{' in value or '}' in value:
        return 'unresolved'
    # A relative URI supplies a path, not an external host.
    try:
        parsed = urlsplit(value)
        return 'literal' if parsed.scheme and parsed.netloc else 'path (host unknown)'
    except ValueError:
        return 'unresolved'
