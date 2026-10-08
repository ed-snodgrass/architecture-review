"""Conservative, source-only discovery of Spring OpenFeign interfaces.

A small Java lexer keeps comments and string contents out of declaration matching.
Only direct string annotation values are reported as known values; expressions
are retained as evidence, never evaluated or resolved from configuration.
"""

from dataclasses import dataclass
import os
from pathlib import Path
import re

from .module import AnalysisError, Module, _require_directory


FEIGN_TYPE = "org.springframework.cloud.openfeign.FeignClient"


@dataclass(frozen=True)
class FeignClient:
    interface_name: str
    name: str | None
    url: str | None
    source_path: str
    line: int
    name_expression: str | None = None
    url_expression: str | None = None
    # Source offsets delimit the interface for subsequent operation discovery.
    body_start: int = 0
    body_end: int = 0


@dataclass(frozen=True)
class Token:
    text: str
    start: int
    end: int
    line: int


_LEX = re.compile(
    r'//[^\n]*|/\*.*?\*/|""".*?"""|"(?:\\.|[^"\\])*"|'
    r"'(?:\\.|[^'\\])*'|[\w$]+|[^\s]", re.DOTALL
)


def tokenize(source: str) -> list[Token]:
    result = []
    line = 1
    previous = 0
    for match in _LEX.finditer(source):
        line += source.count("\n", previous, match.start())
        text = match.group()
        if not text.startswith(("//", "/*")):
            result.append(Token(text, match.start(), match.end(), line))
        line += text.count("\n")
        previous = match.end()
    return result


def _balanced_end(tokens: list[Token], start: int) -> int | None:
    pairs = {"(": ")", "{": "}", "[": "]"}
    stack = []
    for index in range(start, len(tokens)):
        text = tokens[index].text
        if text in pairs:
            stack.append(pairs[text])
        elif text in pairs.values():
            if not stack or stack.pop() != text:
                return None
            if not stack:
                return index
    return None


def _annotation(tokens: list[Token], start: int):
    index = start + 1
    parts = []
    while index < len(tokens) and re.fullmatch(r"[\w$]+", tokens[index].text):
        parts.append(tokens[index].text)
        index += 1
        if index < len(tokens) and tokens[index].text == ".":
            index += 1
        else:
            break
    args = []
    if index < len(tokens) and tokens[index].text == "(":
        end = _balanced_end(tokens, index)
        if end is None:
            return "", [], len(tokens)
        args = tokens[index + 1:end]
        index = end + 1
    return ".".join(parts), args, index


def _attributes(tokens: list[Token]) -> dict[str, list[Token]]:
    groups = [[]]
    depth = 0
    for token in tokens:
        if token.text == "," and depth == 0:
            groups.append([])
            continue
        groups[-1].append(token)
        if token.text in ("(", "{", "["):
            depth += 1
        elif token.text in (")", "}", "]"):
            depth -= 1
    attributes = {}
    for group in groups:
        if len(group) >= 2 and group[1].text == "=":
            attributes[group[0].text] = group[2:]
        elif group:
            attributes["value"] = group
    return attributes


def _literal(tokens: list[Token]) -> str | None:
    if len(tokens) != 1:
        return None
    text = tokens[0].text
    if not text.startswith('"') or text.startswith('"""'):
        return None
    escapes = {"b": "\b", "t": "\t", "n": "\n", "f": "\f", "r": "\r",
               '"': '"', "'": "'", "\\": "\\", "s": " "}
    def decode(match):
        value = match.group(1)
        if value.startswith("u"):
            return chr(int(value.lstrip("u"), 16))
        if value[0] in "01234567":
            return chr(int(value, 8))
        return escapes.get(value, "\\" + value)
    return re.sub(r"\\(u+[0-9a-fA-F]{4}|[0-3][0-7]{0,2}|[4-7][0-7]?|.)",
                  decode, text[1:-1])


def extract_clients(source: str, source_path: str) -> list[FeignClient]:
    tokens = tokenize(source)
    imports = set()
    for index, token in enumerate(tokens):
        if token.text == "import":
            end = index + 1
            while end < len(tokens) and tokens[end].text != ";":
                end += 1
            imports.add("".join(t.text for t in tokens[index + 1:end]))
    short_name_allowed = (FEIGN_TYPE in imports or
                          "org.springframework.cloud.openfeign.*" in imports)
    # An explicit conflicting import must not be mistaken for Spring's type.
    if any(i.endswith(".FeignClient") and i != FEIGN_TYPE for i in imports):
        short_name_allowed = False
    clients = []
    for index, token in enumerate(tokens):
        if token.text != "@":
            continue
        annotation, args, next_index = _annotation(tokens, index)
        if annotation != FEIGN_TYPE and not (annotation == "FeignClient" and short_name_allowed):
            continue
        cursor = next_index
        while cursor < len(tokens):
            if tokens[cursor].text == "@":
                _, _, cursor = _annotation(tokens, cursor)
            elif tokens[cursor].text in ("public", "protected", "private", "abstract", "static", "strictfp"):
                cursor += 1
            else:
                break
        if cursor + 1 >= len(tokens) or tokens[cursor].text != "interface":
            continue
        interface_name = tokens[cursor + 1].text
        opening = cursor + 2
        while opening < len(tokens) and tokens[opening].text not in ("{", ";"):
            opening += 1
        if opening == len(tokens) or tokens[opening].text != "{":
            continue
        closing = _balanced_end(tokens, opening)
        if closing is None:
            continue
        attributes = _attributes(args)
        name_tokens = attributes.get("name") or attributes.get("value", [])
        url_tokens = attributes.get("url", [])
        name = _literal(name_tokens)
        if name == "" and "value" in attributes:
            name_tokens = attributes["value"]
            name = _literal(name_tokens)
        url = _literal(url_tokens)
        def expression(value):
            return source[value[0].start:value[-1].end] if value else None
        clients.append(FeignClient(
            interface_name, name, url, source_path, token.line,
            expression(name_tokens) if name is None else None,
            expression(url_tokens) if url is None else None,
            tokens[opening].end, tokens[closing].start,
        ))
    return clients


def discover_clients(module: Module) -> list[FeignClient]:
    """Read Java sources in stable relative-path order; never follow symlinks."""
    files: list[Path] = []
    def walk_error(error):
        raise AnalysisError(f"Cannot scan Java sources: {error}") from error
    try:
        for root, directories, names in os.walk(module.source_root, onerror=walk_error):
            directory = Path(root)
            _require_directory(directory)
            directories[:] = sorted(d for d in directories if not (directory / d).is_symlink())
            files.extend(directory / name for name in names
                         if name.endswith(".java") and not (directory / name).is_symlink())
        clients = []
        for path in sorted(files, key=lambda p: p.relative_to(module.path).as_posix()):
            if not path.stat().st_mode & 0o444:
                raise AnalysisError(f"Java source is not readable: {path}")
            source = path.read_text(encoding="utf-8")
            clients.extend(extract_clients(source, path.relative_to(module.path).as_posix()))
        return clients
    except (OSError, UnicodeError) as exc:
        raise AnalysisError(f"Cannot read Java sources: {exc}") from exc
