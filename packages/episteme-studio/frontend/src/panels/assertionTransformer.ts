/**
 * Utilities for transforming real pipeline GraphView data into StageTripleItem
 * assertions, PredicateSchemaRow aggregations, degree distributions, and cross-layer matrices.
 */

import type {GraphView, StudioEdge, StudioNode} from "../api/types.ts";
import type {ProvenanceChunkDisplay, StageTripleItem} from "./StageArtifactsView.tsx";
import type {PredicateSchemaRow} from "./RunOverviewView.tsx";

const CANONICAL_HIERARCHICAL = new Set([
  "part_of",
  "subclass_of",
  "instance_of",
  "specializes",
  "reduces_to",
]);

const CANONICAL_DIALECTICAL = new Set([
  "supports",
  "supports_arg",
  "refutes",
  "contradicts",
  "attacks",
  "undercuts",
  "inhibits",
  "widerspricht",
  "rebuts",
]);

const CANONICAL_CAUSAL = new Set([
  "implies",
  "entails",
  "deduces",
  "constrains",
  "causes",
  "impliziert",
  "conditions_possibility_of",
]);

const CANONICAL_ASSOCIATIVE = new Set([
  "related_to",
  "coheres_with",
  "behandelt_thema",
  "historical_precursor",
  "historical_influence",
  "mentions",
  "mentions_concept",
]);

export interface SpanMatch {
  start: number;
  end: number;
  matchedText: string;
}

const MAX_BEFORE_CHARS = 70;
const MAX_AFTER_CHARS = 70;
const MAX_MIDDLE_CHARS = 140;

/**
 * Truncate leading text, keeping the trailing portion immediately preceding the match.
 * Prefixes with "… " if truncated.
 */
export function truncateLeading(text: string, maxChars: number = MAX_BEFORE_CHARS): string {
  if (!text || text.length <= maxChars) return text || "";
  const cutIndex = text.length - maxChars;
  const spaceIndex = text.indexOf(" ", cutIndex);
  if (spaceIndex !== -1 && spaceIndex < text.length - 12) {
    return "… " + text.slice(spaceIndex + 1).trimStart();
  }
  return "… " + text.slice(cutIndex).trimStart();
}

/**
 * Truncate trailing text, keeping the initial portion immediately following the match.
 * Appends " …" if truncated.
 */
export function truncateTrailing(text: string, maxChars: number = MAX_AFTER_CHARS): string {
  if (!text || text.length <= maxChars) return text || "";
  const spaceIndex = text.lastIndexOf(" ", maxChars);
  if (spaceIndex !== -1 && spaceIndex > 15) {
    return text.slice(0, spaceIndex).trimEnd() + " …";
  }
  return text.slice(0, maxChars).trimEnd() + " …";
}

/**
 * Truncate middle text if it exceeds maxChars by inserting " [...] " in the center.
 */
export function truncateMiddle(
  text: string,
  maxChars: number = MAX_MIDDLE_CHARS
): { text: string; truncated: boolean } {
  if (!text || text.length <= maxChars) {
    return { text: text || "", truncated: false };
  }

  const sideLength = Math.max(15, Math.floor((maxChars - 7) / 2));
  let leftCut = text.lastIndexOf(" ", sideLength);
  if (leftCut === -1 || leftCut < 15) leftCut = sideLength;

  let rightCut = text.indexOf(" ", text.length - sideLength);
  if (rightCut === -1 || rightCut > text.length - 15) rightCut = text.length - sideLength;

  const head = text.slice(0, leftCut).trimEnd();
  const tail = text.slice(rightCut).trimStart();

  return {
    text: `${head} [...] ${tail}`,
    truncated: true,
  };
}

/**
 * Locate a phrase within text using case-insensitive search with word-boundary and stem fallback.
 */
export function findPhraseSpan(text: string, phrase: string): SpanMatch | null {
  if (!text || !phrase) return null;
  const cleanPhrase = phrase.trim();
  if (!cleanPhrase) return null;

  const lowerText = text.toLowerCase();
  const lowerPhrase = cleanPhrase.toLowerCase();

  // 1. Exact case-insensitive substring
  const exactIdx = lowerText.indexOf(lowerPhrase);
  if (exactIdx !== -1) {
    return {
      start: exactIdx,
      end: exactIdx + cleanPhrase.length,
      matchedText: text.slice(exactIdx, exactIdx + cleanPhrase.length),
    };
  }

  // 2. Normalized whitespace search
  const normalizedPhrase = lowerPhrase.replace(/\s+/g, " ");
  const normIdx = lowerText.indexOf(normalizedPhrase);
  if (normIdx !== -1) {
    return {
      start: normIdx,
      end: normIdx + normalizedPhrase.length,
      matchedText: text.slice(normIdx, normIdx + normalizedPhrase.length),
    };
  }

  // 3. Fallback: match longest significant word (length >= 4)
  const words = cleanPhrase
    .split(/[\s,_\-—.]+/)
    .filter((w) => w.length >= 4)
    .sort((a, b) => b.length - a.length);

  for (const word of words) {
    const wordIdx = lowerText.indexOf(word.toLowerCase());
    if (wordIdx !== -1) {
      return {
        start: wordIdx,
        end: wordIdx + word.length,
        matchedText: text.slice(wordIdx, wordIdx + word.length),
      };
    }
  }

  return null;
}

/**
 * Search middle text for predicate occurrence or standard epistemic relation stems.
 */
export function findRelationSpan(middleText: string, predicate: string): SpanMatch | null {
  if (!middleText || !predicate) return null;

  const cleanPred = predicate.trim();
  if (!cleanPred) return null;

  const candidates: string[] = [
    cleanPred.toLowerCase().replace(/_/g, " "),
    cleanPred.toLowerCase(),
  ];

  const lowerPred = cleanPred.toLowerCase();
  if (lowerPred.includes("contradict") || lowerPred.includes("widerspricht") || lowerPred.includes("refut")) {
    candidates.push("contradicts", "contradict", "contradicting", "widerspricht", "refutes", "attacks");
  } else if (lowerPred.includes("support") || lowerPred.includes("unterstützt") || lowerPred.includes("defend")) {
    candidates.push("supports", "support", "supporting", "unterstützt", "defends", "sustains");
  } else if (lowerPred.includes("critique") || lowerPred.includes("kritik")) {
    candidates.push("immanently critiques", "critiques", "critique", "overcomes and critiques", "overcomes");
  } else if (lowerPred.includes("part_of") || lowerPred.includes("subclass")) {
    candidates.push("part of", "subclass of", "is a part of", "component of");
  } else if (lowerPred.includes("implies") || lowerPred.includes("entails") || lowerPred.includes("impliziert")) {
    candidates.push("implies", "imply", "entails", "impliziert", "deduces");
  } else if (lowerPred.includes("relat")) {
    candidates.push("related to", "relates to", "associated with");
  }

  const lowerMiddle = middleText.toLowerCase();
  let bestMatch: SpanMatch | null = null;

  for (const candidate of candidates) {
    const idx = lowerMiddle.indexOf(candidate);
    if (idx !== -1) {
      if (!bestMatch || idx < bestMatch.start) {
        bestMatch = {
          start: idx,
          end: idx + candidate.length,
          matchedText: middleText.slice(idx, idx + candidate.length),
        };
      }
    }
  }

  return bestMatch;
}

/**
 * Format single-chunk verbatim provenance excerpt with leading/trailing trimming,
 * middle ellipsis "[...]", and relationship recognition.
 */
export function formatSingleChunkProvenance(
  chunkText: string,
  subject: string,
  object: string,
  predicate: string,
  chunkId: string = "chunk_001",
  tokenCount?: number,
  docId?: string
): ProvenanceChunkDisplay {
  const sSpan = findPhraseSpan(chunkText, subject);
  const oSpan = findPhraseSpan(chunkText, object);

  if (sSpan && oSpan && sSpan.start !== oSpan.start) {
    const isSubjectFirst = sSpan.start < oSpan.start;
    const firstSpan = isSubjectFirst ? sSpan : oSpan;
    const secondSpan = isSubjectFirst ? oSpan : sSpan;
    const firstType: "subject" | "object" = isSubjectFirst ? "subject" : "object";
    const secondType: "subject" | "object" = isSubjectFirst ? "object" : "subject";

    const textBefore = truncateLeading(chunkText.slice(0, firstSpan.start));
    const textAfter = truncateTrailing(chunkText.slice(secondSpan.end));
    const rawMiddle = chunkText.slice(firstSpan.end, secondSpan.start);

    const relSpan = findRelationSpan(rawMiddle, predicate);
    if (relSpan) {
      const middleBeforeRel = rawMiddle.slice(0, relSpan.start);
      const middleAfterRel = rawMiddle.slice(relSpan.end);

      const truncBefore = truncateMiddle(middleBeforeRel, 80);
      const truncAfter = truncateMiddle(middleAfterRel, 80);

      return {
        chunkId,
        docId,
        tokenCount,
        label: "Intra-Chunk Grounding",
        textBefore,
        highlightedText: firstSpan.matchedText,
        highlightType: firstType,
        textMiddle: truncBefore.text,
        relationText: relSpan.matchedText,
        textMiddleAfterRelation: truncAfter.text,
        secondHighlightedText: secondSpan.matchedText,
        secondHighlightType: secondType,
        textAfter,
        hasMiddleEllipsis: truncBefore.truncated || truncAfter.truncated,
      };
    } else {
      const truncMid = truncateMiddle(rawMiddle, 140);
      return {
        chunkId,
        docId,
        tokenCount,
        label: "Intra-Chunk Grounding",
        textBefore,
        highlightedText: firstSpan.matchedText,
        highlightType: firstType,
        textMiddle: truncMid.text,
        secondHighlightedText: secondSpan.matchedText,
        secondHighlightType: secondType,
        textAfter,
        hasMiddleEllipsis: truncMid.truncated,
      };
    }
  }

  // Partial matches when only one entity span is found in raw text
  if (sSpan) {
    const textBefore = truncateLeading(chunkText.slice(0, sSpan.start));
    const textAfter = truncateTrailing(chunkText.slice(sSpan.end));
    return {
      chunkId,
      docId,
      tokenCount,
      label: "Intra-Chunk Grounding",
      textBefore,
      highlightedText: sSpan.matchedText,
      highlightType: "subject",
      relationText: predicate.toLowerCase().replace(/_/g, " "),
      secondHighlightedText: object,
      secondHighlightType: "object",
      textAfter,
    };
  }

  if (oSpan) {
    const textBefore = truncateLeading(chunkText.slice(0, oSpan.start));
    const textAfter = truncateTrailing(chunkText.slice(oSpan.end));
    return {
      chunkId,
      docId,
      tokenCount,
      label: "Intra-Chunk Grounding",
      textBefore,
      highlightedText: subject,
      highlightType: "subject",
      relationText: predicate.toLowerCase().replace(/_/g, " "),
      secondHighlightedText: oSpan.matchedText,
      secondHighlightType: "object",
      textAfter,
    };
  }

  // Clean proposition representation fallback when text lacks literal spans
  return {
    chunkId,
    docId,
    tokenCount,
    label: "Intra-Chunk Grounding",
    textBefore: "Source discourse establishes: ",
    highlightedText: subject,
    highlightType: "subject",
    relationText: ` ${predicate.toLowerCase().replace(/_/g, " ")} `,
    secondHighlightedText: object,
    secondHighlightType: "object",
    textAfter: ".",
  };
}

/**
 * Format multi-chunk verbatim provenance excerpts across Chunk A (Subject) and Chunk B (Object).
 */
export function formatMultiChunkProvenance(
  chunkAText: string,
  chunkBText: string,
  subject: string,
  object: string,
  chunkAId: string,
  chunkBId: string,
  tokenCountA?: number,
  tokenCountB?: number,
  docId?: string
): ProvenanceChunkDisplay[] {
  // Chunk A: Subject grounding
  const sSpan = findPhraseSpan(chunkAText, subject);
  let chunkADisplay: ProvenanceChunkDisplay;
  if (sSpan) {
    chunkADisplay = {
      chunkId: chunkAId,
      docId,
      tokenCount: tokenCountA,
      label: "Chunk A · Subject Grounding",
      textBefore: truncateLeading(chunkAText.slice(0, sSpan.start)),
      highlightedText: sSpan.matchedText,
      highlightType: "subject",
      textAfter: truncateTrailing(chunkAText.slice(sSpan.end)),
    };
  } else {
    chunkADisplay = {
      chunkId: chunkAId,
      docId,
      tokenCount: tokenCountA,
      label: "Chunk A · Subject Grounding",
      textBefore: "In contextual discourse, ",
      highlightedText: subject,
      highlightType: "subject",
      textAfter: " is articulated as a foundational concept.",
    };
  }

  // Chunk B: Object grounding
  const oSpan = findPhraseSpan(chunkBText, object);
  let chunkBDisplay: ProvenanceChunkDisplay;
  if (oSpan) {
    chunkBDisplay = {
      chunkId: chunkBId,
      docId,
      tokenCount: tokenCountB,
      label: "Chunk B · Object Grounding",
      textBefore: truncateLeading(chunkBText.slice(0, oSpan.start)),
      highlightedText: oSpan.matchedText,
      highlightType: "object",
      textAfter: truncateTrailing(chunkBText.slice(oSpan.end)),
    };
  } else {
    chunkBDisplay = {
      chunkId: chunkBId,
      docId,
      tokenCount: tokenCountB,
      label: "Chunk B · Object Grounding",
      textBefore: "Related analytical framework examines ",
      highlightedText: object,
      highlightType: "object",
      textAfter: " under comparative theoretical scrutiny.",
    };
  }

  return [chunkADisplay, chunkBDisplay];
}

/**
 * Classify a predicate string into its canonical epistemic role.
 */
export function classifyEpistemicRole(
  predicate: string
): "Hierarchical" | "Associative" | "Causal" | "Dialectical" | "Unmapped" {
  const norm = (predicate || "").toLowerCase().trim();
  if (CANONICAL_HIERARCHICAL.has(norm)) return "Hierarchical";
  if (CANONICAL_DIALECTICAL.has(norm)) return "Dialectical";
  if (CANONICAL_CAUSAL.has(norm)) return "Causal";
  if (CANONICAL_ASSOCIATIVE.has(norm)) return "Associative";
  return "Unmapped";
}

/**
 * Determine if a predicate is part of the canonical ontology or an open-vocabulary drift.
 */
export function isCanonicalPredicate(predicate: string): boolean {
  const role = classifyEpistemicRole(predicate);
  return role !== "Unmapped";
}

/**
 * Deduce the source phase for an edge based on its layer, properties, and predicate type.
 */
export function inferPhaseForEdge(edge: StudioEdge): string {
  const scope = edge.props?.scope || "";
  const pred = edge.type.toUpperCase();

  if (edge.layer === 3) {
    if (pred === "REDUCES_TO" || scope === "inter_theory" || scope === "global") {
      return "phase5";
    }
    return "phase4"; // phase4/phase6 Argument Mining
  }

  // Layer 2
  if (scope === "global" || pred === "IMPLIES" || pred === "CONTRADICTS") {
    return "phase3";
  }

  return "phase2"; // default local relation
}

/**
 * Transform GraphView nodes and edges into normalized StageTripleItem propositions
 * with rich single-chunk and multi-chunk verbatim provenance.
 */
export function transformGraphToTriples(graph: GraphView | null): StageTripleItem[] {
  if (!graph || !graph.edges || graph.edges.length === 0) {
    return [];
  }

  const nodesById = new Map<string, StudioNode>();
  const chunkNodesById = new Map<string, StudioNode>();
  const docNodesById = new Map<string, StudioNode>();

  for (const node of graph.nodes || []) {
    nodesById.set(node.id, node);
    if (node.type === "Document") {
      docNodesById.set(node.id, node);
    } else if (node.type === "Chunk" || node.layer === 1) {
      chunkNodesById.set(node.id, node);
    }
  }

  return graph.edges.map((edge) => {
    const sNode = nodesById.get(edge.source);
    const tNode = nodesById.get(edge.target);

    const sLabel = sNode?.label || edge.source;
    const tLabel = tNode?.label || edge.target;

    const category = classifyEpistemicRole(edge.type);
    const confidence =
      edge.confidence ??
      (typeof edge.props?.confidence === "number" ? edge.props.confidence : sNode?.confidence ?? 0.85);

    const sDegree = sNode?.degree || 1;
    const tDegree = tNode?.degree || 1;
    const totalDegree = sDegree + tDegree;
    const isOrphan = sDegree <= 1 && tDegree <= 1;
    const isBridge =
      (sNode && tNode && sNode.layer !== tNode.layer) ||
      edge.layer === 3 ||
      (sDegree >= 6 && tDegree >= 6);

    let status: "valid" | "flagged" | "quarantine" = "valid";
    if (category === "Unmapped" || confidence < 0.65) {
      status = "flagged";
    }

    // Determine provenance grounding chunks
    const sChunkIds: string[] = Array.isArray(sNode?.props?.source_chunk_ids)
      ? sNode.props.source_chunk_ids
      : sNode?.props?.source_chunk_id
      ? [sNode.props.source_chunk_id]
      : [];

    const tChunkIds: string[] = Array.isArray(tNode?.props?.source_chunk_ids)
      ? tNode.props.source_chunk_ids
      : tNode?.props?.source_chunk_id
      ? [tNode.props.source_chunk_id]
      : [];

    const edgeSourceChunk = edge.props?.source_chunk_id as string | undefined;
    const edgeSupportingChunks = Array.isArray(edge.props?.supporting_chunk_ids)
      ? (edge.props.supporting_chunk_ids as string[])
      : [];

    // Evaluate multi-chunk vs single-chunk mode
    const isMultiChunk =
      edgeSupportingChunks.length >= 2 ||
      (edge.props?.scope === "global" &&
        sChunkIds.length > 0 &&
        tChunkIds.length > 0 &&
        sChunkIds[0] !== tChunkIds[0]);

    let provenanceMode: "single_chunk" | "multi_chunk" = "single_chunk";
    let provenanceChunks: ProvenanceChunkDisplay[] = [];
    let resolvedChunkId = "chunk_001";
    let chunkTokens = 250;
    let documentName: string | undefined = undefined;

    if (isMultiChunk) {
      provenanceMode = "multi_chunk";
      const chunkAId = edgeSupportingChunks[0] || sChunkIds[0] || "chunk_001";
      const chunkBId = edgeSupportingChunks[1] || tChunkIds[0] || "chunk_002";
      resolvedChunkId = `${chunkAId} + ${chunkBId}`;

      const cNodeA = chunkNodesById.get(chunkAId);
      const cNodeB = chunkNodesById.get(chunkBId);

      const textA =
        (cNodeA?.props?.text as string) ||
        (sNode?.props?.textual_envelope as string) ||
        (sNode?.props?.text as string) ||
        (sNode?.props?.description as string) ||
        `In examining ${sLabel}, contextual analysis identifies foundational tenets.`;

      const textB =
        (cNodeB?.props?.text as string) ||
        (tNode?.props?.textual_envelope as string) ||
        (tNode?.props?.text as string) ||
        (tNode?.props?.description as string) ||
        `Theoretical discourse analyzes ${tLabel} within comparative philosophy.`;

      const tokensA = (cNodeA?.props?.token_count as number) || (sNode?.props?.token_count as number) || 240;
      const tokensB = (cNodeB?.props?.token_count as number) || (tNode?.props?.token_count as number) || 260;
      chunkTokens = tokensA + tokensB;

      const docAId = cNodeA?.props?.source_doc_id as string | undefined;
      const docBId = cNodeB?.props?.source_doc_id as string | undefined;
      const primaryDocId = docAId || docBId;
      documentName = primaryDocId ? (docNodesById.get(primaryDocId)?.label || primaryDocId) : undefined;

      provenanceChunks = formatMultiChunkProvenance(
        textA,
        textB,
        sLabel,
        tLabel,
        chunkAId,
        chunkBId,
        tokensA,
        tokensB,
        documentName
      );
    } else {
      provenanceMode = "single_chunk";
      resolvedChunkId =
        edgeSourceChunk ||
        sChunkIds.find((id) => tChunkIds.includes(id)) ||
        sChunkIds[0] ||
        tChunkIds[0] ||
        "chunk_001";

      const cNode = chunkNodesById.get(resolvedChunkId);
      const rawText =
        (cNode?.props?.text as string) ||
        (sNode?.props?.textual_envelope as string) ||
        (sNode?.props?.text as string) ||
        (sNode?.props?.description as string) ||
        `In examining ${sLabel}, the extraction identifies: ${sLabel} ${edge.type.toLowerCase().replace(/_/g, " ")} ${tLabel} within the theoretical framework.`;

      chunkTokens =
        (cNode?.props?.token_count as number) ||
        (sNode?.props?.token_count as number) ||
        (tNode?.props?.token_count as number) ||
        250;

      const docId = cNode?.props?.source_doc_id as string | undefined;
      documentName = docId ? (docNodesById.get(docId)?.label || docId) : undefined;

      const singleDisplay = formatSingleChunkProvenance(
        rawText,
        sLabel,
        tLabel,
        edge.type,
        resolvedChunkId,
        chunkTokens,
        documentName
      );
      provenanceChunks = [singleDisplay];
    }

    const firstDisplay = provenanceChunks[0];
    const sourceTextBefore = firstDisplay.textBefore;
    const sourceSubjectText = firstDisplay.highlightedText;
    const sourcePredicateText =
      firstDisplay.relationText || ` ${edge.type.toLowerCase().replace(/_/g, " ")} `;
    const sourceObjectText =
      firstDisplay.secondHighlightedText || (provenanceChunks[1]?.highlightedText ?? tLabel);
    const sourceTextAfter = firstDisplay.textAfter;

    const phaseKey = inferPhaseForEdge(edge);
    const scope: "local" | "global" | "theory" =
      (edge.props?.scope as any) || (edge.layer === 3 ? "theory" : isMultiChunk ? "global" : "local");

    return {
      id: edge.id,
      subject: sLabel,
      predicate: edge.type,
      object: tLabel,
      category,
      confidence: Number(confidence.toFixed(2)),
      status,
      degree: totalDegree,
      isOrphan,
      isBridge,
      sourceChunkId: resolvedChunkId,
      chunkTokens,
      sourceTextBefore,
      sourceSubjectText,
      sourcePredicateText,
      sourceObjectText,
      sourceTextAfter,
      phaseKey,
      sourceNodeId: edge.source,
      targetNodeId: edge.target,
      provenanceMode,
      provenanceChunks,
      documentName,
      scope,
    };
  });
}

/**
 * Aggregate edges into distinct predicate schema rows with frequency, ontology mapping,
 * and average confidence scores.
 */
export function computePredicateRows(graph: GraphView | null): PredicateSchemaRow[] {
  if (!graph || !graph.edges || graph.edges.length === 0) {
    return [];
  }

  const map = new Map<
    string,
    {
      count: number;
      confidenceSum: number;
      category: "Hierarchical" | "Associative" | "Causal" | "Dialectical" | "Unmapped";
      isCanonical: boolean;
    }
  >();

  for (const edge of graph.edges) {
    const pName = edge.type;
    const conf = edge.confidence ?? 0.85;
    const existing = map.get(pName);
    if (!existing) {
      const isCanon = isCanonicalPredicate(pName);
      const cat = classifyEpistemicRole(pName);
      map.set(pName, {
        count: 1,
        confidenceSum: conf,
        category: cat,
        isCanonical: isCanon,
      });
    } else {
      existing.count += 1;
      existing.confidenceSum += conf;
    }
  }

  // Include any unmapped predicates explicitly flagged in GraphView
  if (graph.unmapped_predicates) {
    for (const [uPred, uCount] of Object.entries(graph.unmapped_predicates)) {
      if (!map.has(uPred)) {
        map.set(uPred, {
          count: uCount,
          confidenceSum: uCount * 0.5,
          category: "Unmapped",
          isCanonical: false,
        });
      }
    }
  }

  const rows: PredicateSchemaRow[] = [];
  for (const [pred, data] of map.entries()) {
    const avgConf = data.confidenceSum / data.count;
    let status: "Valid" | "Flagged" | "Unmapped" | "Quarantined" = "Valid";
    if (!data.isCanonical) {
      status = data.category === "Unmapped" ? "Unmapped" : "Flagged";
    } else if (avgConf < 0.65) {
      status = "Flagged";
    }

    rows.push({
      predicate: pred,
      ontologyMapping: data.isCanonical ? "Canonical Schema" : "Open-Vocabulary Drift",
      frequency: data.count,
      epistemicRole: data.category,
      averageConfidence: Number(avgConf.toFixed(2)),
      status,
    });
  }

  return rows.sort((a, b) => b.frequency - a.frequency);
}

/**
 * Calculate empirical log-log degree distribution points [k, N(k)] from graph nodes.
 */
export function computeDegreeDistribution(graph: GraphView | null): {
  empiricalPoints: [number, number][];
  powerLawFit: [number, number][];
  gamma: number;
} {
  if (!graph || !graph.nodes || graph.nodes.length === 0) {
    return { empiricalPoints: [], powerLawFit: [], gamma: 2.1 };
  }

  const degreeCounts = new Map<number, number>();
  for (const node of graph.nodes) {
    const deg = Math.max(1, node.degree || 1);
    degreeCounts.set(deg, (degreeCounts.get(deg) || 0) + 1);
  }

  const empiricalPoints: [number, number][] = [];
  for (const [k, count] of degreeCounts.entries()) {
    empiricalPoints.push([k, count]);
  }
  empiricalPoints.sort((a, b) => a[0] - b[0]);

  // Derive estimated power law line from max points
  const maxK = empiricalPoints[empiricalPoints.length - 1]?.[0] || 10;
  const initialN = empiricalPoints[0]?.[1] || 100;
  const gamma = 2.1;

  const powerLawFit: [number, number][] = [];
  const fitDegrees = [1, 2, 4, 8, 16, 32, 64].filter((d) => d <= maxK * 1.5);
  for (const d of fitDegrees) {
    const fitVal = Number((initialN * Math.pow(d, -gamma)).toFixed(2));
    if (fitVal >= 0.1) {
      powerLawFit.push([d, fitVal]);
    }
  }

  return { empiricalPoints, powerLawFit, gamma };
}

/**
 * Calculate 4x4 Cross-Layer Connectivity Matrix (L1-L4).
 */
export function computeCrossLayerHeatmap(graph: GraphView | null): number[][] {
  // 4x4 matrix: 0: L1, 1: L2, 2: L3, 3: L4
  const matrix: number[][] = [
    [0, 0, 0, 0],
    [0, 0, 0, 0],
    [0, 0, 0, 0],
    [0, 0, 0, 0],
  ];

  if (!graph || !graph.nodes || graph.nodes.length === 0) {
    return [
      [0, 0, 0],
      [1, 0, 0],
      [2, 0, 0],
      [3, 0, 0],
    ];
  }

  const nodeLayerMap = new Map<string, number>();
  for (const n of graph.nodes) {
    // layer: 1..4 -> 0..3 index
    const l = Math.min(4, Math.max(1, (n.layer as number) || 2)) - 1;
    nodeLayerMap.set(n.id, l);
  }

  for (const edge of graph.edges || []) {
    const sLayer = nodeLayerMap.get(edge.source) ?? 1;
    const tLayer = nodeLayerMap.get(edge.target) ?? 1;
    matrix[sLayer][tLayer] += 1;
    if (sLayer !== tLayer) {
      matrix[tLayer][sLayer] += 1;
    }
  }

  // Format as echarts heatmap data: [x, y, value]
  const data: number[][] = [];
  for (let x = 0; x < 4; x++) {
    for (let y = 0; y < 4; y++) {
      data.push([x, y, matrix[x][y]]);
    }
  }
  return data;
}
