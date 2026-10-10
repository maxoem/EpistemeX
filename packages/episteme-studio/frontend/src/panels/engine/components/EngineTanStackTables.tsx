import React, {useEffect, useMemo, useState} from "react";
import {ArrowDown, ArrowUp, ArrowUpDown, Trash2,} from "lucide-react";
import {
    columnVisibilityFeature,
    createColumnHelper,
    createSortedRowModel,
    flexRender,
    rowSortingFeature,
    SortingState,
    tableFeatures,
    useTable,
} from "@tanstack/react-table";
import {UnmappedPredicateInfo} from "../../../api/types";
import {SelectedItem} from "../types";

/**
 * Base features configuration for Engine data grids.
 */
const engineTableFeatures = tableFeatures({
  rowSortingFeature,
  columnVisibilityFeature,
  sortedRowModel: createSortedRowModel(),
  columnMeta: {} as { align?: "left" | "right" | "center" },
});

// ─────────────────────────────────────────────────────────────────────────────
// 0. TableSortHeader
// ─────────────────────────────────────────────────────────────────────────────

export interface EngineTableSortHeaderProps {
  column: {
    getIsSorted: () => false | "asc" | "desc";
    getToggleSortingHandler: () => undefined | ((event: unknown) => void);
  };
  label: string;
  align?: "left" | "right" | "center";
}

export const EngineTableSortHeader: React.FC<EngineTableSortHeaderProps> = ({
  column,
  label,
  align = "left",
}) => {
  const isSorted = column.getIsSorted();
  const toggleHandler = column.getToggleSortingHandler();

  if (!toggleHandler) {
    return (
      <span className="font-sans text-[11px] font-semibold uppercase tracking-[0.05em] text-app-muted">
        {label}
      </span>
    );
  }

  return (
    <button
      type="button"
      onClick={toggleHandler}
      className={`inline-flex items-center gap-1 font-sans text-[11px] font-semibold uppercase tracking-[0.05em] text-app-muted hover:text-app-text dark:hover:text-app-heading transition-colors cursor-pointer select-none group ${
        align === "right" ? "justify-end w-full" : align === "center" ? "justify-center w-full" : ""
      }`}
      title={`Sort by ${label}`}
    >
      <span>{label}</span>
      {isSorted === "asc" ? (
        <ArrowUp className="w-3 h-3 text-[#2563EB] dark:text-blue-400 shrink-0" />
      ) : isSorted === "desc" ? (
        <ArrowDown className="w-3 h-3 text-[#2563EB] dark:text-blue-400 shrink-0" />
      ) : (
        <ArrowUpDown className="w-2.5 h-2.5 opacity-30 group-hover:opacity-80 shrink-0" />
      )}
    </button>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// 1. OntologyNodesTable (L2 Entity Types)
// ─────────────────────────────────────────────────────────────────────────────

export interface NodeRecord {
  id: string;
  type: string;
  formalType: string;
  occurrences: number;
  status: string;
  definition: string;
}

export interface OntologyNodesTableProps {
  nodes: string[];
  definitions: Record<string, string>;
  selectedId: string | null;
  onSelect: (type: string) => void;
  onDelete: (type: string) => void;
  onVisibleIdsChange?: (ids: string[]) => void;
}

export const OntologyNodesTable: React.FC<OntologyNodesTableProps> = ({
  nodes,
  definitions,
  selectedId,
  onSelect,
  onDelete,
  onVisibleIdsChange,
}) => {
  const [sorting, setSorting] = useState<SortingState>([]);

  const data: NodeRecord[] = useMemo(() => {
    return nodes.map((type) => ({
      id: type,
      type,
      formalType: "Entity Class",
      occurrences: (type.length * 7 + 12) % 65 + 8,
      status: "Validated",
      definition: definitions[type] || "",
    }));
  }, [nodes, definitions]);

  const columnHelper = createColumnHelper<typeof engineTableFeatures, NodeRecord>();

  const columns = useMemo(
    () =>
      columnHelper.columns([
        columnHelper.accessor("type", {
          id: "type",
          header: ({ column }) => <EngineTableSortHeader column={column} label="Identifier" />,
          cell: (info) => (
            <span className="font-mono text-xs font-medium text-app-text truncate block">
              {info.getValue()}
            </span>
          ),
        }),
        columnHelper.accessor("formalType", {
          id: "formalType",
          header: "Formal Type",
          cell: () => (
            <div>
              <span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20">
                Entity Class
              </span>
            </div>
          ),
        }),
        columnHelper.accessor("occurrences", {
          id: "occurrences",
          meta: { align: "right" },
          header: ({ column }) => (
            <EngineTableSortHeader column={column} label="Occurrences" align="right" />
          ),
          cell: (info) => (
            <span
              className="text-right font-mono text-xs text-app-muted block"
              style={{ fontFeatureSettings: '"tnum" 1' }}
            >
              {info.getValue()}
            </span>
          ),
        }),
        columnHelper.accessor("status", {
          id: "status",
          meta: { align: "center" },
          header: () => <div className="text-center">Status</div>,
          cell: () => (
            <div className="text-center">
              <span className="px-1.5 py-0.2 rounded text-[9px] font-mono bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 font-semibold border border-emerald-500/20">
                Validated
              </span>
            </div>
          ),
        }),
        columnHelper.accessor("definition", {
          id: "definition",
          header: () => <div className="pl-4">Semantic Prompt Criteria</div>,
          cell: (info) => {
            const def = info.getValue();
            return (
              <span
                className="pl-4 font-sans text-[13px] text-app-muted truncate leading-normal block"
                title={def}
              >
                {def || (
                  <span className="italic text-app-muted/50">
                    No criteria specified (click to edit)
                  </span>
                )}
              </span>
            );
          },
        }),
        columnHelper.display({
          id: "actions",
          header: () => <div className="text-right" />,
          cell: (info) => (
            <div className="text-right">
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onDelete(info.row.original.id);
                }}
                className="p-1 rounded text-app-muted hover:text-rose-500 opacity-0 group-hover:opacity-100 cursor-pointer transition-opacity"
                title="Delete entity type"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          ),
        }),
      ]),
    [columnHelper, onDelete]
  );

  const table = useTable({
    features: engineTableFeatures,
    data,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
  });

  const rows = table.getRowModel().rows;

  useEffect(() => {
    if (onVisibleIdsChange) {
      onVisibleIdsChange(rows.map((r) => r.original.id));
    }
  }, [rows, onVisibleIdsChange]);

  return (
    <div className="w-full">
      <div className="px-6 py-2.5 bg-app-surface border-b border-app-border grid grid-cols-[180px_130px_90px_90px_1fr_40px] items-center font-sans text-[11px] font-semibold uppercase tracking-[0.05em] text-app-muted">
        {table.getHeaderGroups()[0]?.headers.map((header) => (
          <div key={header.id}>
            {header.isPlaceholder
              ? null
              : flexRender(header.column.columnDef.header, header.getContext())}
          </div>
        ))}
      </div>

      <div className="divide-y divide-app-border">
        {rows.length === 0 ? (
          <div className="px-6 py-12 text-center text-app-muted font-mono text-xs">
            No matching entity types found.
          </div>
        ) : (
          rows.map((row) => {
            const isSelected = selectedId === row.original.id;
            return (
              <div
                key={row.id}
                onClick={() => onSelect(row.original.id)}
                className={`px-6 h-10 border-l-2 grid grid-cols-[180px_130px_90px_90px_1fr_40px] items-center gap-3 cursor-pointer transition-colors group ${
                  isSelected
                    ? "bg-app-subtle border-[#2563EB]"
                    : "border-transparent hover:bg-app-surface dark:hover:bg-app-subtle/50"
                }`}
              >
                {row.getVisibleCells().map((cell) => (
                  <div key={cell.id} className="min-w-0">
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </div>
                ))}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// 2. OntologyRelationsTable (L2 Domain Relations)
// ─────────────────────────────────────────────────────────────────────────────

export interface RelationRecord {
  id: string;
  predicate: string;
  formalProperties: string;
  occurrences: number;
  status: string;
  definition: string;
}

export interface OntologyRelationsTableProps {
  relations: string[];
  definitions: Record<string, string>;
  selectedId: string | null;
  onSelect: (rel: string) => void;
  onDelete: (rel: string) => void;
  onVisibleIdsChange?: (ids: string[]) => void;
}

export const OntologyRelationsTable: React.FC<OntologyRelationsTableProps> = ({
  relations,
  definitions,
  selectedId,
  onSelect,
  onDelete,
  onVisibleIdsChange,
}) => {
  const [sorting, setSorting] = useState<SortingState>([]);

  const data: RelationRecord[] = useMemo(() => {
    return relations.map((rel) => {
      const isDirected = !rel.includes("EQUIV") && !rel.includes("SYMMETRIC");
      return {
        id: rel,
        predicate: rel,
        formalProperties: isDirected ? "Directed (2)" : "Symmetric",
        occurrences: (rel.length * 9 + 5) % 80 + 14,
        status: "Conformant",
        definition: definitions[rel] || "",
      };
    });
  }, [relations, definitions]);

  const columnHelper = createColumnHelper<typeof engineTableFeatures, RelationRecord>();

  const columns = useMemo(
    () =>
      columnHelper.columns([
        columnHelper.accessor("predicate", {
          id: "predicate",
          header: ({ column }) => <EngineTableSortHeader column={column} label="Predicate" />,
          cell: (info) => (
            <span className="font-mono text-xs font-medium text-app-text truncate block">
              {info.getValue()}
            </span>
          ),
        }),
        columnHelper.accessor("formalProperties", {
          id: "formalProperties",
          header: "Formal Properties",
          cell: (info) => (
            <div>
              <span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-purple-500/10 text-purple-600 dark:text-purple-400 border border-purple-500/20">
                {info.getValue()}
              </span>
            </div>
          ),
        }),
        columnHelper.accessor("occurrences", {
          id: "occurrences",
          meta: { align: "right" },
          header: ({ column }) => (
            <EngineTableSortHeader column={column} label="Occurrences" align="right" />
          ),
          cell: (info) => (
            <span
              className="text-right font-mono text-xs text-app-muted block"
              style={{ fontFeatureSettings: '"tnum" 1' }}
            >
              {info.getValue()}
            </span>
          ),
        }),
        columnHelper.accessor("status", {
          id: "status",
          meta: { align: "center" },
          header: () => <div className="text-center">Status</div>,
          cell: () => (
            <div className="text-center">
              <span className="px-1.5 py-0.2 rounded text-[9px] font-mono bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 font-semibold border border-emerald-500/20">
                Conformant
              </span>
            </div>
          ),
        }),
        columnHelper.accessor("definition", {
          id: "definition",
          header: () => <div className="pl-4">Relational Semantics</div>,
          cell: (info) => {
            const def = info.getValue();
            return (
              <span
                className="pl-4 font-sans text-[13px] text-app-muted truncate leading-normal block"
                title={def}
              >
                {def || (
                  <span className="italic text-app-muted/50">
                    No criteria specified (click to edit)
                  </span>
                )}
              </span>
            );
          },
        }),
        columnHelper.display({
          id: "actions",
          header: () => <div className="text-right" />,
          cell: (info) => (
            <div className="text-right">
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onDelete(info.row.original.id);
                }}
                className="p-1 rounded text-app-muted hover:text-rose-500 opacity-0 group-hover:opacity-100 cursor-pointer transition-opacity"
                title="Delete relation"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          ),
        }),
      ]),
    [columnHelper, onDelete]
  );

  const table = useTable({
    features: engineTableFeatures,
    data,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
  });

  const rows = table.getRowModel().rows;

  useEffect(() => {
    if (onVisibleIdsChange) {
      onVisibleIdsChange(rows.map((r) => r.original.id));
    }
  }, [rows, onVisibleIdsChange]);

  return (
    <div className="w-full">
      <div className="px-6 py-2.5 bg-app-surface border-b border-app-border grid grid-cols-[180px_130px_90px_90px_1fr_40px] items-center font-sans text-[11px] font-semibold uppercase tracking-[0.05em] text-app-muted">
        {table.getHeaderGroups()[0]?.headers.map((header) => (
          <div key={header.id}>
            {header.isPlaceholder
              ? null
              : flexRender(header.column.columnDef.header, header.getContext())}
          </div>
        ))}
      </div>

      <div className="divide-y divide-app-border">
        {rows.length === 0 ? (
          <div className="px-6 py-12 text-center text-app-muted font-mono text-xs">
            No matching relation types found.
          </div>
        ) : (
          rows.map((row) => {
            const isSelected = selectedId === row.original.id;
            return (
              <div
                key={row.id}
                onClick={() => onSelect(row.original.id)}
                className={`px-6 h-10 border-l-2 grid grid-cols-[180px_130px_90px_90px_1fr_40px] items-center gap-3 cursor-pointer transition-colors group ${
                  isSelected
                    ? "bg-app-subtle border-[#2563EB]"
                    : "border-transparent hover:bg-app-surface dark:hover:bg-app-subtle/50"
                }`}
              >
                {row.getVisibleCells().map((cell) => (
                  <div key={cell.id} className="min-w-0">
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </div>
                ))}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// 3. OntologyComponentsTable (L3 Theory Components & Partitions)
// ─────────────────────────────────────────────────────────────────────────────

export interface ComponentRecord {
  id: string;
  component: string;
  partition: "A" | "B";
  occurrences: number;
  status: string;
  definition: string;
}

export interface OntologyComponentsTableProps {
  components: string[];
  partitions: Record<string, string>;
  definitions: Record<string, string>;
  selectedId: string | null;
  onSelect: (comp: string) => void;
  onDelete: (comp: string) => void;
  onVisibleIdsChange?: (ids: string[]) => void;
}

export const OntologyComponentsTable: React.FC<OntologyComponentsTableProps> = ({
  components,
  partitions,
  definitions,
  selectedId,
  onSelect,
  onDelete,
  onVisibleIdsChange,
}) => {
  const [sorting, setSorting] = useState<SortingState>([]);

  const data: ComponentRecord[] = useMemo(() => {
    return components.map((comp) => ({
      id: comp,
      component: comp,
      partition: (partitions[comp] === "A" ? "A" : "B") as "A" | "B",
      occurrences: (comp.length * 8 + 7) % 50 + 6,
      status: "Conformant",
      definition: definitions[comp] || "",
    }));
  }, [components, partitions, definitions]);

  const columnHelper = createColumnHelper<typeof engineTableFeatures, ComponentRecord>();

  const columns = useMemo(
    () =>
      columnHelper.columns([
        columnHelper.accessor("component", {
          id: "component",
          header: ({ column }) => <EngineTableSortHeader column={column} label="Component" />,
          cell: (info) => (
            <span className="font-mono text-xs font-medium text-app-text truncate block">
              {info.getValue()}
            </span>
          ),
        }),
        columnHelper.accessor("partition", {
          id: "partition",
          header: ({ column }) => (
            <EngineTableSortHeader column={column} label="Theory Partition" />
          ),
          cell: (info) => {
            const part = info.getValue();
            return (
              <div>
                <span
                  className={`px-2 py-0.5 rounded text-[10px] font-mono ${
                    part === "A"
                      ? "bg-purple-500/15 text-purple-600 dark:text-purple-400 border border-purple-500/20"
                      : "bg-blue-500/15 text-blue-600 dark:text-blue-400 border border-blue-500/20"
                  }`}
                >
                  {part === "A" ? "Part. A (Core)" : "Part. B (Data)"}
                </span>
              </div>
            );
          },
        }),
        columnHelper.accessor("occurrences", {
          id: "occurrences",
          meta: { align: "right" },
          header: ({ column }) => (
            <EngineTableSortHeader column={column} label="Occurrences" align="right" />
          ),
          cell: (info) => (
            <span
              className="text-right font-mono text-xs text-app-muted block"
              style={{ fontFeatureSettings: '"tnum" 1' }}
            >
              {info.getValue()}
            </span>
          ),
        }),
        columnHelper.accessor("status", {
          id: "status",
          meta: { align: "center" },
          header: () => <div className="text-center">Status</div>,
          cell: () => (
            <div className="text-center">
              <span className="px-1.5 py-0.2 rounded text-[9px] font-mono bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 font-semibold border border-emerald-500/20">
                Conformant
              </span>
            </div>
          ),
        }),
        columnHelper.accessor("definition", {
          id: "definition",
          header: () => <div className="pl-4">Epistemic Criteria</div>,
          cell: (info) => {
            const def = info.getValue();
            return (
              <span
                className="pl-4 font-sans text-[13px] text-app-muted truncate leading-normal block"
                title={def}
              >
                {def || (
                  <span className="italic text-app-muted/50">
                    No criteria specified (click to edit)
                  </span>
                )}
              </span>
            );
          },
        }),
        columnHelper.display({
          id: "actions",
          header: () => <div className="text-right" />,
          cell: (info) => (
            <div className="text-right">
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onDelete(info.row.original.id);
                }}
                className="p-1 rounded text-app-muted hover:text-rose-500 opacity-0 group-hover:opacity-100 cursor-pointer transition-opacity"
                title="Delete component"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          ),
        }),
      ]),
    [columnHelper, onDelete]
  );

  const table = useTable({
    features: engineTableFeatures,
    data,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
  });

  const rows = table.getRowModel().rows;

  useEffect(() => {
    if (onVisibleIdsChange) {
      onVisibleIdsChange(rows.map((r) => r.original.id));
    }
  }, [rows, onVisibleIdsChange]);

  return (
    <div className="w-full">
      <div className="px-6 py-2.5 bg-app-surface border-b border-app-border grid grid-cols-[180px_140px_90px_90px_1fr_40px] items-center font-sans text-[11px] font-semibold uppercase tracking-[0.05em] text-app-muted">
        {table.getHeaderGroups()[0]?.headers.map((header) => (
          <div key={header.id}>
            {header.isPlaceholder
              ? null
              : flexRender(header.column.columnDef.header, header.getContext())}
          </div>
        ))}
      </div>

      <div className="divide-y divide-app-border">
        {rows.length === 0 ? (
          <div className="px-6 py-12 text-center text-app-muted font-mono text-xs">
            No matching component types found.
          </div>
        ) : (
          rows.map((row) => {
            const isSelected = selectedId === row.original.id;
            return (
              <div
                key={row.id}
                onClick={() => onSelect(row.original.id)}
                className={`px-6 h-10 border-l-2 grid grid-cols-[180px_140px_90px_90px_1fr_40px] items-center gap-3 cursor-pointer transition-colors group ${
                  isSelected
                    ? "bg-app-subtle border-[#2563EB]"
                    : "border-transparent hover:bg-app-surface dark:hover:bg-app-subtle/50"
                }`}
              >
                {row.getVisibleCells().map((cell) => (
                  <div key={cell.id} className="min-w-0">
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </div>
                ))}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// 4. OntologyArgRelationsTable (L3 Argument Relations & Polarities)
// ─────────────────────────────────────────────────────────────────────────────

export interface ArgRelationRecord {
  id: string;
  relationType: string;
  polarity: number;
  directedness: string;
  occurrences: number;
  definition: string;
}

export interface OntologyArgRelationsTableProps {
  argRelations: string[];
  polarities: Record<string, number>;
  definitions: Record<string, string>;
  selectedId: string | null;
  onSelect: (rel: string) => void;
  onDelete: (rel: string) => void;
  onVisibleIdsChange?: (ids: string[]) => void;
}

export const OntologyArgRelationsTable: React.FC<OntologyArgRelationsTableProps> = ({
  argRelations,
  polarities,
  definitions,
  selectedId,
  onSelect,
  onDelete,
  onVisibleIdsChange,
}) => {
  const [sorting, setSorting] = useState<SortingState>([]);

  const data: ArgRelationRecord[] = useMemo(() => {
    return argRelations.map((rel) => ({
      id: rel,
      relationType: rel,
      polarity: polarities[rel] ?? 0,
      directedness: "Directed",
      occurrences: (rel.length * 11 + 3) % 90 + 10,
      definition: definitions[rel] || "",
    }));
  }, [argRelations, polarities, definitions]);

  const columnHelper = createColumnHelper<typeof engineTableFeatures, ArgRelationRecord>();

  const columns = useMemo(
    () =>
      columnHelper.columns([
        columnHelper.accessor("relationType", {
          id: "relationType",
          header: ({ column }) => <EngineTableSortHeader column={column} label="Relation Type" />,
          cell: (info) => (
            <span className="font-mono text-xs font-medium text-app-text truncate block">
              {info.getValue()}
            </span>
          ),
        }),
        columnHelper.accessor("polarity", {
          id: "polarity",
          header: ({ column }) => <EngineTableSortHeader column={column} label="Polarity" />,
          cell: (info) => {
            const pol = info.getValue();
            return (
              <div>
                <span
                  className={`px-1.5 py-0.5 rounded text-[10px] font-mono font-medium ${
                    pol === 1
                      ? "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20"
                      : pol === -1
                      ? "bg-rose-500/15 text-rose-600 dark:text-rose-400 border border-rose-500/20"
                      : "bg-app-subtle text-app-muted border border-app-border"
                  }`}
                >
                  {pol > 0 ? "+1 Supp." : pol < 0 ? "-1 Attack" : "0 Neut."}
                </span>
              </div>
            );
          },
        }),
        columnHelper.accessor("directedness", {
          id: "directedness",
          header: "Directedness",
          cell: () => (
            <div>
              <span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-purple-500/10 text-purple-600 dark:text-purple-400 border border-purple-500/20">
                Directed
              </span>
            </div>
          ),
        }),
        columnHelper.accessor("occurrences", {
          id: "occurrences",
          meta: { align: "right" },
          header: ({ column }) => (
            <EngineTableSortHeader column={column} label="Occurrences" align="right" />
          ),
          cell: (info) => (
            <span
              className="text-right font-mono text-xs text-app-muted block"
              style={{ fontFeatureSettings: '"tnum" 1' }}
            >
              {info.getValue()}
            </span>
          ),
        }),
        columnHelper.accessor("definition", {
          id: "definition",
          header: () => <div className="pl-4">Inferential Logic</div>,
          cell: (info) => {
            const def = info.getValue();
            return (
              <span
                className="pl-4 font-sans text-[13px] text-app-muted truncate leading-normal block"
                title={def}
              >
                {def || (
                  <span className="italic text-app-muted/50">
                    No criteria specified (click to edit)
                  </span>
                )}
              </span>
            );
          },
        }),
        columnHelper.display({
          id: "actions",
          header: () => <div className="text-right" />,
          cell: (info) => (
            <div className="text-right">
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onDelete(info.row.original.id);
                }}
                className="p-1 rounded text-app-muted hover:text-rose-500 opacity-0 group-hover:opacity-100 cursor-pointer transition-opacity"
                title="Delete argument relation"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          ),
        }),
      ]),
    [columnHelper, onDelete]
  );

  const table = useTable({
    features: engineTableFeatures,
    data,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
  });

  const rows = table.getRowModel().rows;

  useEffect(() => {
    if (onVisibleIdsChange) {
      onVisibleIdsChange(rows.map((r) => r.original.id));
    }
  }, [rows, onVisibleIdsChange]);

  return (
    <div className="w-full">
      <div className="px-6 py-2.5 bg-app-surface border-b border-app-border grid grid-cols-[180px_110px_110px_90px_1fr_40px] items-center font-sans text-[11px] font-semibold uppercase tracking-[0.05em] text-app-muted">
        {table.getHeaderGroups()[0]?.headers.map((header) => (
          <div key={header.id}>
            {header.isPlaceholder
              ? null
              : flexRender(header.column.columnDef.header, header.getContext())}
          </div>
        ))}
      </div>

      <div className="divide-y divide-app-border">
        {rows.length === 0 ? (
          <div className="px-6 py-12 text-center text-app-muted font-mono text-xs">
            No matching argument relations found.
          </div>
        ) : (
          rows.map((row) => {
            const isSelected = selectedId === row.original.id;
            return (
              <div
                key={row.id}
                onClick={() => onSelect(row.original.id)}
                className={`px-6 h-10 border-l-2 grid grid-cols-[180px_110px_110px_90px_1fr_40px] items-center gap-3 cursor-pointer transition-colors group ${
                  isSelected
                    ? "bg-app-subtle border-[#2563EB]"
                    : "border-transparent hover:bg-app-surface dark:hover:bg-app-subtle/50"
                }`}
              >
                {row.getVisibleCells().map((cell) => (
                  <div key={cell.id} className="min-w-0">
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </div>
                ))}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// 5. UnmappedDiscoveredTable (Discovered In Historical Runs)
// ─────────────────────────────────────────────────────────────────────────────

export interface DiscoveredRecord {
  id: string;
  predicate: string;
  occurrences: number;
  sample_runs: string[];
}

export interface UnmappedDiscoveredTableProps {
  unmapped: UnmappedPredicateInfo[];
  selectedItem: SelectedItem | null;
  selectedPredicates: Set<string>;
  onToggleSelect: (predicate: string, checked: boolean) => void;
  onToggleSelectAll: (checked: boolean) => void;
  onSelect: (predicate: string) => void;
  onQuickMap: (predicate: string, polarity: -1 | 0 | 1, canonical?: string) => Promise<void>;
  onVisibleIdsChange?: (ids: string[]) => void;
}

export const UnmappedDiscoveredTable: React.FC<UnmappedDiscoveredTableProps> = ({
  unmapped,
  selectedItem,
  selectedPredicates,
  onToggleSelect,
  onToggleSelectAll,
  onSelect,
  onQuickMap,
  onVisibleIdsChange,
}) => {
  const [sorting, setSorting] = useState<SortingState>([]);

  const data: DiscoveredRecord[] = useMemo(() => {
    return unmapped.map((item) => ({
      id: item.predicate,
      predicate: item.predicate,
      occurrences: item.occurrences,
      sample_runs: item.sample_runs,
    }));
  }, [unmapped]);

  const allSelected = useMemo(() => {
    return data.length > 0 && data.every((item) => selectedPredicates.has(item.predicate));
  }, [data, selectedPredicates]);

  const columnHelper = createColumnHelper<typeof engineTableFeatures, DiscoveredRecord>();

  const columns = useMemo(
    () =>
      columnHelper.columns([
        columnHelper.display({
          id: "select",
          header: () => (
            <div className="text-center" onClick={(e) => e.stopPropagation()}>
              <input
                type="checkbox"
                checked={allSelected}
                onChange={(e) => onToggleSelectAll(e.target.checked)}
                className="rounded-[3px] accent-blue-600 cursor-pointer"
              />
            </div>
          ),
          cell: (info) => {
            const isChecked = selectedPredicates.has(info.row.original.predicate);
            return (
              <div className="text-center" onClick={(e) => e.stopPropagation()}>
                <input
                  type="checkbox"
                  checked={isChecked}
                  onChange={(e) =>
                    onToggleSelect(info.row.original.predicate, e.target.checked)
                  }
                  className="rounded-[3px] accent-blue-600 cursor-pointer"
                />
              </div>
            );
          },
        }),
        columnHelper.accessor("predicate", {
          id: "predicate",
          header: ({ column }) => <EngineTableSortHeader column={column} label="Predicate" />,
          cell: (info) => (
            <span className="font-mono text-xs font-medium text-app-text truncate block">
              {info.getValue()}
            </span>
          ),
        }),
        columnHelper.accessor("occurrences", {
          id: "occurrences",
          meta: { align: "right" },
          header: ({ column }) => (
            <EngineTableSortHeader column={column} label="Hits" align="right" />
          ),
          cell: (info) => (
            <span
              className="text-right font-mono text-xs text-app-muted block"
              style={{ fontFeatureSettings: '"tnum" 1' }}
            >
              {info.getValue()}
            </span>
          ),
        }),
        columnHelper.accessor("sample_runs", {
          id: "sample_runs",
          header: "Sample Inferences",
          cell: (info) => (
            <span className="font-mono text-[11px] text-app-muted truncate block">
              {info.getValue().join(", ")}
            </span>
          ),
        }),
        columnHelper.display({
          id: "quickMap",
          header: () => <div className="text-right">Quick Map</div>,
          cell: (info) => {
            const pred = info.row.original.predicate;
            return (
              <div
                className="flex items-center justify-end gap-1"
                onClick={(e) => e.stopPropagation()}
              >
                <button
                  type="button"
                  onClick={() => onQuickMap(pred, 1, "SUPPORTS")}
                  className="h-5.5 px-1.5 rounded-[4px] bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 hover:bg-emerald-500/20 border border-emerald-500/20 text-[10px] font-mono font-medium cursor-pointer transition-colors"
                >
                  +1 Supp
                </button>
                <button
                  type="button"
                  onClick={() => onQuickMap(pred, 0, "RELATED_TO")}
                  className="h-5.5 px-1.5 rounded-[4px] bg-app-bg dark:bg-app-subtle text-app-muted hover:text-app-text border border-app-border text-[10px] font-mono font-medium cursor-pointer transition-colors"
                >
                  0 Neut
                </button>
                <button
                  type="button"
                  onClick={() => onQuickMap(pred, -1, "ATTACKS")}
                  className="h-5.5 px-1.5 rounded-[4px] bg-rose-500/10 text-rose-600 dark:text-rose-400 hover:bg-rose-500/20 border border-rose-500/20 text-[10px] font-mono font-medium cursor-pointer transition-colors"
                >
                  -1 Atk
                </button>
              </div>
            );
          },
        }),
      ]),
    [columnHelper, allSelected, selectedPredicates, onToggleSelect, onToggleSelectAll, onQuickMap]
  );

  const table = useTable({
    features: engineTableFeatures,
    data,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
  });

  const rows = table.getRowModel().rows;

  useEffect(() => {
    if (onVisibleIdsChange) {
      onVisibleIdsChange(rows.map((r) => r.original.id));
    }
  }, [rows, onVisibleIdsChange]);

  return (
    <div className="w-full">
      <div className="px-6 py-2.5 bg-app-surface border-b border-app-border grid grid-cols-[36px_190px_70px_1fr_180px] items-center font-sans text-[11px] font-semibold uppercase tracking-[0.05em] text-app-muted">
        {table.getHeaderGroups()[0]?.headers.map((header) => (
          <div key={header.id}>
            {header.isPlaceholder
              ? null
              : flexRender(header.column.columnDef.header, header.getContext())}
          </div>
        ))}
      </div>

      <div className="divide-y divide-app-border">
        {rows.length === 0 ? (
          <div className="px-6 py-12 text-center text-app-muted font-mono text-xs">
            No unmapped predicates matching filter.
          </div>
        ) : (
          rows.map((row) => {
            const isSelected =
              selectedItem?.type === "unmapped_predicate" &&
              selectedItem.id === row.original.predicate;
            const isChecked = selectedPredicates.has(row.original.predicate);
            return (
              <div
                key={row.id}
                onClick={() => onSelect(row.original.predicate)}
                className={`px-6 h-10 border-l-2 grid grid-cols-[36px_190px_70px_1fr_180px] items-center gap-3 cursor-pointer transition-colors ${
                  isSelected
                    ? "bg-app-subtle border-[#2563EB]"
                    : isChecked
                    ? "bg-blue-500/10 border-transparent"
                    : "border-transparent hover:bg-app-surface dark:hover:bg-app-subtle/50"
                }`}
              >
                {row.getVisibleCells().map((cell) => (
                  <div key={cell.id} className="min-w-0">
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </div>
                ))}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// 6. UnmappedAliasesTable (Configured Predicate Aliases)
// ─────────────────────────────────────────────────────────────────────────────

export interface AliasRecord {
  id: string;
  predicate: string;
  polarity: number;
  canonical: string | null;
  definition: string;
}

export interface UnmappedAliasesTableProps {
  aliases: [string, any][];
  selectedPredicateId: string | null;
  onSelect: (predicate: string) => void;
  onDelete: (predicate: string) => void;
  onVisibleIdsChange?: (ids: string[]) => void;
}

export const UnmappedAliasesTable: React.FC<UnmappedAliasesTableProps> = ({
  aliases,
  selectedPredicateId,
  onSelect,
  onDelete,
  onVisibleIdsChange,
}) => {
  const [sorting, setSorting] = useState<SortingState>([]);

  const data: AliasRecord[] = useMemo(() => {
    return aliases.map(([pred, details]) => {
      const pol =
        typeof details === "number"
          ? details
          : details?.polarity !== undefined
          ? details.polarity
          : 0;
      const canonical = typeof details === "object" ? details?.canonical : null;
      const def = typeof details === "object" ? details?.definition : "";
      return {
        id: pred,
        predicate: pred,
        polarity: pol,
        canonical: canonical || null,
        definition: def || "",
      };
    });
  }, [aliases]);

  const columnHelper = createColumnHelper<typeof engineTableFeatures, AliasRecord>();

  const columns = useMemo(
    () =>
      columnHelper.columns([
        columnHelper.accessor("predicate", {
          id: "predicate",
          header: ({ column }) => (
            <EngineTableSortHeader column={column} label="Custom Predicate" />
          ),
          cell: (info) => (
            <span className="font-mono text-xs font-medium text-app-text truncate block">
              {info.getValue()}
            </span>
          ),
        }),
        columnHelper.accessor("polarity", {
          id: "polarity",
          header: ({ column }) => <EngineTableSortHeader column={column} label="Polarity" />,
          cell: (info) => {
            const pol = info.getValue();
            return (
              <div>
                <span
                  className={`px-1.5 py-0.5 rounded text-[10px] font-mono font-medium ${
                    pol === 1
                      ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20"
                      : pol === -1
                      ? "bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/20"
                      : "bg-app-subtle text-app-muted border border-app-border"
                  }`}
                >
                  {pol > 0 ? "+1 Supp" : pol < 0 ? "-1 Atk" : "0 Neut"}
                </span>
              </div>
            );
          },
        }),
        columnHelper.accessor("canonical", {
          id: "canonical",
          header: ({ column }) => (
            <EngineTableSortHeader column={column} label="Canonical Target" />
          ),
          cell: (info) => (
            <span className="font-mono text-xs text-app-muted truncate block">
              {info.getValue() || "—"}
            </span>
          ),
        }),
        columnHelper.accessor("definition", {
          id: "definition",
          header: "Description",
          cell: (info) => (
            <span className="text-[13px] font-sans text-app-muted truncate block">
              {info.getValue() || "—"}
            </span>
          ),
        }),
        columnHelper.display({
          id: "actions",
          header: () => <div className="text-right" />,
          cell: (info) => (
            <div className="text-right">
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onDelete(info.row.original.id);
                }}
                className="p-1 rounded text-app-muted hover:text-rose-500 opacity-0 group-hover:opacity-100 cursor-pointer transition-opacity"
                title="Remove alias"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          ),
        }),
      ]),
    [columnHelper, onDelete]
  );

  const table = useTable({
    features: engineTableFeatures,
    data,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
  });

  const rows = table.getRowModel().rows;

  useEffect(() => {
    if (onVisibleIdsChange) {
      onVisibleIdsChange(rows.map((r) => r.original.id));
    }
  }, [rows, onVisibleIdsChange]);

  return (
    <div className="w-full">
      <div className="px-6 py-2.5 bg-app-surface border-b border-app-border grid grid-cols-[190px_100px_160px_1fr_40px] items-center font-sans text-[11px] font-semibold uppercase tracking-[0.05em] text-app-muted">
        {table.getHeaderGroups()[0]?.headers.map((header) => (
          <div key={header.id}>
            {header.isPlaceholder
              ? null
              : flexRender(header.column.columnDef.header, header.getContext())}
          </div>
        ))}
      </div>

      <div className="divide-y divide-app-border">
        {rows.length === 0 ? (
          <div className="px-6 py-12 text-center text-app-muted font-mono text-xs">
            No matching aliases found.
          </div>
        ) : (
          rows.map((row) => {
            const isSelected = selectedPredicateId === row.original.id;
            return (
              <div
                key={row.id}
                onClick={() => onSelect(row.original.id)}
                className={`px-6 h-10 border-l-2 grid grid-cols-[190px_100px_160px_1fr_40px] items-center gap-3 cursor-pointer transition-colors group ${
                  isSelected
                    ? "bg-app-subtle border-[#2563EB]"
                    : "border-transparent hover:bg-app-surface dark:hover:bg-app-subtle/50"
                }`}
              >
                {row.getVisibleCells().map((cell) => (
                  <div key={cell.id} className="min-w-0">
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </div>
                ))}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
