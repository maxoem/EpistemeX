import {GraphView} from "../api/types";

function escapeXml(unsafe: any): string {
  if (unsafe === null || unsafe === undefined) return "";
  return String(unsafe)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

export function exportGraphToJson(graphData: GraphView, runId?: string | null): void {
  const dataStr = JSON.stringify(graphData, null, 2);
  const blob = new Blob([dataStr], { type: "application/json" });
  downloadBlob(blob, `graph-snapshot-${runId || "active"}-${Date.now()}.json`);
}

export function exportGraphToGraphML(graphData: GraphView, runId?: string | null): void {
  const { nodes = [], edges = [] } = graphData;

  const xmlLines: string[] = [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<graphml xmlns="http://graphml.graphdrawing.org/xmlns"',
    '         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"',
    '         xsi:schemaLocation="http://graphml.graphdrawing.org/xmlns http://graphml.graphdrawing.org/xmlns/1.0/graphml.xsd">',
    '  <key id="label" for="node" attr.name="label" attr.type="string"/>',
    '  <key id="layer" for="node" attr.name="layer" attr.type="int"/>',
    '  <key id="type" for="node" attr.name="type" attr.type="string"/>',
    '  <key id="plausibility" for="node" attr.name="plausibility" attr.type="float"/>',
    '  <key id="confidence" for="node" attr.name="confidence" attr.type="float"/>',
    '  <key id="edge_type" for="edge" attr.name="type" attr.type="string"/>',
    '  <key id="polarity" for="edge" attr.name="polarity" attr.type="int"/>',
    '  <key id="weight" for="edge" attr.name="weight" attr.type="float"/>',
    '  <graph id="G" edgedefault="directed">',
  ];

  nodes.forEach((n) => {
    xmlLines.push(`    <node id="${escapeXml(n.id)}">`);
    xmlLines.push(`      <data key="label">${escapeXml(n.label)}</data>`);
    xmlLines.push(`      <data key="layer">${n.layer ?? 2}</data>`);
    xmlLines.push(`      <data key="type">${escapeXml(n.type)}</data>`);
    if (n.plausibility !== undefined && n.plausibility !== null) {
      xmlLines.push(`      <data key="plausibility">${n.plausibility}</data>`);
    }
    if (n.confidence !== undefined && n.confidence !== null) {
      xmlLines.push(`      <data key="confidence">${n.confidence}</data>`);
    }
    xmlLines.push("    </node>");
  });

  edges.forEach((e) => {
    xmlLines.push(`    <edge id="${escapeXml(e.id)}" source="${escapeXml(e.source)}" target="${escapeXml(e.target)}">`);
    xmlLines.push(`      <data key="edge_type">${escapeXml(e.type)}</data>`);
    if (e.polarity !== undefined && e.polarity !== null) {
      xmlLines.push(`      <data key="polarity">${e.polarity}</data>`);
    }
    if (e.weight !== undefined && e.weight !== null) {
      xmlLines.push(`      <data key="weight">${e.weight}</data>`);
    }
    xmlLines.push("    </edge>");
  });

  xmlLines.push("  </graph>");
  xmlLines.push("</graphml>");

  const blob = new Blob([xmlLines.join("\n")], { type: "application/xml" });
  downloadBlob(blob, `graph-topology-${runId || "active"}-${Date.now()}.graphml`);
}

export function exportGraphToGexf(graphData: GraphView, runId?: string | null): void {
  const { nodes = [], edges = [] } = graphData;

  const xmlLines: string[] = [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<gexf xmlns="http://www.gexf.net/1.2draft" version="1.2">',
    '  <meta lastmodifieddate="' + new Date().toISOString().slice(0, 10) + '">',
    '    <creator>GLP Studio (Epistemic Graph Analysis)</creator>',
    '    <description>Research Theory Graph Export</description>',
    '  </meta>',
    '  <graph defaultedgetype="directed" mode="static">',
    '    <attributes class="node">',
    '      <attribute id="0" title="layer" type="integer"/>',
    '      <attribute id="1" title="type" type="string"/>',
    '      <attribute id="2" title="confidence" type="float"/>',
    '    </attributes>',
    '    <attributes class="edge">',
    '      <attribute id="0" title="type" type="string"/>',
    '      <attribute id="1" title="polarity" type="integer"/>',
    '      <attribute id="2" title="weight" type="float"/>',
    '    </attributes>',
    '    <nodes>',
  ];

  nodes.forEach((n) => {
    xmlLines.push(`      <node id="${escapeXml(n.id)}" label="${escapeXml(n.label)}">`);
    xmlLines.push("        <attvalues>");
    xmlLines.push(`          <attvalue for="0" value="${n.layer ?? 2}"/>`);
    xmlLines.push(`          <attvalue for="1" value="${escapeXml(n.type)}"/>`);
    if (n.confidence !== undefined && n.confidence !== null) {
      xmlLines.push(`          <attvalue for="2" value="${n.confidence}"/>`);
    }
    xmlLines.push("        </attvalues>");
    xmlLines.push("      </node>");
  });

  xmlLines.push("    </nodes>");
  xmlLines.push("    <edges>");

  edges.forEach((e) => {
    xmlLines.push(`      <edge id="${escapeXml(e.id)}" source="${escapeXml(e.source)}" target="${escapeXml(e.target)}">`);
    xmlLines.push("        <attvalues>");
    xmlLines.push(`          <attvalue for="0" value="${escapeXml(e.type)}"/>`);
    if (e.polarity !== undefined && e.polarity !== null) {
      xmlLines.push(`          <attvalue for="1" value="${e.polarity}"/>`);
    }
    if (e.weight !== undefined && e.weight !== null) {
      xmlLines.push(`          <attvalue for="2" value="${e.weight}"/>`);
    }
    xmlLines.push("        </attvalues>");
    xmlLines.push("      </edge>");
  });

  xmlLines.push("    </edges>");
  xmlLines.push("  </graph>");
  xmlLines.push("</gexf>");

  const blob = new Blob([xmlLines.join("\n")], { type: "application/xml" });
  downloadBlob(blob, `graph-topology-${runId || "active"}-${Date.now()}.gexf`);
}

export async function exportGraphImage(
  graphInstance: any,
  containerEl: HTMLElement | null,
  format: "png" | "svg",
  runId?: string | null
): Promise<void> {
  const filename = `graph-render-${runId || "active"}-${Date.now()}.${format}`;

  // Attempt G6 toDataURL first
  if (graphInstance && typeof graphInstance.toDataURL === "function") {
    try {
      const dataUrl = await graphInstance.toDataURL({
        type: format === "svg" ? "image/svg+xml" : "image/png",
        encoderOptions: 1.0,
      });
      if (dataUrl) {
        downloadDataUrl(dataUrl, filename);
        return;
      }
    } catch {
      // Fall through to DOM fallback
    }
  }

  // Fallback: check DOM elements in container
  if (containerEl) {
    if (format === "svg") {
      const svg = containerEl.querySelector("svg");
      if (svg) {
        const svgData = new XMLSerializer().serializeToString(svg);
        const blob = new Blob([svgData], { type: "image/svg+xml;charset=utf-8" });
        downloadBlob(blob, filename);
        return;
      }
    }

    const canvas = containerEl.querySelector("canvas");
    if (canvas) {
      const dataUrl = canvas.toDataURL("image/png", 1.0);
      downloadDataUrl(dataUrl, filename);
      return;
    }
  }

  throw new Error("Unable to capture graph render from current canvas.");
}

function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function downloadDataUrl(dataUrl: string, filename: string): void {
  const a = document.createElement("a");
  a.href = dataUrl;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}
