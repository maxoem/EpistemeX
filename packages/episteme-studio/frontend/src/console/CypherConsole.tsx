import React, {useEffect, useMemo, useRef, useState} from "react";
import {CypherEditor} from "@neo4j-cypher/react-codemirror";
import {AlertTriangle, ChevronDown, Database, Loader2, Play} from "lucide-react";
import {api} from "../api/client";
import {CypherResult} from "../api/types";
import {useRunsStore} from "../store/runsStore";
import {useThemeStore} from "../store/themeStore";

interface CypherConsoleProps {
  neo4jAvailable: boolean;
}

const SAMPLE_QUERIES = [
  {
    name: "Entities (L2)",
    query: "MATCH (n:Entity) RETURN coalesce(n.name, n.label, n.id) AS name, labels(n) AS labels LIMIT 25",
  },
  {
    name: "Entity Relationships",
    query: "MATCH (s:Entity)-[r]->(t:Entity) RETURN coalesce(s.name, s.label) AS source, type(r) AS rel, coalesce(t.name, t.label) AS target LIMIT 50",
  },
  {
    name: "Theory Atoms (L3)",
    query: "MATCH (n:TheoryAtom) RETURN n.text AS text, n.component_type AS type, n.confidence AS confidence LIMIT 25",
  },
  {
    name: "Chunks & Documents (L1)",
    query: "MATCH (c:Chunk) RETURN c.id AS chunk_id, c.chunk_index AS index, c.document_id AS doc LIMIT 25",
  },
];

const isNumericValue = (val: any): boolean => typeof val === "number";

export const CypherConsole: React.FC<CypherConsoleProps> = ({ neo4jAvailable }) => {
  const { fetchCapabilities } = useRunsStore();
  const { theme } = useThemeStore();
  const [query, setQuery] = useState(SAMPLE_QUERIES[0].query);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<CypherResult | null>(null);
  const [error, setError] = useState<any | null>(null);
  const [history, setHistory] = useState<string[]>([]);
  const [showSamples, setShowSamples] = useState(false);

  // Dynamic connection form state
  const [connectUrl, setConnectUrl] = useState("bolt://localhost:7687");
  const [connectUser, setConnectUser] = useState("neo4j");
  const [connectPassword, setConnectPassword] = useState("");
  const [connectDatabase, setConnectDatabase] = useState("neo4j");
  const [isConnecting, setIsConnecting] = useState(false);
  const [connectError, setConnectError] = useState<string | null>(null);

  // Resizable split section state (Editor / Connect Form height)
  // Default to 380px when offline so the connect form is fully visible without clipping
  const [editorHeight, setEditorHeight] = useState<number>(() => (neo4jAvailable ? 200 : 380));
  const [isDragging, setIsDragging] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const prevNeo4jAvailable = useRef(neo4jAvailable);

  // Characterize columns that hold numeric values so they render right-aligned in monospace
  const numericCols = useMemo(() => {
    if (!result) return new Set<string>();
    const cols = new Set<string>();
    for (const col of result.columns) {
      const sample = result.rows.slice(0, 10);
      if (sample.length > 0 && sample.every((row) => isNumericValue(row[col]))) {
        cols.add(col);
      }
    }
    return cols;
  }, [result]);

  // Adjust default height when transitioning from offline to online
  useEffect(() => {
    if (!prevNeo4jAvailable.current && neo4jAvailable) {
      setEditorHeight(200);
    } else if (prevNeo4jAvailable.current && !neo4jAvailable) {
      setEditorHeight(380);
    }
    prevNeo4jAvailable.current = neo4jAvailable;
  }, [neo4jAvailable]);

  const handleMouseDown = (e: React.MouseEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  useEffect(() => {
    if (!isDragging) return;

    const handleMouseMove = (e: MouseEvent) => {
      if (!containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      const newHeight = e.clientY - rect.top - 46; // account for console header
      const minHeight = 130;
      const maxHeight = Math.max(minHeight, rect.height - 100);
      if (newHeight >= minHeight && newHeight <= maxHeight) {
        setEditorHeight(newHeight);
      }
    };

    const handleMouseUp = () => {
      setIsDragging(false);
    };

    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);
    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };
  }, [isDragging]);

  const handleConnect = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsConnecting(true);
    setConnectError(null);
    try {
      await api.connectNeo4j({
        url: connectUrl,
        user: connectUser || undefined,
        password: connectPassword || undefined,
        database: connectDatabase || undefined,
      });
      await fetchCapabilities();
      setIsConnecting(false);
    } catch (err: any) {
      setConnectError(err.detail || err.title || "Failed to establish connection to Neo4j.");
      setIsConnecting(false);
    }
  };

  const handleRun = async (cmdToRun?: string) => {
    if (!neo4jAvailable || running) return;
    const activeQuery = cmdToRun || query;
    if (!activeQuery.trim()) return;

    setRunning(true);
    setError(null);

    try {
      const res = await api.executeCypher(activeQuery);
      setResult(res);
      setHistory((prev) => [activeQuery, ...prev.filter((q) => q !== activeQuery)].slice(0, 30));
    } catch (err: any) {
      setError(err);
      setResult(null);
    } finally {
      setRunning(false);
    }
  };

  const renderCellValue = (val: any) => {
    if (val === null || val === undefined) {
      return <span className="text-app-muted italic">null</span>;
    }
    if (typeof val === "boolean") {
      return (
        <span className={val ? "text-emerald-600 dark:text-emerald-400" : "text-app-muted"}>
          {val.toString()}
        </span>
      );
    }
    if (typeof val === "number") {
      return <span className="text-app-heading tabular-nums">{val}</span>;
    }
    if (typeof val === "object") {
      return (
        <span className="font-mono text-xs text-app-muted bg-app-subtle px-1.5 py-0.5 rounded-[4px]">
          {JSON.stringify(val)}
        </span>
      );
    }
    return <span>{String(val)}</span>;
  };

  return (
    <div
      ref={containerRef}
      className={`flex flex-col h-full bg-app-bg border border-app-border overflow-hidden relative text-app-text select-none ${
        isDragging ? "cursor-row-resize" : ""
      }`}
    >
      {/* Top Header & Toolbar */}
      <div className="flex items-center justify-between px-4 h-11 bg-app-surface border-b border-app-border shrink-0">
        <div className="flex items-center gap-3 min-w-0">
          <span className="text-blue-600 dark:text-blue-400">
            <Database className="w-4 h-4" />
          </span>
          <span className="text-[13px] font-semibold text-app-heading whitespace-nowrap">Cypher Console</span>
          <span className="font-mono text-[10px] uppercase tracking-wider text-app-muted border border-app-border px-1.5 py-0.5 rounded-[4px] whitespace-nowrap">
            Read-only session
          </span>
          <span className="flex items-center gap-1.5 text-[11px] whitespace-nowrap">
            <span
              className={`h-1.5 w-1.5 rounded-full ${
                neo4jAvailable ? "bg-emerald-500" : "bg-app-muted/60"
              }`}
            />
            <span
              className={neo4jAvailable ? "text-emerald-600 dark:text-emerald-400 font-medium" : "text-app-muted"}
            >
              {neo4jAvailable ? "Connected" : "Disconnected"}
            </span>
          </span>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {/* Sample Queries Dropdown */}
          <div className="relative">
            <button
              onClick={() => setShowSamples(!showSamples)}
              className="h-8 px-2.5 text-xs text-app-text bg-app-subtle hover:bg-app-hover rounded-[4px] border border-app-border flex items-center gap-1.5 transition-colors cursor-pointer"
            >
              <span>Sample Queries</span>
              <ChevronDown className="w-3.5 h-3.5 text-app-muted" />
            </button>

            {showSamples && (
              <div className="absolute right-0 top-full mt-1.5 w-72 bg-app-surface border border-app-border rounded-[4px] shadow-xl z-20 py-1">
                {SAMPLE_QUERIES.map((sample, idx) => (
                  <button
                    key={idx}
                    onClick={() => {
                      setQuery(sample.query);
                      setShowSamples(false);
                    }}
                    className="w-full text-left px-3 py-2 text-xs hover:bg-app-subtle flex flex-col gap-0.5 border-b border-app-border-subtle last:border-b-0 cursor-pointer"
                  >
                    <span className="font-medium text-app-heading">{sample.name}</span>
                    <span className="font-mono text-[11px] text-app-muted truncate">{sample.query}</span>
                  </button>
                ))}
              </div>
            )}
          </div>

          <button
            onClick={() => handleRun()}
            disabled={!neo4jAvailable || running}
            className={`h-8 px-3 text-xs font-medium rounded-[4px] flex items-center gap-1.5 transition-colors cursor-pointer ${
              !neo4jAvailable
                ? "bg-app-subtle text-app-muted cursor-not-allowed border border-app-border"
                : running
                ? "bg-app-subtle text-app-muted cursor-wait border border-app-border"
                : "bg-blue-600 hover:bg-blue-500 text-white"
            }`}
          >
            <Play className="w-3.5 h-3.5 fill-current" />
            <span>{running ? "Running..." : "Run"}</span>
            <span className="text-[10px] opacity-70 hidden sm:inline ml-1 font-mono">⌘↵</span>
          </button>
        </div>
      </div>

      {/* CodeMirror Cypher Editor (Resizable Top Section) */}
      <div
        style={{ height: `${editorHeight}px` }}
        className="border-b border-app-border bg-app-bg relative flex-shrink-0 overflow-hidden"
      >
        <CypherEditor
          value={query}
          onChange={(val: string) => setQuery(val)}
          onExecute={(cmd) => handleRun(cmd)}
          theme={theme === "light" ? "light" : "dark"}
          lineNumbers={true}
          newLineOnEnter={true}
          overrideThemeBackgroundColor={true}
          readonly={!neo4jAvailable}
        />

        {/* Offline Overlay with Interactive Connection Form (flat, divider-separated) */}
        {!neo4jAvailable && (
          <div className="absolute inset-0 bg-app-bg/95 z-10 flex flex-col overflow-y-auto">
            <div className="flex items-center gap-3 px-6 py-3 border-b border-app-border">
              <span className="text-blue-600 dark:text-blue-400 shrink-0">
                <Database className="w-4.5 h-4.5" />
              </span>
              <div className="min-w-0">
                <h4 className="text-[13px] font-semibold text-app-heading">Connect to Neo4j</h4>
                <p className="text-[11px] text-app-muted">Provide connection credentials for this session</p>
              </div>
            </div>

            <form onSubmit={handleConnect} className="px-6 py-2 flex-1 flex flex-col">
              {connectError && (
                <div className="mb-3 p-2.5 flex items-start gap-2 text-xs rounded-[4px] border border-red-500/30 bg-red-500/10 text-red-600 dark:text-red-300">
                  <AlertTriangle className="w-4 h-4 text-red-500 dark:text-red-400 shrink-0 mt-0.5" />
                  <div>{connectError}</div>
                </div>
              )}

              <FieldRow label="Bolt Connection URI" hint="bolt://host:port">
                <input
                  type="text"
                  value={connectUrl}
                  onChange={(e) => setConnectUrl(e.target.value)}
                  placeholder="bolt://localhost:7687"
                  required
                  className="h-8 w-72 max-w-full px-2.5 bg-app-bg border border-app-border rounded-[4px] text-app-heading font-mono text-xs focus:outline-none focus:border-blue-500"
                />
              </FieldRow>

              <div className="grid grid-cols-2 gap-x-6">
                <FieldRow label="Username">
                  <input
                    type="text"
                    value={connectUser}
                    onChange={(e) => setConnectUser(e.target.value)}
                    placeholder="neo4j"
                    className="h-8 w-full px-2.5 bg-app-bg border border-app-border rounded-[4px] text-app-heading font-mono text-xs focus:outline-none focus:border-blue-500"
                  />
                </FieldRow>
                <FieldRow label="Database">
                  <input
                    type="text"
                    value={connectDatabase}
                    onChange={(e) => setConnectDatabase(e.target.value)}
                    placeholder="neo4j"
                    className="h-8 w-full px-2.5 bg-app-bg border border-app-border rounded-[4px] text-app-heading font-mono text-xs focus:outline-none focus:border-blue-500"
                  />
                </FieldRow>
              </div>

              <FieldRow label="Password">
                <input
                  type="password"
                  value={connectPassword}
                  onChange={(e) => setConnectPassword(e.target.value)}
                  placeholder="Enter password"
                  className="h-8 w-72 max-w-full px-2.5 bg-app-bg border border-app-border rounded-[4px] text-app-heading font-mono text-xs focus:outline-none focus:border-blue-500"
                />
              </FieldRow>

              <div className="pt-3">
                <button
                  type="submit"
                  disabled={isConnecting}
                  className="h-8 px-4 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-medium text-xs rounded-[4px] transition-colors flex items-center gap-2 cursor-pointer"
                >
                  {isConnecting ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      Connecting to Neo4j...
                    </>
                  ) : (
                    <>
                      <Database className="w-3.5 h-3.5" />
                      Connect & Verify
                    </>
                  )}
                </button>
              </div>

              <p className="mt-4 pb-4 text-[11px] font-mono text-app-muted">
                Note: connecting activates live graph queries, k-hop expansion, and PageRank / graph algorithms in
                Graph Explorer.
              </p>
            </form>
          </div>
        )}
      </div>

      {/* Moveable Resizer Handle (Pull to increase/decrease section height) */}
      <div
        onMouseDown={handleMouseDown}
        className={`h-2 bg-app-surface border-b border-app-border hover:bg-blue-500/20 cursor-row-resize flex items-center justify-center transition-colors group shrink-0 ${
          isDragging ? "bg-blue-500/30 border-blue-500/50 h-2.5" : ""
        }`}
        title="Pull up or down to resize Cypher Editor and Results View"
      >
        <div
          className={`w-12 h-1 rounded-full bg-app-muted/40 group-hover:bg-blue-400 transition-all ${
            isDragging ? "bg-blue-500 w-16" : ""
          }`}
        />
      </div>

      {/* Query Stats & Status Bar (inline KPI strip) */}
      {result && (
        <div className="flex items-stretch border-b border-app-border bg-app-bg shrink-0">
          <div className="flex items-center gap-2 px-4 border-r border-app-border">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
            <span className="text-xs font-medium text-emerald-600 dark:text-emerald-400">Success</span>
          </div>
          <div className="px-4 py-1.5 border-r border-app-border flex flex-col justify-center">
            <span className="text-[10px] uppercase tracking-wider text-app-muted">Rows</span>
            <span className="text-sm font-bold text-app-heading font-mono leading-tight">
              {result.row_count}
            </span>
          </div>
          <div className="px-4 py-1.5 flex flex-col justify-center">
            <span className="text-[10px] uppercase tracking-wider text-app-muted">Time</span>
            <span className="text-sm font-bold text-app-heading font-mono leading-tight">
              {result.execution_time_ms}
              <span className="text-app-muted text-xs font-medium"> ms</span>
            </span>
          </div>
          {history.length > 0 && (
            <div className="ml-auto px-4 py-1.5 flex flex-col justify-center border-l border-app-border">
              <span className="text-[10px] uppercase tracking-wider text-app-muted">History</span>
              <span className="text-sm font-bold text-app-heading font-mono leading-tight text-right">
                {history.length}
              </span>
            </div>
          )}
        </div>
      )}

      {/* Error Message */}
      {error && (
        <div className="p-3 border-b border-red-500/30 bg-red-500/5 flex items-start gap-2.5 shrink-0">
          <AlertTriangle className="w-4 h-4 text-red-500 dark:text-red-400 shrink-0 mt-0.5" />
          <div className="text-xs">
            <div className="font-semibold text-red-600 dark:text-red-300">
              {error.title || error.type || "Cypher Execution Error"}
            </div>
            <div className="text-red-600/90 dark:text-red-400/90 font-mono mt-0.5">{error.detail || String(error)}</div>
          </div>
        </div>
      )}

      {/* Results Table */}
      <div className="flex-1 overflow-auto bg-app-bg">
        {result ? (
          result.rows.length === 0 ? (
            <div className="p-8 text-center text-xs font-mono text-app-muted">Query returned zero rows.</div>
          ) : (
            <table className="w-full text-left border-collapse text-xs">
              <thead className="sticky top-0 bg-app-surface border-b border-app-border">
                <tr>
                  <th className="px-3 h-8 font-mono text-[11px] uppercase tracking-wider text-app-muted font-normal text-right select-none">
                    #
                  </th>
                  {result.columns.map((col, idx) => (
                    <th
                      key={idx}
                      className={`px-3 h-8 font-mono text-[11px] uppercase tracking-wider text-app-muted font-medium ${
                        numericCols.has(col) ? "text-right" : "text-left"
                      }`}
                    >
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {result.rows.map((row, rowIdx) => (
                  <tr key={rowIdx} className="border-b border-app-border-subtle last:border-b-0 hover:bg-app-hover/40 transition-colors">
                    <td className="px-3 py-1.5 text-right font-mono text-app-muted select-none tabular-nums">{rowIdx + 1}</td>
                    {result.columns.map((col, colIdx) => (
                      <td
                        key={colIdx}
                        className={`px-3 py-1.5 font-mono max-w-sm truncate ${
                          numericCols.has(col) ? "text-right tabular-nums text-app-heading" : "text-left text-app-text"
                        }`}
                      >
                        {renderCellValue(row[col])}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          )
        ) : !error && (
          <div className="h-full flex items-center justify-center p-8 text-center text-app-muted text-xs font-mono">
            Enter a Cypher query above and press Run / ⌘↵ to execute.
          </div>
        )}
      </div>
    </div>
  );
};

interface FieldRowProps {
  label: string;
  hint?: string;
  children: React.ReactNode;
}

const FieldRow: React.FC<FieldRowProps> = ({ label, hint, children }) => (
  <label className="py-2.5 border-b border-app-border flex items-center justify-between gap-4">
    <span className="flex flex-col min-w-0">
      <span className="text-[13px] font-medium text-app-heading">{label}</span>
      {hint && <span className="text-[11px] text-app-muted">{hint}</span>}
    </span>
    <span className="shrink-0 flex-1 flex justify-end">{children}</span>
  </label>
);
