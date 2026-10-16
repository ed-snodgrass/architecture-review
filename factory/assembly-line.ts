export type Edge = { from: string; to: string; label?: string };

export function parseAssemblyLine(source: string): Edge[] {
  return [...source.matchAll(/\b([A-Za-z][\w-]*)\s*->\s*([A-Za-z][\w-]*)(?:\s*\[\s*label\s*=\s*"([^"]+)"\s*\])?/g)]
    .map(match => ({
      from: match[1],
      to: match[2],
      label: match[3],
    }));
}

export function machineNames(edges: Edge[]): Set<string> {
  return new Set(edges.flatMap(edge => [edge.from, edge.to]));
}

function reachesFinish(
  edges: Edge[],
  node: string,
  seen = new Set<string>(),
): boolean {
  if (node === 'finish') return true;
  if (seen.has(node)) return false;
  seen.add(node);
  return edges.some(edge =>
    edge.from === node && reachesFinish(edges, edge.to, new Set(seen)),
  );
}

export function assemblyLineError(edges: Edge[]): string | undefined {
  for (const name of [...new Set(edges.map(edge => edge.from))].reverse()) {
    if (!reachesFinish(edges, name)) return `finish cannot be reached from ${name}`;
  }

  for (const name of new Set(edges.map(edge => edge.from))) {
    const outgoing = edges.filter(edge => edge.from === name);
    if (outgoing.length < 2 || outgoing.some(edge => edge.label)) continue;

    const branchEdges = outgoing.map(edge =>
      edges.filter(candidate => candidate.from === edge.to),
    );
    const meetingPoints = branchEdges.map(branch => branch[0]?.to);

    if (
      branchEdges.some(
        branch => branch.length !== 1 || branch[0].label !== undefined,
      )
      || new Set(meetingPoints).size !== 1
    ) {
      return `The branches from ${name} do not meet`;
    }
  }
}

export function outputFields(edges: Edge[], name: string): string[] {
  return [...new Set(
    edges
      .filter(edge => edge.from === name && edge.label)
      .map(edge => edge.label!.replace(/^not /, '')),
  )];
}

export function selectRoute(
  edges: Edge[],
  name: string,
  result: Record<string, unknown>,
): { next: string } | { error: string } {
  const outgoing = edges.filter(edge => edge.from === name);
  for (const edge of outgoing) {
    if (!edge.label) continue;
    const negative = edge.label.startsWith('not ');
    const field = edge.label.replace(/^not /, '');
    if (!(field in result)) {
      return { error: `The result of ${name} has no field "${field}"` };
    }
    if (Boolean(result[field]) !== negative) return { next: edge.to };
  }

  const direct = outgoing.find(edge => !edge.label);
  if (direct) return { next: direct.to };
  return { error: `The result of ${name} did not select an edge` };
}
