import {create} from "zustand";
import type {Overlay, OverlayKind} from "../api/types.ts";

export interface SubgraphMask {
  lensId: string | null;
  theoryId?: string | null; // Filter for dynamically induced theory elements (Phi_spec)
  allowedNodeTypes: string[] | null; // null = all allowed
  allowedEdgeTypes: string[] | null; // null = all allowed
  allowedPolarities: (number | null)[] | null; // null = all allowed
  partitionFilter?: "B" | "A" | null;
  layerFilter?: (1 | 2 | 3)[] | null;
}

export interface CuratedLens {
  id: string;
  name: string;
  category: "theory" | "partition" | "layer" | "general";
  description: string;
  badge?: string;
  mask: SubgraphMask;
}

export interface DynamicTheoryLens {
  theoryId: string;
  name: string;
  category: "theory";
  badge: string;
  description: string;
  elementCount: number;
  parameters: string[];
  clusters: string[];
  avgTenability?: number;
  mask: SubgraphMask;
}

/**
 * Domain-agnostic curated lenses grounded in structuralist metatheory
 * (Sneed, 1971; Stegmüller, 1976; Balzer et al., 1987).
 * Domain-specific theory lenses (Phi_spec) are induced dynamically at runtime.
 */
export const CURATED_LENSES: CuratedLens[] = [
  {
    id: "all",
    name: "Full Graph Snapshot",
    category: "general",
    description: "Complete graph across all ontological layers and element types.",
    mask: {
      lensId: "all",
      theoryId: null,
      allowedNodeTypes: null,
      allowedEdgeTypes: null,
      allowedPolarities: null,
      partitionFilter: null,
      layerFilter: null,
    },
  },
  {
    id: "empirical_base",
    name: "Empirical Base (B)",
    category: "partition",
    badge: "M_pp",
    description:
      "Non-theoretical empirical observations and grounded data statements (partition B).",
    mask: {
      lensId: "empirical_base",
      theoryId: null,
      allowedNodeTypes: ["ObservationUnit", "EmpiricalStatement", "Chunk"],
      allowedEdgeTypes: null,
      allowedPolarities: null,
      partitionFilter: "B",
      layerFilter: null,
    },
  },
  {
    id: "theoretical_core",
    name: "Theoretical Postulates (A)",
    category: "partition",
    badge: "M",
    description:
      "Theoretical hypotheses, latent constructs, and core systemic laws (partition A).",
    mask: {
      lensId: "theoretical_core",
      theoryId: null,
      allowedNodeTypes: ["TheoreticalHypothesis", "CoreExpansion", "Concept"],
      allowedEdgeTypes: null,
      allowedPolarities: null,
      partitionFilter: "A",
      layerFilter: [2, 3],
    },
  },
  {
    id: "argument_web",
    name: "Dialectical Argument Web",
    category: "layer",
    badge: "L3",
    description:
      "TheoryNet argument units (ADUs), inferential support, attack, and undercut relations.",
    mask: {
      lensId: "argument_web",
      theoryId: null,
      allowedNodeTypes: null,
      allowedEdgeTypes: [
        "SUPPORTS_ARG",
        "ATTACKS",
        "UNDERCUTS",
        "SPECIALIZES",
        "CONSTRAINS",
        "REDUCES_TO",
        "ENTAILS",
        "DEDUCES",
        "COHERES_WITH",
        "INHIBITS",
        "SUPPORTS",
      ],
      allowedPolarities: null,
      partitionFilter: null,
      layerFilter: [3],
    },
  },
  {
    id: "knowledge_graph",
    name: "Entity Knowledge Graph",
    category: "layer",
    badge: "L2",
    description: "Extracted named entities, academic concepts, and domain relationships.",
    mask: {
      lensId: "knowledge_graph",
      theoryId: null,
      allowedNodeTypes: null,
      allowedEdgeTypes: null,
      allowedPolarities: null,
      partitionFilter: null,
      layerFilter: [2],
    },
  },
  {
    id: "bridges",
    name: "Intertheoretical Bridges",
    category: "layer",
    badge: "Links",
    description:
      "Constraint and reduction relations bridging different theoretical frameworks.",
    mask: {
      lensId: "bridges",
      theoryId: null,
      allowedNodeTypes: null,
      allowedEdgeTypes: ["CONSTRAINS", "REDUCES_TO", "ENTAILS", "SPECIALIZES"],
      allowedPolarities: null,
      partitionFilter: null,
      layerFilter: [2, 3],
    },
  },
];

/**
 * Dynamically extract active Theory-Elements (Phi_spec) from graph data.
 * Generic pipeline extraction attaches `theory_id`, `tenability`, and `parameters`.
 */
export function extractTheoriesFromGraph(graph: any | null): DynamicTheoryLens[] {
  if (!graph || !graph.nodes || graph.nodes.length === 0) return [];

  const theoriesMap = new Map<
    string,
    {
      count: number;
      parameters: Set<string>;
      clusters: Set<string>;
      tenabilityScores: number[];
    }
  >();

  for (const node of graph.nodes) {
    const rawTheoryId =
      node.props?.theory_id ||
      node.tenability?.theory_id ||
      (node.props?.tenability as any)?.theory_id;

    if (rawTheoryId && typeof rawTheoryId === "string") {
      const theoryId = rawTheoryId.trim();
      if (!theoriesMap.has(theoryId)) {
        theoriesMap.set(theoryId, {
          count: 0,
          parameters: new Set(),
          clusters: new Set(),
          tenabilityScores: [],
        });
      }
      const entry = theoriesMap.get(theoryId)!;
      entry.count++;

      const clusterId =
        node.props?.theory_cluster ||
        node.tenability?.cluster_id ||
        (node.props?.tenability as any)?.cluster_id;
      if (clusterId) entry.clusters.add(String(clusterId));

      const params = node.parameters || node.props?.parameters;
      if (params && typeof params === "object") {
        Object.keys(params).forEach((k) => entry.parameters.add(k));
      }

      const ts =
        node.tenability?.aggregated_score ??
        node.tenability?.local_score ??
        (node.props?.tenability as any)?.aggregated_score ??
        (node.props?.tenability as any)?.local_score;
      if (typeof ts === "number" && !isNaN(ts)) {
        entry.tenabilityScores.push(ts);
      }
    }
  }

  return Array.from(theoriesMap.entries()).map(([theoryId, data]) => {
    const formattedName = theoryId
      .replace(/^theory_/, "")
      .replace(/[_-]/g, " ")
      .replace(/\b\w/g, (c) => c.toUpperCase());
    const shortBadge = `Φ_${theoryId.replace(/^theory_/, "").slice(0, 6)}`;
    const avgTs =
      data.tenabilityScores.length > 0
        ? data.tenabilityScores.reduce((a, b) => a + b, 0) / data.tenabilityScores.length
        : undefined;

    const paramList = Array.from(data.parameters);
    const clusterCount = data.clusters.size;
    const desc =
      paramList.length > 0
        ? `Evaluated across ${clusterCount || 1} intended application cluster${clusterCount === 1 ? "" : "s"}. Parameters: ${paramList.slice(0, 3).join(", ")}${paramList.length > 3 ? "..." : ""}.`
        : `Dynamically induced Theory-Element projected over ${data.count} graph node${data.count === 1 ? "" : "s"}.`;

    return {
      theoryId,
      name: `Theory: ${formattedName}`,
      category: "theory",
      badge: shortBadge,
      description: desc,
      elementCount: data.count,
      parameters: paramList,
      clusters: Array.from(data.clusters),
      avgTenability: avgTs,
      mask: {
        lensId: `theory_${theoryId}`,
        theoryId,
        allowedNodeTypes: null,
        allowedEdgeTypes: null,
        allowedPolarities: null,
        partitionFilter: null,
        layerFilter: null,
      },
    };
  });
}

const PRESETS_STORAGE_KEY = "glp-studio-custom-masks";

const loadStoredPresets = (): Record<string, SubgraphMask> => {
  if (typeof window === "undefined") return {};
  try {
    const raw = localStorage.getItem(PRESETS_STORAGE_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
};

interface ViewOverlayState {
  // 1. Subgraph Mask (What is visible)
  activeMask: SubgraphMask;
  customPresets: Record<string, SubgraphMask>;
  setActiveLens: (lensId: string, customMask?: SubgraphMask) => void;
  setCustomMask: (mask: Partial<SubgraphMask>) => void;
  resetMask: () => void;
  saveCustomPreset: (name: string, mask: SubgraphMask) => void;
  deleteCustomPreset: (name: string) => void;

  // 2. Overlay (How visible elements are decorated)
  activeOverlay: Overlay | null;
  activeOverlayKind: OverlayKind | "none";
  setActiveOverlay: (overlay: Overlay | null) => void;
  clearOverlay: () => void;

  // 3. UI Drawer state (Floating canvas overlay matching MetricsDrawer)
  isDrawerOpen: boolean;
  isPanelOpen: boolean; // Alias for backward compatibility
  isPinned: boolean;
  activeTab: "previews" | "custom" | "overlays";
  openDrawer: (tab?: "previews" | "custom" | "overlays") => void;
  closeDrawer: () => void;
  toggleDrawer: () => void;
  setPanelOpen: (open: boolean) => void;
  setPinned: (pinned: boolean) => void;
  setActiveTab: (tab: "previews" | "custom" | "overlays") => void;
}

export const useViewOverlayStore = create<ViewOverlayState>((set, get) => ({
  activeMask: CURATED_LENSES[0].mask,
  customPresets: loadStoredPresets(),
  activeOverlay: null,
  activeOverlayKind: "none",
  isDrawerOpen: false,
  isPanelOpen: false,
  isPinned: false,
  activeTab: "previews",

  openDrawer: (tab) => {
    set({
      isDrawerOpen: true,
      isPanelOpen: true,
      ...(tab ? { activeTab: tab } : {}),
    });
  },

  closeDrawer: () => {
    set({ isDrawerOpen: false, isPanelOpen: false });
  },

  toggleDrawer: () => {
    const next = !get().isDrawerOpen;
    set({ isDrawerOpen: next, isPanelOpen: next });
  },

  setActiveLens: (lensId, customMask) => {
    if (customMask) {
      set({ activeMask: customMask });
      return;
    }
    const match = CURATED_LENSES.find((l) => l.id === lensId);
    if (match) {
      set({ activeMask: match.mask });
    } else if (get().customPresets[lensId]) {
      set({ activeMask: get().customPresets[lensId] });
    } else if (lensId.startsWith("theory_")) {
      const theoryId = lensId.replace(/^theory_/, "");
      set({
        activeMask: {
          lensId,
          theoryId,
          allowedNodeTypes: null,
          allowedEdgeTypes: null,
          allowedPolarities: null,
          partitionFilter: null,
          layerFilter: null,
        },
      });
    } else {
      set({ activeMask: { ...CURATED_LENSES[0].mask, lensId } });
    }
  },

  setCustomMask: (partial) => {
    set((state) => ({
      activeMask: {
        ...state.activeMask,
        ...partial,
        lensId: "custom",
      },
    }));
  },

  resetMask: () => {
    set({ activeMask: CURATED_LENSES[0].mask });
  },

  saveCustomPreset: (name, mask) => {
    const updated = { ...get().customPresets, [name]: { ...mask, lensId: name } };
    try {
      localStorage.setItem(PRESETS_STORAGE_KEY, JSON.stringify(updated));
    } catch {}
    set({ customPresets: updated });
  },

  deleteCustomPreset: (name) => {
    const updated = { ...get().customPresets };
    delete updated[name];
    try {
      localStorage.setItem(PRESETS_STORAGE_KEY, JSON.stringify(updated));
    } catch {}
    set({ customPresets: updated });
  },

  setActiveOverlay: (overlay) => {
    set({
      activeOverlay: overlay,
      activeOverlayKind: overlay?.kind || "none",
    });
  },

  clearOverlay: () => {
    set({ activeOverlay: null, activeOverlayKind: "none" });
  },

  setPanelOpen: (open) => set({ isPanelOpen: open, isDrawerOpen: open }),
  setPinned: (pinned) => set({ isPinned: pinned }),
  setActiveTab: (tab) => set({ activeTab: tab }),
}));
