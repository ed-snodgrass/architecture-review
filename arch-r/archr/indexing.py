"""Source inventory for ordinary Java declarations and instance invocations.

This is deliberately not a call graph: receiver names are recorded without
selecting methods, inferring runtime wiring, or treating declarations as use.
The lexer and source boundary are shared with Feign discovery.
"""

from dataclasses import dataclass
import re

from .discovery import Token, _annotation, _balanced_end, read_java_sources, tokenize
from .module import Module


@dataclass(frozen=True)
class Invocation:
    receiver: str
    method_name: str
    argument_count: int
    source_path: str
    line: int
    # Unqualified receivers can be shadowed by parameters or local variables.
    field_receiver: bool = True
    explicit_type_arguments: bool = False


@dataclass(frozen=True)
class Method:
    name: str
    parameter_count: int
    source_path: str
    line: int
    invocations: tuple[Invocation, ...] = ()


@dataclass(frozen=True)
class Field:
    name: str
    type_name: str
    source_path: str
    line: int


@dataclass(frozen=True)
class JavaType:
    qualified_name: str
    kind: str
    source_path: str
    line: int
    fields: tuple[Field, ...]
    methods: tuple[Method, ...]


@dataclass(frozen=True)
class SourceIndex:
    types: tuple[JavaType, ...]


_IDENTIFIER = re.compile(r'[A-Za-z_$][\w$]*\Z')
_MODIFIERS = {'public', 'protected', 'private', 'static', 'final', 'abstract',
              'transient', 'volatile', 'synchronized', 'native', 'strictfp', 'default'}
_PRIMITIVES = {'boolean', 'byte', 'short', 'int', 'long', 'char', 'float', 'double', 'void'}
_JAVA_LANG = {'String', 'Object', 'Integer', 'Long', 'Boolean', 'Double', 'Float',
              'Byte', 'Short', 'Character', 'Number', 'Exception', 'RuntimeException'}


def _groups(tokens: list[Token]) -> list[list[Token]]:
    """Split commas outside nested delimiters (including generic declarations)."""
    groups = [[]]
    depth = 0
    for token in tokens:
        if token.text == ',' and depth == 0:
            groups.append([])
        else:
            groups[-1].append(token)
            if token.text in ('(', '[', '{', '<'):
                depth += 1
            elif token.text in (')', ']', '}', '>'):
                depth -= 1
    return [group for group in groups if group]


def _argument_count(tokens: list[Token]) -> int:
    # Recognize type-shaped constructor/method arguments, not comparisons.
    # Strings are single tokens; ordinary nested delimiters also hide commas.
    depth = 0
    count = 1 if tokens else 0
    i = 0
    while i < len(tokens):
        text = tokens[i].text
        if text == '<':
            end = _initializer_type_arguments_end(tokens, i)
            if end is not None:
                i = end + 1
                continue
        if text in ('(', '[', '{'):
            depth += 1
        elif text in (')', ']', '}'):
            depth -= 1
        elif text == ',' and depth == 0:
            count += 1
        i += 1
    return count


def _initializer_type_arguments_end(tokens: list[Token], start: int) -> int | None:
    """Recognize type arguments without treating comparisons as nesting.

    Only skip a balanced type-shaped list followed by constructor or generic
    method syntax. This keeps its commas out of declarator scanning while an
    ordinary comparison such as `a < b` cannot hide subsequent locals.
    """
    depth = 1
    i = start + 1
    while i < len(tokens):
        text = tokens[i].text
        if text == '<':
            depth += 1
        elif text == '>':
            depth -= 1
            if depth == 0:
                following = i + 1
                if following < len(tokens) and tokens[following].text in ('(', '.'):
                    return i
                if (following + 1 < len(tokens) and
                        _IDENTIFIER.fullmatch(tokens[following].text) and
                        tokens[following + 1].text == '('):
                    return i
                return None
        elif not (_IDENTIFIER.fullmatch(text) or text in ('.', ',', '?', '[', ']')):
            return None
        i += 1
    return None


def _local_declarations(tokens: list[Token], start: int) -> dict[int, str]:
    """Locate declarator names, including annotations and multiple locals.

    Register each name at its own token, not before preceding initializers.
    Types are deliberately not resolved: local receivers remain unsupported.
    """
    i = start
    while i < len(tokens):
        if tokens[i].text == '@':
            _, _, i = _annotation(tokens, i)
        elif tokens[i].text == 'final':
            i += 1
        else:
            break
    if i >= len(tokens) or not _IDENTIFIER.fullmatch(tokens[i].text):
        return {}
    if tokens[i].text in {'return', 'throw', 'new', 'this', 'super'}:
        return {}
    i += 1
    while i + 1 < len(tokens) and tokens[i].text == '.' and _IDENTIFIER.fullmatch(tokens[i + 1].text):
        i += 2
    if i < len(tokens) and tokens[i].text == '<':
        depth = 1
        i += 1
        while i < len(tokens) and depth:
            depth += (tokens[i].text == '<') - (tokens[i].text == '>')
            i += 1
    while i + 1 < len(tokens) and tokens[i].text == '[' and tokens[i + 1].text == ']':
        i += 2
    names = {}
    while i + 1 < len(tokens) and _IDENTIFIER.fullmatch(tokens[i].text):
        name_index = i
        i += 1
        while i + 1 < len(tokens) and tokens[i].text == '[' and tokens[i + 1].text == ']':
            i += 2
        if i >= len(tokens) or tokens[i].text not in ('=', ';', ',', ':', ')'):
            break
        names[name_index] = tokens[name_index].text
        # Skip the initializer, preserving only top-level declarator commas.
        depth = 0
        conditionals = 0
        while i < len(tokens):
            text = tokens[i].text
            if depth == 0:
                if text in (';', ')', ','):
                    break
                if text == '?':
                    conditionals += 1
                elif text == ':':
                    # An enhanced-for separator ends a declaration, but a
                    # ternary separator belongs to its initializer. Nested
                    # conditionals must not hide later comma declarators.
                    if not conditionals:
                        break
                    conditionals -= 1
            if text == '<':
                generic_end = _initializer_type_arguments_end(tokens, i)
                if generic_end is not None:
                    i = generic_end + 1
                    continue
            if text in ('(', '[', '{'):
                depth += 1
            elif text in (')', ']', '}'):
                depth -= 1
            i += 1
        if i >= len(tokens) or tokens[i].text != ',':
            break
        i += 1
    return names


def _statement_end(tokens: list[Token], start: int) -> int:
    """Find the extent of an ordinary loop body, including unbraced bodies."""
    if start >= len(tokens):
        return len(tokens)
    if tokens[start].text == '{':
        end = _balanced_end(tokens, start)
        return end if end is not None else len(tokens)
    if tokens[start].text in ('for', 'while', 'if', 'synchronized'):
        opening = start + 1
        if opening < len(tokens) and tokens[opening].text == '(':
            end = _balanced_end(tokens, opening)
            if end is not None:
                body_end = _statement_end(tokens, end + 1)
                if (tokens[start].text == 'if' and body_end + 1 < len(tokens)
                        and tokens[body_end + 1].text == 'else'):
                    return _statement_end(tokens, body_end + 2)
                return body_end
    i = start
    while i < len(tokens):
        if tokens[i].text == ';':
            return i
        if tokens[i].text in ('(', '[', '{'):
            end = _balanced_end(tokens, i)
            if end is None:
                return len(tokens)
            i = end
        i += 1
    return len(tokens)


def _invocations(tokens: list[Token], path: str,
                 parameters: tuple[str, ...] = ()) -> tuple[Invocation, ...]:
    calls = []
    # Each lexical scope has an inclusive end token. Explicit extents also
    # handle for headers, whose variables do not live in the enclosing block.
    scopes = [(set(parameters), len(tokens))]
    local_declarations = {}
    deferred_names = {}
    deferred_scopes = {}
    anonymous_bodies = {}
    i = 0
    while i < len(tokens):
        scopes = [(names, end) for names, end in scopes if i <= end]
        if tokens[i].text == 'for' and i + 1 < len(tokens) and tokens[i + 1].text == '(':
            header_end = _balanced_end(tokens, i + 1)
            if header_end is not None:
                names = set()
                scopes.append((names, _statement_end(tokens, header_end + 1)))
                declarations = _local_declarations(tokens, i + 2)
                for name_index, name in declarations.items():
                    separator = name_index + 1
                    while (separator + 1 < header_end and
                           tokens[separator].text == '[' and
                           tokens[separator + 1].text == ']'):
                        separator += 2
                    if separator < header_end and tokens[separator].text == ':':
                        # The iterable is evaluated outside the loop variable's
                        # scope. Activate its name only when the body begins.
                        deferred_names[name_index] = name
                        deferred_scopes.setdefault(header_end + 1, []).append((names, name))
        for names, name in deferred_scopes.pop(i, ()):
            names.add(name)
        if tokens[i].text == 'try' and i + 1 < len(tokens) and tokens[i + 1].text == '(':
            header_end = _balanced_end(tokens, i + 1)
            if header_end is not None:
                # Resources live in the header and try body, not subsequent
                # catches, finally blocks, or the enclosing method body.
                scopes.append((set(), _statement_end(tokens, header_end + 1)))
        if tokens[i].text == 'catch' and i + 1 < len(tokens) and tokens[i + 1].text == '(':
            header_end = _balanced_end(tokens, i + 1)
            if header_end is not None:
                # Register the parameter in a dedicated scope before scanning
                # its header; it must not leak into the enclosing block. The
                # last header token is the name, including multi-catch forms.
                names = set()
                if header_end > i + 2 and _IDENTIFIER.fullmatch(tokens[header_end - 1].text):
                    names.add(tokens[header_end - 1].text)
                scopes.append((names, _statement_end(tokens, header_end + 1)))
        if i in anonymous_bodies:
            i = anonymous_bodies[i] + 1
            continue
        if tokens[i].text == 'new':
            # A constructor's arguments belong to the enclosing method, but
            # an anonymous type's body (methods and initializers) does not.
            opening = i + 1
            while opening < len(tokens) and (
                    _IDENTIFIER.fullmatch(tokens[opening].text) or
                    tokens[opening].text in ('.', '<', '>', ',', '?')):
                opening += 1
            if opening < len(tokens) and tokens[opening].text == '(':
                end = _balanced_end(tokens, opening)
                if end is not None and end + 1 < len(tokens) and tokens[end + 1].text == '{':
                    body_end = _balanced_end(tokens, end + 1)
                    if body_end is not None:
                        anonymous_bodies[end + 1] = body_end
        # A class literal is an expression, not a local type declaration.
        # Do not attribute local type bodies to the enclosing method.
        if (tokens[i].text in ('class', 'interface', 'enum', 'record') and
                (i == 0 or tokens[i - 1].text != '.') and
                i + 1 < len(tokens) and _IDENTIFIER.fullmatch(tokens[i + 1].text)):
            while i < len(tokens) and tokens[i].text != '{':
                i += 1
            end = _balanced_end(tokens, i) if i < len(tokens) else None
            i = end + 1 if end is not None else len(tokens)
            continue
        if tokens[i].text == '{':
            end = _balanced_end(tokens, i)
            scopes.append((set(), end if end is not None else len(tokens)))
        # Only declaration positions, not a suffix of a qualified expression.
        if i == 0 or tokens[i - 1].text in ('{', '}', ';', '('):
            local_declarations.update(_local_declarations(tokens, i))
        if i in local_declarations and i not in deferred_names:
            scopes[-1][0].add(local_declarations[i])
        if tokens[i].text == '@':
            # Annotation argument syntax is not an invocation in the method.
            _, _, i = _annotation(tokens, i)
            continue
        # Retain chained-expression calls as uncertainty evidence, not field
        # links. The inner field invocation is indexed independently. Neither
        # a method result nor an array element is a supported receiver.
        if (tokens[i].text == '.' and i > 0 and
                tokens[i - 1].text in (')', ']') and i + 2 < len(tokens) and
                _IDENTIFIER.fullmatch(tokens[i + 1].text) and
                tokens[i + 2].text == '('):
            end = _balanced_end(tokens, i + 2)
            if end is not None:
                calls.append(Invocation('<chained expression>', tokens[i + 1].text,
                                        _argument_count(tokens[i + 3:end]), path,
                                        tokens[i + 1].line, False))
                i += 3
                continue
        start = i
        cursor = i
        receiver = tokens[i].text
        if receiver == 'this' and i + 2 < len(tokens) and tokens[i + 1].text == '.':
            receiver += '.' + tokens[i + 2].text
            cursor += 2
        if (i == 0 or tokens[i - 1].text not in ('.', 'new', '@')) and (
                _IDENTIFIER.fullmatch(tokens[cursor].text)) and cursor + 3 < len(tokens):
            method_index = cursor + 2
            explicit_types = False
            if tokens[cursor + 1].text == '.' and tokens[method_index].text == '<':
                type_end = _initializer_type_arguments_end(tokens, method_index)
                if type_end is not None:
                    method_index = type_end + 1
                    explicit_types = True
            if (tokens[cursor + 1].text == '.' and
                    method_index + 1 < len(tokens) and
                    _IDENTIFIER.fullmatch(tokens[method_index].text) and
                    tokens[method_index + 1].text == '('):
                end = _balanced_end(tokens, method_index + 1)
                if end is not None:
                    calls.append(Invocation(receiver, tokens[method_index].text,
                                            _argument_count(tokens[method_index + 2:end]),
                                            path, tokens[start].line,
                                            receiver.startswith('this.') or not any(
                                                receiver in names for names, _ in scopes),
                                            explicit_types))
                    # Continue inside arguments so nested field calls retain evidence.
                    i = method_index + 2
                    continue
        i += 1
    return tuple(calls)


def _clean(tokens: list[Token]) -> list[Token]:
    result = []
    i = 0
    while i < len(tokens):
        if tokens[i].text == '@':
            _, _, i = _annotation(tokens, i)
        elif tokens[i].text in _MODIFIERS:
            i += 1
        else:
            result.append(tokens[i])
            i += 1
    return result


def _parameter_name(tokens: list[Token]) -> str:
    """Read a declarator name independently of post-name array dimensions."""
    clean = _clean(tokens)
    end = len(clean)
    while end >= 2 and clean[end - 2].text == '[' and clean[end - 1].text == ']':
        end -= 2
    return clean[end - 1].text if end and _IDENTIFIER.fullmatch(clean[end - 1].text) else ''


def _resolve(name: str, package: str, imports: dict[str, str]) -> str:
    if name in _PRIMITIVES:
        return name
    first, dot, rest = name.partition('.')
    if first in imports:
        return imports[first] + (dot + rest if dot else '')
    if dot:
        return name
    if name in _JAVA_LANG:
        return 'java.lang.' + name
    return package + '.' + name if package else name


def _fields(declaration, path, package, imports):
    clean = _clean(declaration)
    if not clean or not _IDENTIFIER.fullmatch(clean[0].text):
        return []
    # Ordinary explicit type, optionally qualified. Generic fields are outside
    # the supported slice and must not be guessed as a different receiver type.
    i = 1
    while i + 1 < len(clean) and clean[i].text == '.' and _IDENTIFIER.fullmatch(clean[i + 1].text):
        i += 2
    name = ''.join(t.text for t in clean[:i])
    if i < len(clean) and clean[i].text in ('<', '['):
        return []
    fields = []
    for group in _groups(clean[i:]):
        if group and _IDENTIFIER.fullmatch(group[0].text) and (
                len(group) == 1 or group[1].text == '='):
            fields.append(Field(group[0].text, _resolve(name, package, imports),
                                path, declaration[0].line))
    return fields


def _members(tokens, opening, closing, path, package, imports):
    fields, methods = [], []
    i = opening + 1
    while i < closing:
        start = i
        declaration = []
        paren = None
        field_initializer = False
        while i < closing and tokens[i].text != ';':
            if tokens[i].text == '{':
                # An initializer body is part of a field declaration, not a
                # member body. Preserve the field and resume at its semicolon;
                # its anonymous methods must not become enclosing members.
                if not field_initializer:
                    break
                end = _balanced_end(tokens, i)
                if end is None:
                    return tuple(fields), tuple(methods)
                declaration.extend(tokens[i:end + 1])
                i = end + 1
            elif tokens[i].text == '@':
                _, _, end = _annotation(tokens, i)
                declaration.extend(tokens[i:end])
                i = end
            elif tokens[i].text in ('(', '['):
                end = _balanced_end(tokens, i)
                if end is None:
                    return tuple(fields), tuple(methods)
                if tokens[i].text == '(' and paren is None:
                    paren = len(declaration)
                declaration.extend(tokens[i:end + 1])
                i = end + 1
            else:
                if tokens[i].text == '=':
                    field_initializer = True
                declaration.append(tokens[i])
                i += 1
        if i >= closing:
            break
        body_end = _balanced_end(tokens, i) if tokens[i].text == '{' else i
        if body_end is None:
            break
        is_method = paren is not None and paren > 0 and not any(
            t.text in ('=', 'class', 'interface', 'enum', 'record', 'new')
            for t in _clean(declaration[:paren]))
        if is_method:
            end = _balanced_end(declaration, paren)
            if end is not None:
                methods.append(Method(declaration[paren - 1].text,
                                      len(_groups(declaration[paren + 1:end])),
                                      path, tokens[start].line,
                                      _invocations(tokens[i + 1:body_end], path,
                                                   tuple(_parameter_name(group) for group in
                                                         _groups(declaration[paren + 1:end])))
                                      if tokens[i].text == '{' else ()))
        elif tokens[i].text == ';':
            fields.extend(_fields(declaration, path, package, imports))
        # Skip initializer/nested type bodies, not their contents as members.
        i = body_end + 1
    return tuple(fields), tuple(methods)


def _extract(source: str, path: str) -> list[JavaType]:
    tokens = tokenize(source)
    package = ''
    imports = {}
    types = []
    i = 0
    while i < len(tokens):
        text = tokens[i].text
        if text in ('package', 'import'):
            end = i + 1
            while end < len(tokens) and tokens[end].text != ';':
                end += 1
            name = ''.join(t.text for t in tokens[i + 1:end])
            if text == 'package':
                package = name
            elif not name.startswith('static') and '*' not in name:
                imports[name.rsplit('.', 1)[-1]] = name
            i = end + 1
        elif text == '@':
            _, _, i = _annotation(tokens, i)
        elif text in ('class', 'interface') and i + 1 < len(tokens):
            opening = i + 2
            while opening < len(tokens) and tokens[opening].text not in ('{', ';'):
                opening += 1
            end = _balanced_end(tokens, opening) if opening < len(tokens) and tokens[opening].text == '{' else None
            if end is None:
                i += 1
                continue
            fields, methods = _members(tokens, opening, end, path, package, imports)
            name = tokens[i + 1].text
            types.append(JavaType(package + '.' + name if package else name,
                                  text, path, tokens[i].line, fields, methods))
            i = end + 1
        else:
            i += 1
    return types


def index_module(module: Module) -> SourceIndex:
    """Index Java sources without executing tools or changing module contents."""
    return SourceIndex(tuple(t for path, source in read_java_sources(module)
                             for t in _extract(source, path)))
