import type { Component, DataEntity, Workflow } from "../types";

// Simple SVG diagram renderers (no external chart dependency).

function colors(seed: string): string {
  const palette = ["#4f8cff", "#7c5cff", "#2fd47c", "#f5b544", "#f0566a", "#38c4d8", "#e879f9"];
  let h = 0;
  for (const c of seed) h = (h * 31 + c.charCodeAt(0)) % 997;
  return palette[h % palette.length];
}

export function ComponentDiagram({ components, height = 340 }: { components: Component[]; height?: number }) {
  const nodes = components.slice(0, 40);
  const byId = new Map(nodes.map((c) => [c.id, c]));
  const byName = new Map(nodes.map((c) => [c.name, c]));
  const cols = Math.ceil(Math.sqrt(nodes.length));
  const w = 900;
  const cw = w / cols;
  const rowH = 70;
  const rows = Math.ceil(nodes.length / cols);
  const h = Math.max(height, rows * rowH + 40);

  const pos = new Map<string, { x: number; y: number }>();
  nodes.forEach((n, i) => {
    pos.set(n.id, { x: (i % cols) * cw + cw / 2, y: Math.floor(i / cols) * rowH + 24 });
  });

  const edges: { x1: number; y1: number; x2: number; y2: number; color: string }[] = [];
  nodes.forEach((n) => {
    const from = pos.get(n.id)!;
    n.dependencies.slice(0, 4).forEach((dep) => {
      const target = byId.get(dep) ?? byName.get(dep);
      if (target && pos.has(target.id)) {
        const to = pos.get(target.id)!;
        edges.push({ x1: from.x, y1: from.y, x2: to.x, y2: to.y, color: colors(n.id) });
      }
    });
  });

  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="diagram">
      <defs>
        <marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
          <path d="M0,0 L6,3 L0,6" fill="#5a6a8a" />
        </marker>
      </defs>
      {edges.map((e, i) => (
        <line key={i} x1={e.x1} y1={e.y1} x2={e.x2} y2={e.y2} stroke="#3a465c" strokeWidth="1" markerEnd="url(#arrow)" />
      ))}
      {nodes.map((n) => {
        const p = pos.get(n.id)!;
        const color = colors(n.architectural_layer || n.type);
        return (
          <g key={n.id}>
            <rect x={p.x - cw / 2 + 4} y={p.y - 16} width={cw - 8} height={34} rx={7} fill="#1a2233" stroke={color} strokeWidth="1.2" />
            <text x={p.x} y={p.y + 2} textAnchor="middle" fill="#e6ebf5" fontSize="10" fontFamily="monospace">
              {n.name.slice(0, 14)}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

export function WorkflowDiagram({ workflow }: { workflow: Workflow }) {
  const steps = workflow.steps;
  const w = 900;
  const stepH = 56;
  const h = steps.length * stepH + 40;
  const cx = 260;
  const kindColor: Record<string, string> = {
    trigger: "#f5b544",
    transform: "#4f8cff",
    decision: "#f0566a",
    output: "#2fd47c",
    error: "#f0566a",
    external: "#e879f9",
  };
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="diagram">
      {steps.map((s, i) => {
        const y = i * stepH + 20;
        return (
          <g key={s.id}>
            <rect x={cx - 120} y={y} width={240} height={40} rx={8} fill="#1a2233" stroke={kindColor[s.kind] || "#4f8cff"} strokeWidth="1.2" />
            <text x={cx} y={y + 24} textAnchor="middle" fill="#e6ebf5" fontSize="11" fontFamily="monospace">
              {s.name.slice(0, 28)}
            </text>
            {i > 0 && <line x1={cx} y1={y - 14} x2={cx} y2={y} stroke="#3a465c" strokeWidth="1.5" markerEnd="url(#arrow)" />}
          </g>
        );
      })}
    </svg>
  );
}

export function DataModelDiagram({ entities }: { entities: DataEntity[] }) {
  const cols = Math.min(3, Math.max(1, Math.ceil(entities.length / 3)));
  const w = 900;
  const cw = w / cols;
  const rowH = 150;
  const rows = Math.ceil(entities.length / cols);
  const h = rows * rowH + 20;
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="diagram">
      {entities.map((e, i) => {
        const x = (i % cols) * cw + 12;
        const y = Math.floor(i / cols) * rowH + 12;
        return (
          <g key={e.name}>
            <rect x={x} y={y} width={cw - 24} height={rowH - 24} rx={8} fill="#1a2233" stroke="#4f8cff" strokeWidth="1.2" />
            <rect x={x} y={y} width={cw - 24} height={24} rx={8} fill="#243150" />
            <text x={x + 10} y={y + 17} fill="#e6ebf5" fontSize="12" fontWeight="bold">{e.name}</text>
            {e.columns.slice(0, 6).map((c, j) => (
              <text key={j} x={x + 10} y={y + 40 + j * 16} fill="#8b96ab" fontSize="10" fontFamily="monospace">
                {c.primary_key ? "🔑 " : c.foreign_key ? "🔗 " : ""}{c.name}: {c.type}
              </text>
            ))}
          </g>
        );
      })}
    </svg>
  );
}

export function LayerDiagram({ layers }: { layers: { name: string; components: string[] }[] }) {
  const w = 900;
  const lh = 58;
  const h = layers.length * lh + 30;
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="diagram">
      {layers.map((l, i) => (
        <g key={l.name}>
          <rect x={60} y={i * lh + 12} width={w - 120} height={lh - 16} rx={8} fill="#1a2233" stroke="#7c5cff" strokeWidth="1.2" />
          <text x={80} y={i * lh + 40} fill="#e6ebf5" fontSize="12" fontWeight="bold">{l.name}</text>
          <text x={80} y={i * lh + 56} fill="#8b96ab" fontSize="10" fontFamily="monospace">
            {l.components.slice(0, 12).join(", ")}
          </text>
        </g>
      ))}
    </svg>
  );
}
