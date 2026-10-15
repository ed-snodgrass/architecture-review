"""Check evidence retained in analysis when iteration 005 omits verbose citations."""
from dataclasses import fields, is_dataclass
from archr.module import load_module
from archr.discovery import discover_clients
from archr.findings import discover_findings
from archr.traversal import trace_usage


def locations(root):
    module = load_module(root)
    found = set()
    def visit(value):
        if is_dataclass(value):
            path = getattr(value, 'source_path', None)
            if path:
                for key in ('line', 'declaration_line'):
                    line = getattr(value, key, None)
                    if line:
                        found.add(f'{path}:{line}')
            for field in fields(value):
                visit(getattr(value, field.name))
        elif isinstance(value, (tuple, list)):
            for item in value:
                visit(item)
    visit((discover_clients(module), discover_findings(module), trace_usage(module)))
    return found
