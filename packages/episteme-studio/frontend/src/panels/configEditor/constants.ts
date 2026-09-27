import type { InvalidationPreview } from "../../api/types.ts";
import type { ThinkingLevelPreset } from "./types.ts";

export const BASELINE_PREVIEW: InvalidationPreview = {
  invalidated_phases: [],
  reused_phases: [1, 2, 3, 4, 5, 6, 7, 8],
  changed_fingerprints: {},
  reason: "Baseline configuration (all upstream phases cached)",
  estimated_artifact_loss: 0,
};

export const DEFAULT_L2_NODE_DEFINITIONS: Record<string, string> = {
  Concept: "Abstract idea, category, mental construct, or theoretical term (e.g. 'Justified True Belief', 'Working Memory').",
  Person: "Individual thinker, scientist, philosopher, author, or historical figure (e.g. 'Edmund Gettier', 'Immanuel Kant').",
  Work: "Publication, paper, treatise, book, or essay (e.g. 'Is Justified True Belief Knowledge?', 'Critique of Pure Reason').",
  Theory: "Cohesive conceptual framework, formal model, doctrine, or system (e.g. 'Classical Theory of Knowledge', 'Behaviorism').",
  Institution: "Academic school, university, research group, movement, or organization (e.g. 'Vienna Circle', 'Harvard University').",
};

export const DEFAULT_L2_RELATION_DEFINITIONS: Record<string, string> = {
  RELATED_TO: "General associative semantic connection between entities.",
  INSTANCE_OF: "Entity is a concrete realization or token of a conceptual type.",
  PART_OF: "Mereological containment or constituent sub-component.",
  SUBCLASS_OF: "Taxonomic specialization or categorical subsumption.",
  SUPPORTS: "Entity evidence or premise positively contributes to another.",
  REFUTES: "Entity evidence or counterargument denies or falsifies another.",
  IMPLIES: "Logical, causal, or inferential entailment from source to target.",
  CONTRADICTS: "Direct propositional inconsistency or mutual exclusivity.",
};

export const DEFAULT_L3_COMPONENT_DEFINITIONS: Record<string, string> = {
  ObservationUnit: "Singular or localized statements containing exclusively observational terms. Act as raw data nodes.",
  EmpiricalStatement: "Statements containing only logical and empirical concepts.",
  TheoreticalHypothesis: "Statements containing theoretical concepts or whose quantifiers have theoretical scope. These represent core laws or abstract hypotheses.",
  CoreExpansion: "Special auxiliary laws and constraints that form a shifting superstructure around the stable theory core.",
};

export const DEFAULT_L3_ARGUMENT_RELATION_DEFINITIONS: Record<string, string> = {
  ATTACKS: "Argument component attacks another (critical relationship).",
  SUPPORTS_ARG: "Argument component provides support for another.",
  UNDERCUTS: "Argument component undermines the inference of another.",
  SPECIALIZES: "Directed vertical edges forming a hierarchy where a specialized node inherits and restricts properties from its parent.",
  CONSTRAINS: "Lateral/horizontal edges crossing overlapping applications to ensure intrinsic properties remain constant.",
  REDUCES_TO: "Intertheoretical links connecting entirely separate theories, including strict reduction from older to newer theories.",
  ENTAILS: "Intertheoretical links connecting entirely separate theories, including strict reduction from older to newer theories.",
  DEDUCES: "Logical entailments between nodes such as Explanation Patterns (Erklärungsschema) and Falsification Patterns (Falsifikationsschema).",
  COHERES_WITH: "Positive (excitatory) connections between hypotheses that explain evidence, or co-hypotheses that jointly explain a fact.",
  INHIBITS: "Negative (inhibitory) weights representing incoherence between logically contradictory or competing hypotheses.",
};

export const DEFAULT_COMPONENT_PARTITIONS: Record<string, string> = {
  ObservationUnit: "B",
  EmpiricalStatement: "B",
  TheoreticalHypothesis: "A",
  CoreExpansion: "A",
};

export const DEFAULT_RELATION_POLARITIES: Record<string, number> = {
  RELATED_TO: 0,
  INSTANCE_OF: 0,
  PART_OF: 0,
  SUBCLASS_OF: 0,
  SUPPORTS: 1,
  REFUTES: -1,
  IMPLIES: 1,
  CONTRADICTS: -1,
  ATTACKS: -1,
  SUPPORTS_ARG: 1,
  UNDERCUTS: -1,
  SPECIALIZES: 0,
  CONSTRAINS: 0,
  REDUCES_TO: 1,
  ENTAILS: 1,
  DEDUCES: 1,
  COHERES_WITH: 1,
  INHIBITS: -1,
};

export const THINKING_LEVEL_PRESETS: ThinkingLevelPreset[] = [
  { id: "off", label: "Off", description: "Standard generation without thinking tokens" },
  { id: "low", label: "Low", description: "Light reasoning for fast extraction and classification" },
  { id: "medium", label: "Medium", description: "Balanced depth for inter-document relation synthesis" },
  { id: "high", label: "High", description: "Maximum reasoning budget for complex philosophical analysis" },
  { id: "custom", label: "Custom...", description: "Specify a custom token budget or reasoning effort level" },
];
