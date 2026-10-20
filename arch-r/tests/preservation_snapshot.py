"""Canonical analysis snapshot, usable with both iteration 004 and 005 code."""
from dataclasses import asdict
import hashlib
import json

from archr.discovery import discover_clients
from archr.findings import discover_findings
from archr.indexing import index_module
from archr.integrations import discover_declarations
from archr.interfaces import resolve_interface_index
from archr.module import load_module
from archr.report import render_report
from archr.resolution import resolve_index
from archr.traversal import trace_usage


def snapshot(path):
    module = load_module(path)
    clients = discover_clients(module)
    findings = discover_findings(module)
    index = index_module(module)
    usage = trace_usage(module)
    # The iteration 004 baseline covers traversal/coverage, not the additional
    # iteration 006 catch evidence carried alongside those unchanged results.
    traversal = asdict(usage)
    traversal.pop('failure_handling', None)
    values = {
        'clients': [asdict(item) for item in clients],
        'declarations': [asdict(item) for item in discover_declarations(module)],
        'findings_operations_queries_destinations': [asdict(item) for item in findings],
        'resolution': asdict(resolve_index(index)),
        'interface_resolution': asdict(resolve_interface_index(index)),
        'traversal_and_coverage': traversal,
    }
    report = render_report(module, clients, usage, findings=findings)
    values['diagram'] = report.split('```mermaid\n', 1)[1].split('```', 1)[0]
    return {key: hashlib.sha256(json.dumps(value, sort_keys=True,
                ensure_ascii=True, separators=(',', ':')).encode()).hexdigest()
            for key, value in values.items()}


if __name__ == '__main__':
    import sys
    print(json.dumps(snapshot(sys.argv[1]), indent=2, sort_keys=True))
