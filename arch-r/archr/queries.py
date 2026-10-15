"""Bounded literal query evidence; expressions are never evaluated."""

from bisect import bisect_left
from dataclasses import dataclass
import re

from .discovery import Token, _attributes, _balanced_end, _literal, tokenize
from .indexing import Invocation, Method


JPA_QUERY = 'org.springframework.data.jpa.repository.Query'
JPQL_EXPLANATION = ('JPQL queries Java persistence entities rather than database tables.')


@dataclass(frozen=True)
class QueryEvidence:
    preview: str | None
    source_path: str
    line: int
    language: str = 'SQL'


def jdbc_query(source: str, invocation: Invocation,
               *, tokens: list[Token] | None = None) -> QueryEvidence:
    """Inspect only the first argument at this exact invocation site.

    Unknown overloads still have call evidence. In particular a callback,
    variable, concatenation or batch array is not invented SQL text.
    """
    # Callers analyzing several operations in one file can reuse its tokens.
    if tokens is None:
        tokens = tokenize(source)
    if invocation.source_offset is None:
        return QueryEvidence(None, invocation.source_path, invocation.line)
    # Tokens retain source order. Avoid rescanning the file from the beginning
    # for each JDBC operation when callers reuse a compilation unit's tokens.
    start = bisect_left(tokens, invocation.source_offset, key=lambda token: token.start)
    if start == len(tokens) or tokens[start].start != invocation.source_offset:
        return QueryEvidence(None, invocation.source_path, invocation.line)
    opening = start
    while opening < len(tokens) and tokens[opening].text != '(':
        opening += 1
    closing = _balanced_end(tokens, opening) if opening < len(tokens) else None
    if closing is None:
        return QueryEvidence(None, invocation.source_path, invocation.line)
    argument = []
    depth = 0
    for token in tokens[opening + 1:closing]:
        if token.text == ',' and depth == 0:
            break
        argument.append(token)
        if token.text in ('(', '[', '{'):
            depth += 1
        elif token.text in (')', ']', '}'):
            depth -= 1
    return QueryEvidence(query_preview(argument), invocation.source_path,
                         argument[0].line if argument else invocation.line)


def query_preview(argument: list[Token]) -> str | None:
    """Read one literal only, with the same bounded preview for JDBC and JPA."""
    literal = _literal(argument)
    if len(argument) == 1 and argument[0].text.startswith('"""'):
        token = argument[0]
        # Text blocks strip incidental indentation and trailing whitespace
        # before decoding escapes. This order matters for line continuations:
        # indentation must not become a space inside a joined SQL token.
        text = token.text[3:-3].replace('\r\n', '\n').replace('\r', '\n')
        opening_line, separator, text_body = text.partition('\n')
        if separator and not opening_line.strip():
            lines = text_body.split('\n')
            determining = [line for line in lines if line.strip()]
            # The closing delimiter's indentation also bounds removal, even
            # when its line has no content (including a column-zero delimiter).
            if not lines[-1].strip():
                determining.append(lines[-1])
            indent = min((len(line) - len(line.lstrip(' \t\f'))
                          for line in determining), default=0)
            text = '\n'.join(line[indent:].rstrip(' \t\f') for line in lines)
        # Java normalizes source line terminators before interpreting escapes,
        # including a backslash followed by CRLF/CR.
        # Consume escaped backslashes as pairs so only an unescaped final
        # backslash joins lines ("\\\\" followed by a newline does not).
        text = re.sub(r'\\\\|\\\r?\n',
                      lambda match: '' if '\n' in match[0] else match[0], text)
        literal = _literal([Token('"' + text + '"', token.start, token.end, token.line)])
    preview = None
    if literal is not None:
        # Java Unicode escapes can represent one supplementary character as
        # a UTF-16 surrogate pair. Count it as one Unicode character, just as
        # when the same character appears directly in the source literal.
        literal = re.sub(
            r'[\ud800-\udbff][\udc00-\udfff]',
            lambda match: chr(0x10000 + ((ord(match[0][0]) - 0xd800) << 10)
                              + ord(match[0][1]) - 0xdc00), literal)
        preview = ' '.join(literal.split())
        if len(preview) > 100:
            preview = preview[:99] + '…'
    return preview


def repository_queries(method: Method) -> tuple[QueryEvidence, ...]:
    """Extract only Spring @Query value evidence, never named or derived SQL.

    Language certainty is independent of value certainty. Only the literal
    boolean tokens true/false select a language; constants are not evaluated.
    """
    queries = []
    for annotation in method.annotations:
        if annotation.type_name != JPA_QUERY:
            continue
        attributes = _attributes(list(annotation.arguments))
        # @Query(name = "...") references a named query, not visible query text.
        if 'value' not in attributes:
            continue
        value = attributes['value']
        native = attributes.get('nativeQuery')
        if native is None or [token.text for token in native] == ['false']:
            language = 'JPQL'
        elif [token.text for token in native] == ['true']:
            language = 'SQL'
        else:
            language = 'Query (language unresolved)'
        queries.append(QueryEvidence(
            query_preview(value), method.source_path,
            value[0].line if value else annotation.line, language))
    return tuple(queries)
