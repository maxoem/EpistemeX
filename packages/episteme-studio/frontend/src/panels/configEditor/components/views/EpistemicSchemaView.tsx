import React, {useMemo, useState} from "react";
import {Plus, Search, X} from "lucide-react";
import {
    DEFAULT_COMPONENT_PARTITIONS,
    DEFAULT_L2_NODE_DEFINITIONS,
    DEFAULT_L2_RELATION_DEFINITIONS,
    DEFAULT_L3_ARGUMENT_RELATION_DEFINITIONS,
    DEFAULT_L3_COMPONENT_DEFINITIONS,
    DEFAULT_RELATION_POLARITIES,
} from "../../constants";
import {SchemaFilterState} from "../../types";

interface EpistemicSchemaViewProps {
  patch: Record<string, any>;
  configValues?: Record<string, any>;
  updateField: (fieldPath: string, value: any) => void;
}

export const EpistemicSchemaView: React.FC<EpistemicSchemaViewProps> = ({
  patch,
  configValues,
  updateField,
}) => {
  // Schema builder inputs
  const [newEntityType, setNewEntityType] = useState<string>("");
  const [newEntityDef, setNewEntityDef] = useState<string>("");
  const [newRelationType, setNewRelationType] = useState<string>("");
  const [newRelationDef, setNewRelationDef] = useState<string>("");
  const [newComponentType, setNewComponentType] = useState<string>("");
  const [newComponentPartition, setNewComponentPartition] = useState<string>("B");
  const [newComponentDef, setNewComponentDef] = useState<string>("");
  const [newArgumentRelationType, setNewArgumentRelationType] = useState<string>("");
  const [newArgumentRelationPolarity, setNewArgumentRelationPolarity] = useState<number>(1);
  const [newArgumentRelationDef, setNewArgumentRelationDef] = useState<string>("");
  const [schemaActiveTab, setSchemaActiveTab] = useState<SchemaFilterState["activeTab"]>("all");
  const [schemaFilterText, setSchemaFilterText] = useState<string>("");

  // Schema state
  const activeNodeTypes: string[] =
    patch["graph_schema.node_types"] ||
    configValues?.["graph_schema.node_types"] ||
    Object.keys(DEFAULT_L2_NODE_DEFINITIONS);

  const activeRelationTypes: string[] =
    patch["graph_schema.relation_types"] ||
    configValues?.["graph_schema.relation_types"] ||
    Object.keys(DEFAULT_L2_RELATION_DEFINITIONS);

  const activeNodeDefinitions: Record<string, string> = {
    ...DEFAULT_L2_NODE_DEFINITIONS,
    ...(configValues?.["graph_schema.node_definitions"] || {}),
    ...(patch["graph_schema.node_definitions"] || {}),
  };

  const activeRelationDefinitions: Record<string, string> = {
    ...DEFAULT_L2_RELATION_DEFINITIONS,
    ...(configValues?.["graph_schema.relation_definitions"] || {}),
    ...(patch["graph_schema.relation_definitions"] || {}),
  };

  const activeComponentTypes: string[] =
    patch["graph_schema.component_types"] ||
    configValues?.["graph_schema.component_types"] ||
    Object.keys(DEFAULT_L3_COMPONENT_DEFINITIONS);

  const activeComponentDefinitions: Record<string, string> = {
    ...DEFAULT_L3_COMPONENT_DEFINITIONS,
    ...(configValues?.["graph_schema.component_definitions"] || {}),
    ...(patch["graph_schema.component_definitions"] || {}),
  };

  const activeComponentPartitions: Record<string, string> = {
    ...DEFAULT_COMPONENT_PARTITIONS,
    ...(configValues?.["graph_schema.component_partitions"] || {}),
    ...(patch["graph_schema.component_partitions"] || {}),
  };

  const activeArgumentRelationTypes: string[] =
    patch["graph_schema.argument_relation_types"] ||
    configValues?.["graph_schema.argument_relation_types"] ||
    Object.keys(DEFAULT_L3_ARGUMENT_RELATION_DEFINITIONS);

  const activeArgumentRelationDefinitions: Record<string, string> = {
    ...DEFAULT_L3_ARGUMENT_RELATION_DEFINITIONS,
    ...(configValues?.["graph_schema.argument_relation_definitions"] || {}),
    ...(patch["graph_schema.argument_relation_definitions"] || {}),
  };

  const activeRelationPolarities: Record<string, number> = {
    ...DEFAULT_RELATION_POLARITIES,
    ...(configValues?.["graph_schema.relation_polarities"] || {}),
    ...(patch["graph_schema.relation_polarities"] || {}),
  };

  const normalizedFilter = schemaFilterText.trim().toLowerCase();

  const filteredNodeTypes = useMemo(() => {
    if (!normalizedFilter) return activeNodeTypes;
    return activeNodeTypes.filter((t) => {
      const def = activeNodeDefinitions[t] || "";
      return t.toLowerCase().includes(normalizedFilter) || def.toLowerCase().includes(normalizedFilter);
    });
  }, [activeNodeTypes, activeNodeDefinitions, normalizedFilter]);

  const filteredRelationTypes = useMemo(() => {
    if (!normalizedFilter) return activeRelationTypes;
    return activeRelationTypes.filter((t) => {
      const def = activeRelationDefinitions[t] || "";
      return t.toLowerCase().includes(normalizedFilter) || def.toLowerCase().includes(normalizedFilter);
    });
  }, [activeRelationTypes, activeRelationDefinitions, normalizedFilter]);

  const filteredComponentTypes = useMemo(() => {
    if (!normalizedFilter) return activeComponentTypes;
    return activeComponentTypes.filter((t) => {
      const def = activeComponentDefinitions[t] || "";
      const partition = activeComponentPartitions[t] || "A";
      return (
        t.toLowerCase().includes(normalizedFilter) ||
        def.toLowerCase().includes(normalizedFilter) ||
        partition.toLowerCase().includes(normalizedFilter)
      );
    });
  }, [activeComponentTypes, activeComponentDefinitions, activeComponentPartitions, normalizedFilter]);

  const filteredArgumentRelationTypes = useMemo(() => {
    if (!normalizedFilter) return activeArgumentRelationTypes;
    return activeArgumentRelationTypes.filter((t) => {
      const def = activeArgumentRelationDefinitions[t] || "";
      return t.toLowerCase().includes(normalizedFilter) || def.toLowerCase().includes(normalizedFilter);
    });
  }, [activeArgumentRelationTypes, activeArgumentRelationDefinitions, normalizedFilter]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="pb-5 border-b border-app-border/80">
        <div className="flex items-center justify-between gap-2">
          <h3 className="type-h1 text-app-heading">
            Schema & Ontology Specification
          </h3>
          <span className="type-caption text-app-muted">
            L2 Entities & L3 Arguments
          </span>
        </div>
        <p className="type-body text-app-muted mt-1.5 max-w-2xl">
          Decoupled epistemic ontology defining L2 entities, relational predicates, L3 argument components, and dialectical polarities.
          Injected dynamically into prompt templates via <code>&#123;entity_types&#125;</code> and <code>&#123;component_types&#125;</code>.
        </p>
      </div>

      {/* Toolbar (Zero-Box flat segmented controls) */}
      <div className="flex flex-wrap items-center justify-between gap-3 pb-2 border-b border-app-border">
        <div className="h-7 p-0.5 inline-flex items-center bg-app-bg rounded border border-app-border text-xs">
          {[
            {
              id: "all" as const,
              label: "All",
              count:
                activeNodeTypes.length +
                activeRelationTypes.length +
                activeComponentTypes.length +
                activeArgumentRelationTypes.length,
            },
            { id: "l2_nodes" as const, label: "L2 Entities", count: activeNodeTypes.length },
            { id: "l2_relations" as const, label: "L2 Relations", count: activeRelationTypes.length },
            { id: "l3_components" as const, label: "L3 Components", count: activeComponentTypes.length },
            { id: "l3_relations" as const, label: "L3 Relations", count: activeArgumentRelationTypes.length },
          ].map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setSchemaActiveTab(tab.id)}
              className={`h-6 px-2.5 rounded transition-colors cursor-pointer flex items-center gap-1.5 ${
                schemaActiveTab === tab.id
                  ? "bg-app-surface text-app-heading font-semibold shadow-xs"
                  : "text-app-muted hover:text-app-heading"
              }`}
            >
              <span>{tab.label}</span>
              <span className="text-[10px] font-mono px-1 rounded bg-app-subtle text-app-muted">
                {tab.count}
              </span>
            </button>
          ))}
        </div>

        <div className="relative">
          <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-app-muted" />
          <input
            type="text"
            value={schemaFilterText}
            onChange={(e) => setSchemaFilterText(e.target.value)}
            placeholder="Filter ontology..."
            className="h-7 w-48 pl-8 pr-2.5 bg-app-bg text-app-heading border border-app-border rounded text-xs focus:outline-none focus:border-blue-500 font-mono"
          />
        </div>
      </div>

      {/* Data Grids */}
      {(schemaActiveTab === "all" || schemaActiveTab === "l2_nodes") && (
        <div className="space-y-2">
          <div className="flex items-center justify-between pb-1 border-b border-app-border">
            <h4 className="text-xs font-semibold text-app-heading">
              L2 Entity Classifications ({filteredNodeTypes.length})
            </h4>
          </div>
          <div className="border border-app-border rounded-lg overflow-hidden bg-app-bg text-xs">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-app-surface border-b border-app-border text-[10px] text-app-muted font-mono uppercase tracking-wider">
                  <th className="py-2 px-3 w-48">Identifier</th>
                  <th className="py-2 px-3">Semantic Criteria & Prompt Guidance</th>
                  <th className="py-2 px-2 w-10 text-center"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-app-border-subtle">
                {filteredNodeTypes.map((type) => (
                  <tr key={type} className="hover:bg-app-surface/50 transition-colors">
                    <td className="px-3 py-2 font-mono font-semibold text-app-heading">{type}</td>
                    <td className="px-3 py-1">
                      <input
                        type="text"
                        value={activeNodeDefinitions[type] || ""}
                        onChange={(e) => {
                          const nextDefs = { ...activeNodeDefinitions, [type]: e.target.value };
                          updateField("graph_schema.node_definitions", nextDefs);
                        }}
                        className="w-full h-7 px-2 rounded bg-transparent hover:bg-app-surface focus:bg-app-surface border border-transparent focus:border-app-border text-xs text-app-heading focus:outline-none"
                      />
                    </td>
                    <td className="text-center px-2">
                      <button
                        type="button"
                        onClick={() => {
                          const nextTypes = activeNodeTypes.filter((t) => t !== type);
                          const nextDefs = { ...activeNodeDefinitions };
                          delete nextDefs[type];
                          updateField("graph_schema.node_types", nextTypes);
                          updateField("graph_schema.node_definitions", nextDefs);
                        }}
                        className="p-1 rounded text-app-muted hover:text-rose-500 cursor-pointer"
                      >
                        <X className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex items-center gap-2 pt-1">
            <input
              type="text"
              value={newEntityType}
              onChange={(e) => setNewEntityType(e.target.value)}
              placeholder="New Entity Type..."
              className="h-7 px-2.5 rounded bg-app-bg text-app-heading border border-app-border text-xs font-mono w-48 focus:outline-none focus:border-blue-500"
            />
            <input
              type="text"
              value={newEntityDef}
              onChange={(e) => setNewEntityDef(e.target.value)}
              placeholder="Semantic classification description..."
              className="flex-1 h-7 px-2.5 rounded bg-app-bg text-app-heading border border-app-border text-xs focus:outline-none focus:border-blue-500"
            />
            <button
              type="button"
              onClick={() => {
                const trimmed = newEntityType.trim();
                if (!trimmed) return;
                const nextTypes = [...activeNodeTypes, trimmed];
                const nextDefs = { ...activeNodeDefinitions, [trimmed]: newEntityDef.trim() };
                updateField("graph_schema.node_types", nextTypes);
                updateField("graph_schema.node_definitions", nextDefs);
                setNewEntityType("");
                setNewEntityDef("");
              }}
              className="h-7 px-3 rounded bg-blue-600 hover:bg-blue-700 text-white text-xs font-medium cursor-pointer flex items-center gap-1 shrink-0"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Add</span>
            </button>
          </div>
        </div>
      )}

      {(schemaActiveTab === "all" || schemaActiveTab === "l2_relations") && (
        <div className="space-y-2">
          <div className="flex items-center justify-between pb-1 border-b border-app-border">
            <h4 className="text-xs font-semibold text-app-heading">
              L2 Domain Relation Predicates ({filteredRelationTypes.length})
            </h4>
          </div>
          <div className="border border-app-border rounded-lg overflow-hidden bg-app-bg text-xs">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-app-surface border-b border-app-border text-[10px] text-app-muted font-mono uppercase tracking-wider">
                  <th className="py-2 px-3 w-48">Predicate</th>
                  <th className="py-2 px-3">Entailment Scope & Direction</th>
                  <th className="py-2 px-2 w-10 text-center"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-app-border-subtle">
                {filteredRelationTypes.map((rel) => (
                  <tr key={rel} className="hover:bg-app-surface/50 transition-colors">
                    <td className="px-3 py-2 font-mono font-semibold text-app-heading">{rel}</td>
                    <td className="px-3 py-1">
                      <input
                        type="text"
                        value={activeRelationDefinitions[rel] || ""}
                        onChange={(e) => {
                          const nextDefs = { ...activeRelationDefinitions, [rel]: e.target.value };
                          updateField("graph_schema.relation_definitions", nextDefs);
                        }}
                        className="w-full h-7 px-2 rounded bg-transparent hover:bg-app-surface focus:bg-app-surface border border-transparent focus:border-app-border text-xs text-app-heading focus:outline-none"
                      />
                    </td>
                    <td className="text-center px-2">
                      <button
                        type="button"
                        onClick={() => {
                          const nextTypes = activeRelationTypes.filter((t) => t !== rel);
                          const nextDefs = { ...activeRelationDefinitions };
                          delete nextDefs[rel];
                          updateField("graph_schema.relation_types", nextTypes);
                          updateField("graph_schema.relation_definitions", nextDefs);
                        }}
                        className="p-1 rounded text-app-muted hover:text-rose-500 cursor-pointer"
                      >
                        <X className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex items-center gap-2 pt-1">
            <input
              type="text"
              value={newRelationType}
              onChange={(e) => setNewRelationType(e.target.value)}
              placeholder="New Relation Predicate..."
              className="h-7 px-2.5 rounded bg-app-bg text-app-heading border border-app-border text-xs font-mono w-48 focus:outline-none focus:border-blue-500"
            />
            <input
              type="text"
              value={newRelationDef}
              onChange={(e) => setNewRelationDef(e.target.value)}
              placeholder="Relational definition..."
              className="flex-1 h-7 px-2.5 rounded bg-app-bg text-app-heading border border-app-border text-xs focus:outline-none focus:border-blue-500"
            />
            <button
              type="button"
              onClick={() => {
                const trimmed = newRelationType.trim();
                if (!trimmed) return;
                const nextTypes = [...activeRelationTypes, trimmed];
                const nextDefs = { ...activeRelationDefinitions, [trimmed]: newRelationDef.trim() };
                updateField("graph_schema.relation_types", nextTypes);
                updateField("graph_schema.relation_definitions", nextDefs);
                setNewRelationType("");
                setNewRelationDef("");
              }}
              className="h-7 px-3 rounded bg-blue-600 hover:bg-blue-700 text-white text-xs font-medium cursor-pointer flex items-center gap-1 shrink-0"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Add</span>
            </button>
          </div>
        </div>
      )}

      {(schemaActiveTab === "all" || schemaActiveTab === "l3_components") && (
        <div className="space-y-2">
          <div className="flex items-center justify-between pb-1 border-b border-app-border">
            <h4 className="text-xs font-semibold text-app-heading">
              L3 Argument Components & Partitions ({filteredComponentTypes.length})
            </h4>
          </div>
          <div className="border border-app-border rounded-lg overflow-hidden bg-app-bg text-xs">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-app-surface border-b border-app-border text-[10px] text-app-muted font-mono uppercase tracking-wider">
                  <th className="py-2 px-3 w-48">Component</th>
                  <th className="py-2 px-3 w-36 text-center">Partition</th>
                  <th className="py-2 px-3">Classification Criteria</th>
                  <th className="py-2 px-2 w-10 text-center"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-app-border-subtle">
                {filteredComponentTypes.map((comp) => {
                  const part = activeComponentPartitions[comp] || "B";
                  return (
                    <tr key={comp} className="hover:bg-app-surface/50 transition-colors">
                      <td className="px-3 py-2 font-mono font-semibold text-app-heading">{comp}</td>
                      <td className="px-3 py-1 text-center">
                        <div className="inline-flex rounded border border-app-border p-0.5 bg-app-surface text-[10px] font-mono">
                          <button
                            type="button"
                            onClick={() => {
                              const nextParts = { ...activeComponentPartitions, [comp]: "A" };
                              updateField("graph_schema.component_partitions", nextParts);
                            }}
                            className={`px-1.5 py-0.5 rounded cursor-pointer ${
                              part === "A" ? "bg-app-heading text-app-surface font-semibold" : "text-app-muted"
                            }`}
                          >
                            Part. A (Core)
                          </button>
                          <button
                            type="button"
                            onClick={() => {
                              const nextParts = { ...activeComponentPartitions, [comp]: "B" };
                              updateField("graph_schema.component_partitions", nextParts);
                            }}
                            className={`px-1.5 py-0.5 rounded cursor-pointer ${
                              part === "B" ? "bg-app-heading text-app-surface font-semibold" : "text-app-muted"
                            }`}
                          >
                            Part. B (Data)
                          </button>
                        </div>
                      </td>
                      <td className="px-3 py-1">
                        <input
                          type="text"
                          value={activeComponentDefinitions[comp] || ""}
                          onChange={(e) => {
                            const nextDefs = { ...activeComponentDefinitions, [comp]: e.target.value };
                            updateField("graph_schema.component_definitions", nextDefs);
                          }}
                          className="w-full h-7 px-2 rounded bg-transparent hover:bg-app-surface focus:bg-app-surface border border-transparent focus:border-app-border text-xs text-app-heading focus:outline-none"
                        />
                      </td>
                      <td className="text-center px-2">
                        <button
                          type="button"
                          onClick={() => {
                            const nextTypes = activeComponentTypes.filter((t) => t !== comp);
                            const nextDefs = { ...activeComponentDefinitions };
                            delete nextDefs[comp];
                            const nextParts = { ...activeComponentPartitions };
                            delete nextParts[comp];
                            updateField("graph_schema.component_types", nextTypes);
                            updateField("graph_schema.component_definitions", nextDefs);
                            updateField("graph_schema.component_partitions", nextParts);
                          }}
                          className="p-1 rounded text-app-muted hover:text-rose-500 cursor-pointer"
                        >
                          <X className="w-3.5 h-3.5" />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div className="flex items-center gap-2 pt-1">
            <input
              type="text"
              value={newComponentType}
              onChange={(e) => setNewComponentType(e.target.value)}
              placeholder="New Component Type..."
              className="h-7 px-2.5 rounded bg-app-bg text-app-heading border border-app-border text-xs font-mono w-44 focus:outline-none focus:border-blue-500"
            />
            <select
              value={newComponentPartition}
              onChange={(e) => setNewComponentPartition(e.target.value)}
              className="h-7 px-2 rounded bg-app-bg text-app-heading border border-app-border text-xs font-mono focus:outline-none"
            >
              <option value="A">Part. A (Theoretical Core)</option>
              <option value="B">Part. B (Empirical Data)</option>
            </select>
            <input
              type="text"
              value={newComponentDef}
              onChange={(e) => setNewComponentDef(e.target.value)}
              placeholder="Epistemic criteria..."
              className="flex-1 h-7 px-2.5 rounded bg-app-bg text-app-heading border border-app-border text-xs focus:outline-none focus:border-blue-500"
            />
            <button
              type="button"
              onClick={() => {
                const trimmed = newComponentType.trim();
                if (!trimmed) return;
                const nextTypes = [...activeComponentTypes, trimmed];
                const nextDefs = { ...activeComponentDefinitions, [trimmed]: newComponentDef.trim() };
                const nextParts = { ...activeComponentPartitions, [trimmed]: newComponentPartition };
                updateField("graph_schema.component_types", nextTypes);
                updateField("graph_schema.component_definitions", nextDefs);
                updateField("graph_schema.component_partitions", nextParts);
                setNewComponentType("");
                setNewComponentDef("");
              }}
              className="h-7 px-3 rounded bg-blue-600 hover:bg-blue-700 text-white text-xs font-medium cursor-pointer flex items-center gap-1 shrink-0"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Add</span>
            </button>
          </div>
        </div>
      )}

      {(schemaActiveTab === "all" || schemaActiveTab === "l3_relations") && (
        <div className="space-y-2">
          <div className="flex items-center justify-between pb-1 border-b border-app-border">
            <h4 className="text-xs font-semibold text-app-heading">
              L3 Argument Relations & Polarities ({filteredArgumentRelationTypes.length})
            </h4>
          </div>
          <div className="border border-app-border rounded-lg overflow-hidden bg-app-bg text-xs">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-app-surface border-b border-app-border text-[10px] text-app-muted font-mono uppercase tracking-wider">
                  <th className="py-2 px-3 w-48">Relation Type</th>
                  <th className="py-2 px-3 w-44 text-center">Dialectical Polarity</th>
                  <th className="py-2 px-3">Logical Semantics</th>
                  <th className="py-2 px-2 w-10 text-center"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-app-border-subtle">
                {filteredArgumentRelationTypes.map((rel) => {
                  const pol = activeRelationPolarities[rel] ?? 0;
                  return (
                    <tr key={rel} className="hover:bg-app-surface/50 transition-colors">
                      <td className="px-3 py-2 font-mono font-semibold text-app-heading">{rel}</td>
                      <td className="px-3 py-1 text-center">
                        <div className="inline-flex rounded border border-app-border p-0.5 bg-app-surface text-[10px] font-mono">
                          <button
                            type="button"
                            onClick={() => {
                              const nextPol = { ...activeRelationPolarities, [rel]: 1 };
                              updateField("graph_schema.relation_polarities", nextPol);
                            }}
                            className={`px-1.5 py-0.5 rounded cursor-pointer ${
                              pol === 1 ? "bg-emerald-500 text-white font-semibold" : "text-app-muted"
                            }`}
                          >
                            +1 Supp.
                          </button>
                          <button
                            type="button"
                            onClick={() => {
                              const nextPol = { ...activeRelationPolarities, [rel]: 0 };
                              updateField("graph_schema.relation_polarities", nextPol);
                            }}
                            className={`px-1.5 py-0.5 rounded cursor-pointer ${
                              pol === 0 ? "bg-app-heading text-app-surface font-semibold" : "text-app-muted"
                            }`}
                          >
                            0 Neut.
                          </button>
                          <button
                            type="button"
                            onClick={() => {
                              const nextPol = { ...activeRelationPolarities, [rel]: -1 };
                              updateField("graph_schema.relation_polarities", nextPol);
                            }}
                            className={`px-1.5 py-0.5 rounded cursor-pointer ${
                              pol === -1 ? "bg-rose-500 text-white font-semibold" : "text-app-muted"
                            }`}
                          >
                            -1 Attack
                          </button>
                        </div>
                      </td>
                      <td className="px-3 py-1">
                        <input
                          type="text"
                          value={activeArgumentRelationDefinitions[rel] || ""}
                          onChange={(e) => {
                            const nextDefs = { ...activeArgumentRelationDefinitions, [rel]: e.target.value };
                            updateField("graph_schema.argument_relation_definitions", nextDefs);
                          }}
                          className="w-full h-7 px-2 rounded bg-transparent hover:bg-app-surface focus:bg-app-surface border border-transparent focus:border-app-border text-xs text-app-heading focus:outline-none"
                        />
                      </td>
                      <td className="text-center px-2">
                        <button
                          type="button"
                          onClick={() => {
                            const nextTypes = activeArgumentRelationTypes.filter((t) => t !== rel);
                            const nextDefs = { ...activeArgumentRelationDefinitions };
                            delete nextDefs[rel];
                            updateField("graph_schema.argument_relation_types", nextTypes);
                            updateField("graph_schema.argument_relation_definitions", nextDefs);
                          }}
                          className="p-1 rounded text-app-muted hover:text-rose-500 cursor-pointer"
                        >
                          <X className="w-3.5 h-3.5" />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div className="flex items-center gap-2 pt-1">
            <input
              type="text"
              value={newArgumentRelationType}
              onChange={(e) => setNewArgumentRelationType(e.target.value)}
              placeholder="New Argument Relation..."
              className="h-7 px-2.5 rounded bg-app-bg text-app-heading border border-app-border text-xs font-mono w-44 focus:outline-none focus:border-blue-500"
            />
            <select
              value={newArgumentRelationPolarity}
              onChange={(e) => setNewArgumentRelationPolarity(parseInt(e.target.value, 10))}
              className="h-7 px-2 rounded bg-app-bg text-app-heading border border-app-border text-xs font-mono focus:outline-none"
            >
              <option value={1}>+1 Support</option>
              <option value={0}>0 Neutral / Structural</option>
              <option value={-1}>-1 Attack / Undercut</option>
            </select>
            <input
              type="text"
              value={newArgumentRelationDef}
              onChange={(e) => setNewArgumentRelationDef(e.target.value)}
              placeholder="Inferential criteria..."
              className="flex-1 h-7 px-2.5 rounded bg-app-bg text-app-heading border border-app-border text-xs focus:outline-none focus:border-blue-500"
            />
            <button
              type="button"
              onClick={() => {
                const trimmed = newArgumentRelationType.trim();
                if (!trimmed) return;
                const nextTypes = [...activeArgumentRelationTypes, trimmed];
                const nextDefs = { ...activeArgumentRelationDefinitions, [trimmed]: newArgumentRelationDef.trim() };
                const nextPols = { ...activeRelationPolarities, [trimmed]: newArgumentRelationPolarity };
                updateField("graph_schema.argument_relation_types", nextTypes);
                updateField("graph_schema.argument_relation_definitions", nextDefs);
                updateField("graph_schema.relation_polarities", nextPols);
                setNewArgumentRelationType("");
                setNewArgumentRelationDef("");
              }}
              className="h-7 px-3 rounded bg-blue-600 hover:bg-blue-700 text-white text-xs font-medium cursor-pointer flex items-center gap-1 shrink-0"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Add</span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
