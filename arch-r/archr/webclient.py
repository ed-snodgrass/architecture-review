"""Bounded WebClient fluent expressions, never data-flow or runtime analysis."""
from bisect import bisect_left
from dataclasses import dataclass

from .discovery import _balanced_end, _literal

VERBS = {'get': 'GET', 'post': 'POST', 'put': 'PUT', 'patch': 'PATCH',
         'delete': 'DELETE', 'head': 'HEAD', 'options': 'OPTIONS'}
REQUESTS = frozenset({'retrieve', 'exchangeToMono', 'exchangeToFlux'})
CONFIGURATION = frozenset({'uri', 'header', 'headers', 'accept', 'acceptCharset',
                           'contentType', 'contentLength', 'cookie', 'cookies',
                           'attribute', 'attributes', 'body', 'bodyValue',
                           'bodyValueWithType', 'ifModifiedSince', 'ifNoneMatch',
                           'httpRequest'})


@dataclass(frozen=True)
class FluentExpression:
    http_method: str | None
    destination: str | None
    destination_line: int
    request_operation: str | None
    request_line: int | None
    # Chained calls belong to this expression, not separate receiver gaps.
    segment_offsets: frozenset[int]


def webclient_expression(source, invocation, tokens):
    """Inspect only adjacent fluent calls rooted at this exact field site.

    Nested argument calls remain separate sites. A variable/helper result is
    never followed. A request operation is source evidence, not subscription.
    """
    from .http import explicit_http_method

    if invocation.source_offset is None or invocation.method_name not in (*VERBS, 'method'):
        return None
    start = bisect_left(tokens, invocation.source_offset, key=lambda t: t.start)
    if start == len(tokens) or tokens[start].start != invocation.source_offset:
        return None
    opening = start
    while opening < len(tokens) and tokens[opening].text != '(':
        opening += 1
    end = _balanced_end(tokens, opening) if opening < len(tokens) else None
    if end is None:
        return None
    argument = tokens[opening + 1:end]
    if invocation.method_name in VERBS and argument:
        return None
    verb = (VERBS[invocation.method_name] if invocation.method_name in VERBS else
            explicit_http_method(source, invocation, argument, tokens=tokens))
    destination, line, request = None, invocation.line, None
    request_line = None
    offsets = set()
    cursor = end + 1
    while (cursor + 3 < len(tokens) and tokens[cursor].text == '.' and
           tokens[cursor + 2].text == '('):
        name = tokens[cursor + 1].text
        closing = _balanced_end(tokens, cursor + 2)
        if closing is None:
            break
        if request is None and name not in CONFIGURATION | REQUESTS:
            break
        offsets.add(tokens[cursor + 1].start)
        if name == 'uri' and request is None:
            # uri(String, Object...) still exposes its literal template. Keep
            # placeholders unresolved; never evaluate expansion arguments,
            # URI objects, lambdas, or concatenated expressions.
            arguments = tokens[cursor + 3:closing]
            depth = 0
            first_end = len(arguments)
            for position, token in enumerate(arguments):
                if token.text == ',' and depth == 0:
                    first_end = position
                    break
                if token.text in ('(', '[', '{'):
                    depth += 1
                elif token.text in (')', ']', '}'):
                    depth -= 1
            destination = _literal(arguments[:first_end])
            line = tokens[cursor + 3].line if closing > cursor + 3 else invocation.line
        if request is None and name in REQUESTS:
            request = name
            request_line = tokens[cursor + 1].line
        cursor = closing + 1
    return FluentExpression(verb, destination, line, request, request_line, frozenset(offsets))
