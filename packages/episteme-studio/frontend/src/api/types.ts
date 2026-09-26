/**
 * Wire contract types for GLP Studio frontend matching CONTRACT.md
 */

export type RunStatus = "planned" | "running" | "completed" | "failed" | "aborted";

export interface PhaseStatus {
  phase_name: string;
  phase_ordinal: number;
  status: RunStatus;
  started_at?: string | null;
  completed_at?: string | null;
  duration_seconds?: number | null;
  reused?: boolean;
  artifact_count: number;
  yield_summary?: string | null;
  artifact_counts_by_kind?: Record<string, number>;
}

export interface GlobalStructuralAnchor {
  toc_structure?: string[] | string;
  document_summary?: string | null;
  global_thesis?: string | null;
}

export interface RunSummary {
  run_id: string;
  status: RunStatus;
  created_at: string;
  completed_at?: string | null;
  duration_seconds?: number | null;
  pipeline_version: string;
  schema_version?: string | null;
  input_sources: string[];
  bib_sources?: string[];
  metadata?: Record<string, string>;
  structural_anchor?: GlobalStructuralAnchor | null;
  primary_input?: string | null;
  models: Record<string, string>;
  artifact_count: number;
  size_bytes: number;
  reused_phase_count?: number;
  total_phase_count?: number;
  tags: string[];
  parent_run_id?: string | null;
}

export interface ProblemDetail {
  type: string;
  title: string;
  status: number;
  detail?: string | null;
  instance?: string | null;
  extra?: Record<string, any>;
}

export interface RunDetail extends RunSummary {
  phase_records: PhaseStatus[];
  artifact_counts_by_kind: Record<string, number>;
  graph_schema: Record<string, any>;
  config_snapshot: Record<string, any>;
  fingerprints: Record<string, any>;
  unresolved_count: number;
  langfuse_url?: string | null;
  failure?: ProblemDetail | null;
}

export interface StudioEvent {
  seq: number;
  run_id: string;
  ts: string;
  kind: string;
  level: "debug" | "info" | "warning" | "error";
  phase?: string | null;
  message?: string | null;
  payload: Record<string, any>;
  dropped_before: number;
}

export interface StudioNode {
  id: string;
  layer: 1 | 2 | 3;
  type: string;
  label: string;
  partition?: "B" | "A" | null;
  degree?: number;
  plausibility?: number | null;
  confidence?: number | null;
  resolved: boolean;
  synthetic: boolean;
  parameters?: Record<string, number> | null;
  tenability?: Record<string, any> | null;
  props: Record<string, any>;
}

export interface StudioEdge {
  id: string;
  source: string;
  target: string;
  target_kind: "node" | "edge";
  type: string;
  layer: 1 | 2 | 3;
  polarity?: number | null;
  weight?: number | null;
  confidence?: number | null;
  tenability?: number | null;
  props: Record<string, any>;
}

export interface TextAnchor {
  source_doc_id?: string | null;
  char_start?: number | null;
  char_end?: number | null;
  verbatim_quote?: string | null;
  bbox?: number[] | null;
  page?: number | null;
  formula_id?: string | null;
  table_id?: string | null;
  figure_id?: string | null;
}

export interface EvidenceSpan {
  start_char?: number | null;
  end_char?: number | null;
  text: string;
  mode: "exact" | "substring" | "whole_chunk" | "visual" | "tabular" | "formula";
  bbox?: number[] | null;
  page?: number | null;
  formula_id?: string | null;
  table_id?: string | null;
  figure_id?: string | null;
}

export interface EvidenceChunk {
  chunk_id: string;
  text: string;
  doc_id?: string | null;
  chapter_id?: string | null;
  spans: EvidenceSpan[];
}

export interface EvidenceTrail {
  node_id: string;
  layer: number;
  chunks: EvidenceChunk[];
  anchors?: TextAnchor[];
}

export interface GraphView {
  nodes: StudioNode[];
  edges: StudioEdge[];
  source: "artifacts" | "neo4j" | "fixture";
  run_id?: string | null;
  graph_version: string;
  schema_version: string;
  truncated: boolean;
  dropped_count: number;
  unmapped_predicates: Record<string, number>;
  unresolved_count: number;
  layer_counts: Record<number, number>;
}

export interface Capabilities {
  artifacts: boolean;
  neo4j: boolean;
  execution: boolean;
  overlays: string[];
}

export interface StartRunPayload {
  profile_id?: string | null;
  patch?: Record<string, any>;
  source_paths?: string[];
  bib_paths?: string[];
  metadata?: Record<string, string>;
  structural_anchor?: GlobalStructuralAnchor | null;
  demo_mode?: boolean;
  parent_run_id?: string | null;
}

export interface CypherRequest {
  query: string;
  params?: Record<string, any>;
  limit?: number | null;
}

export interface Neo4jConnectPayload {
  url: string;
  user?: string | null;
  password?: string | null;
  database?: string | null;
}

export interface Neo4jConnectResponse {
  status: string;
  neo4j: boolean;
  url: string;
  database?: string | null;
}

export interface Neo4jStatusResponse {
  connected: boolean;
  url?: string | null;
  database?: string | null;
}

export interface CypherResult {
  columns: string[];
  rows: Record<string, any>[];
  row_count: number;
  execution_time_ms: number;
}

export type OverlayKind =
  | "gradual_strength"
  | "internal_correlation"
  | "degree"
  | "component"
  | "pagerank"
  | "leiden"
  | "tenability"
  | "b_consistency"
  | "stable_extension";

export interface Overlay {
  id: string;
  kind: OverlayKind;
  params: Record<string, any>;
  node_values: Record<string, number | string | null>;
  edge_values: Record<string, number | string | null>;
  scale: "continuous" | "categorical" | "ordinal";
  domain?: number[] | string[] | null;
  computed_at: string;
  graph_version: string;
  incomplete_inputs: number;
}

export interface ComputeOverlayRequest {
  run_id?: string | null;
  graph_version?: string | null;
  kind: OverlayKind;
  source?: "artifacts" | "neo4j" | null;
  params?: Record<string, any>;
}

export type FieldProvenance = "default" | "env" | "profile" | "override";

export interface ConfigView {
  values: Record<string, any>;
  provenance: Record<string, FieldProvenance>;
  profile_id?: string | null;
  schema_version: string;
}

export interface ConfigPatch {
  profile_id?: string | null;
  patch: Record<string, any>;
  parent_run_id?: string | null;
  source_paths?: string[];
  bib_paths?: string[];
  structural_anchor?: GlobalStructuralAnchor | null;
}

export interface InvalidationPreview {
  invalidated_phases: number[];
  reused_phases: number[];
  changed_fingerprints: Record<string, [string | null, string | null]>;
  reason: string;
  estimated_artifact_loss: number;
}

export type MetricScope = "global" | "single_node";

export interface MetricDescriptor {
  id: string;
  label: string;
  description: string;
  scope: MetricScope;
  available: boolean;
  unavailable_reason?: string | null;
  engine: "cypher" | "gds" | "igraph" | "python" | "epistemetrics";
  param_schema: Record<string, any>;
}

export interface AffectedNodeDetail {
  roles: string[];
  net_contribution?: number | null;
  metadata: Record<string, any>;
}

export interface AffectedEdgeDetail {
  source_node_id: string;
  target_node_id: string;
  relationship_id?: string | null;
  role: string;
  weight?: number | null;
  polarity?: number | null;
  hop_distance: number;
  contribution?: number | null;
  metadata: Record<string, any>;
}

export interface MetricResult {
  execution_id: string;
  metric_id: string;
  scope: MetricScope;
  focus_node_id?: string | null;
  result_value?: number | string | null;
  graph_revision: string;
  duration_ms: number;
  summary: Record<string, any>;
  affected_nodes: Record<string, AffectedNodeDetail>;
  affected_edges: AffectedEdgeDetail[];
  warnings: string[];
  computed_at: string;
}

export type MetricOrientation = "natural" | "reversed" | "undirected";
export type MetricSizeStrength = "subtle" | "normal" | "strong";

export interface MetricRunConfig {
  instanceId: string;
  metricId: string;
  focusNodeId?: string | null;
  params: Record<string, any>;
  nodeLabels: string[];
  relationshipTypes: string[];
  relationshipWeightProperty?: string;
  orientation?: MetricOrientation;
  styling: {
    enabled: boolean;
    sizeScaling: boolean;
    colorGradient: boolean;
    sizeStrength?: MetricSizeStrength;
  };
  isConfigOpen?: boolean;
  isCollapsed?: boolean;
}

export interface MetricRunInstance extends MetricRunConfig {
  status: "idle" | "running" | "completed" | "failed";
  result?: MetricResult | null;
  error?: string | null;
  elapsedSeconds?: number;
  executionId?: string | null;
}

export interface StyleConflictInfo {
  hasSizeConflict: boolean;
  conflictingSizeInstances: string[];
  hasColorConflict: boolean;
  conflictingColorInstances: string[];
  activeSizeCount: number;
  activeColorCount: number;
}

export interface ExecuteMetricRequest {
  metric_id: string;
  focus_node_id?: string | null;
  params?: Record<string, any>;
  source?: "artifacts" | "neo4j" | null;
  run_id?: string | null;
  graph_version?: string | null;
}

export interface MetricExecutionQueuedResponse {
  execution_id: string;
  status: "queued" | "running";
  status_url: string;
}

export interface ExecutionStatusResponse {
  execution_id: string;
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
  progress?: number | null;
  result?: MetricResult | null;
  error?: ProblemDetail | null;
}

export interface PromptResolveRequest {
  provider: "default" | "langfuse" | "file";
  label_or_version?: string;
  prompts_dir?: string | null;
  host?: string | null;
  public_key?: string | null;
  secret_key?: string | null;
}

export interface LangfuseTestRequest {
  host?: string | null;
  public_key?: string | null;
  secret_key?: string | null;
}

export interface ResolvedPromptItem {
  name: string;
  version?: number | null;
  label?: string | null;
  provider: string;
  direct_template: string;
  reasoning_template?: string | null;
  format_template?: string | null;
  gleaning_template?: string | null;
  metadata?: Record<string, any>;
}

export interface PromptResolveResponse {
  provider: string;
  label_or_version: string;
  bundles: Record<string, ResolvedPromptItem>;
  warning?: string | null;
}

export interface AvailableInputDoc {
  path: string;
  name: string;
  size_bytes: number;
  description?: string | null;
}

export interface LangfuseStatusResponse {
  configured: boolean;
  host: string;
  has_public_key: boolean;
  public_key_preview?: string | null;
  has_secret_key: boolean;
  telemetry_enabled: boolean;
  connected: boolean;
  message?: string | null;
}

export type NodeDiffStatus = "retained" | "gained" | "lost";

export type EdgeDiffStatus =
  | "retained"
  | "gained"
  | "lost"
  | "polarity_inverted"
  | "weight_shifted";

export interface PolarityInversion {
  edge_id: string;
  source: string;
  target: string;
  source_label: string;
  target_label: string;
  predicate_a: string;
  polarity_a?: number | null;
  weight_a?: number | null;
  predicate_b: string;
  polarity_b?: number | null;
  weight_b?: number | null;
  scope: string;
}

export interface ConfigDeltaItem {
  path: string;
  category: "models" | "prompts" | "phase" | "general" | string;
  value_a?: any;
  value_b?: any;
}

export interface DiffKPIs {
  nodes_retained: number;
  nodes_gained: number;
  nodes_lost: number;
  edges_retained: number;
  edges_gained: number;
  edges_lost: number;
  polarity_inversions_count: number;
  jaccard_node_similarity: number;
  jaccard_edge_similarity: number;
  l2_entity_delta: number;
  l3_atom_delta: number;
  max_rho_drift: number;
}

export interface GraphDiffView {
  run_a_id: string;
  run_b_id: string;
  union_graph: GraphView;
  node_diff: Record<string, NodeDiffStatus>;
  edge_diff: Record<string, EdgeDiffStatus>;
  polarity_inversions: PolarityInversion[];
  rho_deltas: Record<string, number>;
  config_diff: ConfigDeltaItem[];
  kpis: DiffKPIs;
}

export interface RunLangfuseResponse {
  configured: boolean;
  connected: boolean;
  run_id: string;
  trace_id?: string;
  count: number;
  observations: any[];
  message?: string;
}

export interface SchemaConfig {
  version: string;
  node_types: string[];
  relation_types: string[];
  node_definitions: Record<string, string>;
  relation_definitions: Record<string, string>;
  component_types: string[];
  argument_relation_types: string[];
  component_definitions: Record<string, string>;
  argument_relation_definitions: Record<string, string>;
  relation_polarities: Record<string, number>;
  component_partitions: Record<string, string>;
  predicate_aliases?: Record<string, any>;
}

export interface PredicateMapping {
  predicate: string;
  polarity: -1 | 0 | 1;
  canonical?: string | null;
  definition?: string | null;
}

export interface UnmappedPredicateInfo {
  predicate: string;
  occurrences: number;
  sample_runs: string[];
}

export interface EngineSettings {
  schema_config: SchemaConfig;
  predicate_aliases: Record<string, any>;
  models: {
    llm_model: string;
    embedding_model: string;
    reranker_model: string;
    temperature: number;
    seed?: number | null;
    llm_api_base?: string | null;
    thinking_level: string;
  };
  updated_at: string;
}

export interface EngineSettingsPatch {
  schema_config?: Partial<SchemaConfig>;
  predicate_aliases?: Record<string, any>;
  models?: Partial<EngineSettings["models"]>;
}

export interface DynamicsStepDetail {
  step: string;
  delta_auxiliary: number;
  anomalies_count: number;
  delta_empirical: number;
  step_degeneration_index: number;
}

export interface DynamicsTrajectoryRequest {
  run_ids?: string[];
  snapshots?: Record<string, any>[];
  core_node_ids?: string[];
  epsilon?: number;
}

export interface DynamicsTrajectoryResponse {
  degeneration_index: number;
  is_progressive: boolean;
  core_invariant: boolean;
  delta_auxiliary: number;
  anomalies_count: number;
  delta_empirical_content: number;
  violated_invariance: Record<string, any>[];
  node_immunization_scores: Record<string, number>;
  trajectory: DynamicsStepDetail[];
  chart_data: {
    epochs: string[];
    steps: string[];
    di_series: number[];
    delta_auxiliary_series: number[];
    delta_empirical_series: number[];
    anomalies_series: number[];
    overall_degeneration_index: number;
    progressive_threshold: number;
    is_progressive: boolean;
    core_invariant: boolean;
  };
  summary_markdown: string;
}

export type AdjudicationDecision = "true_positive" | "false_positive" | "schema_alias";

export interface EdgeAdjudicationItem {
  adjudication_id: string;
  predicted_edge: Record<string, any>;
  reference_edge?: Record<string, any> | null;
  similarity_score?: number;
  decision: AdjudicationDecision;
  alias_target?: string | null;
  rationale?: string | null;
  adjudicated_by?: string | null;
  adjudicated_at?: string;
}

export interface AdjudicationRequest {
  items: EdgeAdjudicationItem[];
  gold_standard_path?: string | null;
  export_dataset_path?: string | null;
}

export interface AdjudicationResponse {
  adjudicated_count: number;
  stored_items: EdgeAdjudicationItem[];
  exported_gold_path?: string | null;
  message: string;
}

export type EvaluationJobStatus = "pending" | "running" | "completed" | "failed";

export interface EvaluationJobDescriptor {
  job_id: string;
  status: EvaluationJobStatus;
  created_at: string;
  completed_at?: string | null;
  request_type: string;
  report_id?: string | null;
  error?: string | null;
  report?: any | null;
}

