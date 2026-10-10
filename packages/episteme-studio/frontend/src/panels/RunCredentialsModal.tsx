import React, {useEffect, useMemo, useState} from "react";
import {AlertTriangle, Check, Database, Info, Loader2, Trash2, X} from "lucide-react";
import {RunNeo4jCredentials, useCredentialStore} from "../store/credentialStore";
import {api} from "../api/client";
import {useRunsStore} from "../store/runsStore";

interface RunCredentialsModalProps {
  isOpen: boolean;
  onClose: () => void;
  runId?: string | null;
  onConnected?: () => void;
}

export const RunCredentialsModal: React.FC<RunCredentialsModalProps> = ({
  isOpen,
  onClose,
  runId,
  onConnected,
}) => {
  const { getRunCredentials, saveRunCredentials, deleteRunCredentials, lastUsedCredentials, findRunsForDatabase } =
    useCredentialStore();
  const { fetchCapabilities, setActiveDataSource } = useRunsStore();

  const [url, setUrl] = useState("bolt://localhost:7687");
  const [user, setUser] = useState("neo4j");
  const [password, setPassword] = useState("");
  const [database, setDatabase] = useState("neo4j");

  const [isTesting, setIsTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);

  const effectiveRunId = runId || "default";

  const conflictingRuns = useMemo(() => {
    if (!database) return [];
    return findRunsForDatabase(database, runId);
  }, [database, runId, findRunsForDatabase]);

  // Load existing credentials for this run or populate with last-used
  useEffect(() => {
    if (!isOpen) return;
    setTestResult(null);
    const existing = runId ? getRunCredentials(runId) : getRunCredentials("default");
    if (existing) {
      setUrl(existing.url || "bolt://localhost:7687");
      setUser(existing.user || "neo4j");
      setPassword(existing.password || "");
      setDatabase(existing.database || "neo4j");
    } else if (lastUsedCredentials) {
      setUrl(lastUsedCredentials.url || "bolt://localhost:7687");
      setUser(lastUsedCredentials.user || "neo4j");
      setPassword(lastUsedCredentials.password || "");
      setDatabase(lastUsedCredentials.database || "neo4j");
    } else {
      setUrl("bolt://localhost:7687");
      setUser("neo4j");
      setPassword("");
      setDatabase("neo4j");
    }
  }, [isOpen, runId, getRunCredentials, lastUsedCredentials]);

  // Close on Escape
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const handleSaveOnly = () => {
    const payload: RunNeo4jCredentials = {
      url: url.trim(),
      user: user.trim() || undefined,
      password: password || undefined,
      database: database.trim() || undefined,
    };
    saveRunCredentials(effectiveRunId, payload);
    onClose();
  };

  const handleTestAndConnect = async () => {
    setIsTesting(true);
    setTestResult(null);

    const payload: RunNeo4jCredentials = {
      url: url.trim(),
      user: user.trim() || undefined,
      password: password || undefined,
      database: database.trim() || undefined,
    };

    try {
      await api.connectNeo4j({
        url: payload.url,
        user: payload.user,
        password: payload.password,
        database: payload.database,
      });

      // Save credentials safely in browser storage upon successful verification
      saveRunCredentials(effectiveRunId, payload);
      await fetchCapabilities();
      setActiveDataSource("neo4j");

      setTestResult({
        success: true,
        message: `Successfully connected to Neo4j (${payload.database || "default"})!`,
      });

      if (onConnected) {
        onConnected();
      }

      setTimeout(() => {
        onClose();
      }, 700);
    } catch (err: any) {
      setTestResult({
        success: false,
        message: err?.detail || err?.title || "Failed to connect to Neo4j server.",
      });
    } finally {
      setIsTesting(false);
    }
  };

  const handleDelete = () => {
    deleteRunCredentials(effectiveRunId);
    onClose();
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs select-none animate-in fade-in duration-150"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md bg-app-surface border border-app-border rounded-xl shadow-2xl overflow-hidden flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-app-border bg-app-subtle/50">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
              <Database className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-xs font-semibold text-app-heading">
                {runId ? "Run Neo4j Credentials" : "Neo4j Database Connection"}
              </h3>
              <p className="text-[10px] text-app-muted font-mono truncate max-w-[240px]">
                {runId ? `Run: ${runId}` : "Live Graph Connection"}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded text-app-muted hover:text-app-heading hover:bg-app-subtle transition-colors cursor-pointer"
            title="Close (Esc)"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Security Notice */}
        <div className="px-4 py-2 bg-emerald-500/5 border-b border-emerald-500/10 flex items-start gap-2 text-[11px] text-app-muted">
          <Info className="w-3.5 h-3.5 text-emerald-400 shrink-0 mt-0.5" />
          <span>
            Credentials are saved <strong>securely in your browser</strong> (localStorage). They are never saved to server manifests or disk.
          </span>
        </div>

        {/* Form Body */}
        <div className="p-4 space-y-3 text-xs">
          <div>
            <label className="block text-[11px] font-medium text-app-muted mb-1">
              Bolt URI / Host URL
            </label>
            <input
              type="text"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="bolt://localhost:7687"
              className="w-full px-2.5 py-1.5 rounded bg-app-bg border border-app-border text-app-heading font-mono text-xs focus:outline-none focus:border-blue-500"
            />
          </div>

          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="block text-[11px] font-medium text-app-muted mb-1">Username</label>
              <input
                type="text"
                value={user}
                onChange={(e) => setUser(e.target.value)}
                placeholder="neo4j"
                className="w-full px-2.5 py-1.5 rounded bg-app-bg border border-app-border text-app-heading font-mono text-xs focus:outline-none focus:border-blue-500"
              />
            </div>
            <div>
              <label className="block text-[11px] font-medium text-app-muted mb-1">Database</label>
              <input
                type="text"
                value={database}
                onChange={(e) => setDatabase(e.target.value)}
                placeholder="neo4j"
                className="w-full px-2.5 py-1.5 rounded bg-app-bg border border-app-border text-app-heading font-mono text-xs focus:outline-none focus:border-blue-500"
              />
            </div>
          </div>

          {conflictingRuns.length > 0 && (
            <div className="p-2.5 rounded-lg bg-amber-500/10 border border-amber-500/30 text-[11px] text-amber-400 flex items-start gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5 text-amber-400" />
              <div className="leading-tight">
                <strong>Collision Warning:</strong> Database <code className="font-mono text-amber-300">{database}</code> was already used by {conflictingRuns.length === 1 ? "run" : "runs"}{" "}
                <span className="font-mono font-medium">{conflictingRuns.slice(0, 2).join(", ")}{conflictingRuns.length > 2 ? "..." : ""}</span>.
                Writing into it may collide with existing nodes.
              </div>
            </div>
          )}

          <div>
            <label className="block text-[11px] font-medium text-app-muted mb-1">
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••••••"
              className="w-full px-2.5 py-1.5 rounded bg-app-bg border border-app-border text-app-heading font-mono text-xs focus:outline-none focus:border-blue-500"
            />
          </div>

          {/* Result Alert */}
          {testResult && (
            <div
              className={`p-2.5 rounded-lg border text-[11px] flex items-start gap-2 ${
                testResult.success
                  ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
                  : "bg-red-500/10 border-red-500/30 text-red-400"
              }`}
            >
              {testResult.success ? (
                <Check className="w-3.5 h-3.5 shrink-0 mt-0.5 text-emerald-400" />
              ) : (
                <X className="w-3.5 h-3.5 shrink-0 mt-0.5 text-red-400" />
              )}
              <span className="break-all">{testResult.message}</span>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-4 py-3 border-t border-app-border bg-app-subtle/30">
          <div>
            {getRunCredentials(effectiveRunId) && (
              <button
                type="button"
                onClick={handleDelete}
                className="flex items-center gap-1 text-[11px] text-red-400 hover:text-red-300 transition-colors cursor-pointer"
                title="Remove credentials from browser storage"
              >
                <Trash2 className="w-3 h-3" />
                <span>Forget</span>
              </button>
            )}
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleSaveOnly}
              className="px-3 py-1.5 rounded text-xs text-app-muted hover:text-app-heading border border-app-border hover:bg-app-subtle transition-colors cursor-pointer"
            >
              Save Only
            </button>
            <button
              type="button"
              onClick={handleTestAndConnect}
              disabled={isTesting}
              className="px-3 py-1.5 rounded text-xs bg-emerald-600 hover:bg-emerald-500 text-white font-medium shadow-xs transition-colors cursor-pointer flex items-center gap-1.5"
            >
              {isTesting ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>Testing...</span>
                </>
              ) : (
                <>
                  <Database className="w-3.5 h-3.5" />
                  <span>Connect & Switch</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
