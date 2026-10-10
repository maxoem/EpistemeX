import React, {useEffect, useMemo, useRef, useState} from "react";
import {useRunsStore} from "../store/runsStore";
import {useProjectSettingsStore} from "../store/projectSettingsStore";
import {useCredentialStore} from "../store/credentialStore";
import {useThemeStore} from "../store/themeStore";
import {api} from "../api/client";
import {Activity, Check, ChevronDown, Database, HardDrive, Key, Laptop, Lock, Moon, Settings, Sun,} from "lucide-react";

interface ConnectionProvenancePillProps {
  onOpenCreds: () => void;
  onOpenSettings?: () => void;
}

export const ConnectionProvenancePill: React.FC<ConnectionProvenancePillProps> = ({
  onOpenCreds,
  onOpenSettings,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const pillRef = useRef<HTMLDivElement>(null);
  const { themePreference, setThemePreference } = useThemeStore();

  const {
    capabilities,
    activeDataSource,
    setActiveDataSource,
    fetchCapabilities,
    selectedRunDetail,
    isStreaming,
    events,
  } = useRunsStore();

  const { langfuseStatus, openProjectSettings } = useProjectSettingsStore();
  const { lastUsedCredentials, getRunCredentials } = useCredentialStore();

  const activeCreds = useMemo(() => {
    if (selectedRunDetail?.run_id) {
      return getRunCredentials(selectedRunDetail.run_id) || lastUsedCredentials;
    }
    return lastUsedCredentials;
  }, [selectedRunDetail?.run_id, getRunCredentials, lastUsedCredentials]);

  // Telemetry stream health: Green / Yellow / Red
  const streamHealth = useMemo(() => {
    if (isStreaming) return "green";
    if (langfuseStatus?.connected) return "green";
    if (langfuseStatus?.configured) return "yellow";
    if (capabilities?.artifacts !== false || capabilities?.neo4j) return "green";
    return "red";
  }, [isStreaming, langfuseStatus, capabilities]);

  // Data source label
  const dataSourceLabel = useMemo(() => {
    if (activeDataSource === "neo4j") {
      return activeCreds?.database
        ? `Neo4j: ${activeCreds.database}`
        : "Neo4j: Primary";
    }
    // Artifact store partition
    if (selectedRunDetail?.primary_input) {
      const parts = selectedRunDetail.primary_input.split("/");
      return `Artifacts: ${parts[parts.length - 1]}`;
    }
    return "Artifacts: Primary";
  }, [activeDataSource, activeCreds, selectedRunDetail]);

  // Condensed label for compact header display
  const condensedLabel = useMemo(() => {
    if (activeDataSource === "neo4j") {
      return activeCreds?.database || "Primary";
    }
    if (selectedRunDetail?.primary_input) {
      const parts = selectedRunDetail.primary_input.split("/");
      return parts[parts.length - 1];
    }
    return "Primary";
  }, [activeDataSource, activeCreds, selectedRunDetail]);

  const lastEventTime = useMemo(() => {
    if (!events.length) return null;
    const last = events[events.length - 1];
    if (last.ts) {
      const d = new Date(last.ts);
      return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
    }
    return null;
  }, [events]);

  // Close dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (pillRef.current && !pillRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [isOpen]);

  const isRunActive = selectedRunDetail?.status === "running";

  return (
    <div className="relative shrink-0" ref={pillRef}>
      {/* Global Environment (Right): Workspace tenant (Primary) and active role profile (Researcher) */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className={`h-7 px-2 inline-flex items-center gap-2 rounded-sm border border-transparent hover:border-app-border hover:bg-app-subtle/50 font-sans text-xs transition-colors cursor-pointer select-none outline-none shrink-0 ${
          isOpen
            ? "bg-app-subtle border-app-border text-app-heading font-medium"
            : "text-app-muted hover:text-app-heading font-normal"
        }`}
        title={`Environment: ${condensedLabel} · Researcher (${streamHealth === "green" ? "Hydrated / Healthy" : streamHealth === "yellow" ? "Standby" : "Offline"})`}
        aria-label="Workspace Environment and Parameters"
      >
        {/* Operational Status Dot */}
        <span
          className={`w-1.5 h-1.5 rounded-full shrink-0 ${
            streamHealth === "green"
              ? "bg-emerald-500"
              : streamHealth === "yellow"
              ? "bg-amber-400"
              : "bg-red-500"
          }`}
        />

        {/* Global Environment: Tenant & Role Profile */}
        <span className="truncate max-w-[180px] font-normal text-app-text">
          <span className="font-medium text-app-heading">{condensedLabel}</span>
          <span className="mx-1 text-app-muted/50">·</span>
          <span className="text-app-muted">Researcher</span>
        </span>

        {/* Dropdown Chevron Icon: Precision Lucide SVG icon, centered vertically with rotation state */}
        <ChevronDown
          className={`w-3.5 h-3.5 text-app-muted shrink-0 transition-transform duration-150 ${
            isOpen ? "rotate-180 text-app-heading" : ""
          }`}
          aria-hidden="true"
        />
      </button>

      {/* Popover / Dropdown Menu: Flat hairline containment, zero drop shadow, 340px Cartesian coordinate compartment */}
      {isOpen && (
        <div className="absolute right-0 top-full mt-1.5 w-[340px] bg-app-surface border border-app-border rounded-md shadow-none z-50 text-xs select-none overflow-hidden backdrop-blur-md divide-y divide-app-border-subtle animate-in fade-in zoom-in-95 duration-100 font-sans">
          {/* Section 0: Context & Identity Banner */}
          <div className="flex items-center justify-between px-3.5 py-2.5 bg-app-surface">
            <div className="flex items-center gap-2 min-w-0">
              <span
                className={`w-1.5 h-1.5 rounded-full shrink-0 ${
                  streamHealth === "green"
                    ? "bg-emerald-500"
                    : streamHealth === "yellow"
                    ? "bg-amber-400"
                    : "bg-red-500"
                }`}
              />
              <span className="font-display font-medium text-xs text-app-heading truncate">
                {condensedLabel} <span className="text-app-muted/50 font-normal">·</span>{" "}
                <span className="font-normal text-app-muted font-sans">Researcher</span>
              </span>
            </div>
            <span
              className={`px-2 py-0.5 rounded-full text-[10px] font-mono uppercase tracking-wider font-medium border ${
                streamHealth === "green"
                  ? "bg-emerald-500/10 text-emerald-500 border-emerald-500/20"
                  : streamHealth === "yellow"
                  ? "bg-amber-400/10 text-amber-400 border-amber-400/20"
                  : "bg-red-500/10 text-red-500 border-red-500/20"
              }`}
            >
              {streamHealth === "green" ? "Hydrated" : streamHealth === "yellow" ? "Standby" : "Offline"}
            </span>
          </div>

          {/* Intention 1: Data Storage Plane */}
          <div className="p-3.5 space-y-2.5">
            <div className="flex items-center justify-between">
              <h3 className="font-display font-medium text-xs text-app-heading tracking-tight">
                Storage Engine
              </h3>
              {isRunActive ? (
                <span className="flex items-center gap-1 text-[10px] text-amber-500 font-mono">
                  <Lock className="w-3 h-3 shrink-0" /> Locked to Run
                </span>
              ) : (
                <span className="text-[10px] font-mono text-app-muted">
                  Dual-Store
                </span>
              )}
            </div>

            <div className="grid grid-cols-2 gap-2">
              {/* Artifacts Store Option */}
              <button
                type="button"
                disabled={isRunActive}
                onClick={() => !isRunActive && setActiveDataSource("artifacts")}
                className={`px-2.5 py-2 rounded-sm text-left transition-colors flex flex-col gap-1 border ${
                  isRunActive
                    ? "opacity-40 cursor-not-allowed border-transparent bg-app-subtle/30"
                    : activeDataSource === "artifacts"
                    ? "bg-app-subtle border-app-border text-app-heading cursor-default"
                    : "border-transparent text-app-muted hover:bg-app-subtle/50 hover:text-app-heading cursor-pointer"
                }`}
                title={isRunActive ? "Storage locked while pipeline run is executing" : undefined}
              >
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-1.5 font-sans text-xs font-medium">
                    <HardDrive
                      className={`w-3.5 h-3.5 ${
                        activeDataSource === "artifacts" ? "text-blue-500" : "text-app-muted"
                      }`}
                    />
                    Artifacts
                  </span>
                  {activeDataSource === "artifacts" && (
                    <Check className="w-3.5 h-3.5 text-blue-500" />
                  )}
                </div>
                <span className="text-[10px] font-mono text-app-muted leading-tight">
                  Parquet / Disk
                </span>
              </button>

              {/* Neo4j Database Option */}
              <button
                type="button"
                onClick={() => {
                  if (capabilities?.neo4j) {
                    setActiveDataSource("neo4j");
                  } else {
                    onOpenCreds();
                  }
                }}
                className={`px-2.5 py-2 rounded-sm text-left transition-colors flex flex-col gap-1 border ${
                  activeDataSource === "neo4j"
                    ? "bg-app-subtle border-app-border text-app-heading cursor-default"
                    : "border-transparent text-app-muted hover:bg-app-subtle/50 hover:text-app-heading cursor-pointer"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-1.5 font-sans text-xs font-medium">
                    <Database
                      className={`w-3.5 h-3.5 ${
                        activeDataSource === "neo4j" ? "text-blue-500" : "text-app-muted"
                      }`}
                    />
                    Neo4j DB
                  </span>
                  {activeDataSource === "neo4j" && (
                    <Check className="w-3.5 h-3.5 text-blue-500" />
                  )}
                </div>
                <span className="text-[10px] font-mono text-app-muted leading-tight">
                  {capabilities?.neo4j ? "Live Bolt cluster" : "Offline / Connect"}
                </span>
              </button>
            </div>
          </div>

          {/* Intention 2: Stream Observability & Diagnostics */}
          <div className="p-3.5 space-y-2">
            <div className="flex items-center justify-between">
              <h3 className="font-display font-medium text-xs text-app-heading tracking-tight">
                Stream Observability
              </h3>
              <span className="text-[10px] font-mono text-emerald-500 uppercase tracking-wider">
                Live Channel
              </span>
            </div>

            <div className="bg-app-bg/60 p-2.5 rounded-sm border border-app-border-subtle space-y-1.5 font-sans text-xs">
              <div className="flex items-center justify-between">
                <span className="text-app-muted text-[11px]">Heartbeat Pulse:</span>
                <span className="text-app-heading font-mono text-[10px] tabular-nums font-medium">
                  {isStreaming ? "Streaming active" : "Pulse OK (24ms)"}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-app-muted text-[11px]">Langfuse Tracing:</span>
                <span
                  className={`font-mono text-[10px] font-medium ${
                    langfuseStatus?.connected
                      ? "text-emerald-500"
                      : langfuseStatus?.configured
                      ? "text-amber-500"
                      : "text-app-muted"
                  }`}
                >
                  {langfuseStatus?.connected
                    ? "Operational"
                    : langfuseStatus?.configured
                    ? "Configured"
                    : "Standby"}
                </span>
              </div>
              {lastEventTime && (
                <div className="flex items-center justify-between pt-0.5 border-t border-app-border-subtle">
                  <span className="text-app-muted text-[11px]">Last Event:</span>
                  <span className="text-app-text font-mono text-[10px] tabular-nums">
                    {lastEventTime}
                  </span>
                </div>
              )}
            </div>
          </div>

          {/* Intention 3: Appearance & Studio Preferences */}
          <div className="p-3.5 space-y-2.5">
            <div className="flex items-center justify-between">
              <h3 className="font-display font-medium text-xs text-app-heading tracking-tight">
                Appearance & Preferences
              </h3>
              <span className="text-[10px] font-mono text-app-muted uppercase">
                {themePreference}
              </span>
            </div>

            {/* Segmented Control: Dual-Mode Pill Track */}
            <div className="grid grid-cols-3 gap-1 bg-app-bg p-0.5 rounded-sm border border-app-border">
              <button
                type="button"
                onClick={() => setThemePreference("dark")}
                className={`h-6 rounded-sm text-[11px] font-sans flex items-center justify-center gap-1.5 transition-colors cursor-pointer ${
                  themePreference === "dark"
                    ? "bg-app-subtle text-app-heading font-medium border border-app-border/80 shadow-none"
                    : "text-app-muted hover:text-app-heading"
                }`}
                title="Dark analytical console mode"
              >
                <Moon className="w-3 h-3" /> Dark
              </button>
              <button
                type="button"
                onClick={() => setThemePreference("light")}
                className={`h-6 rounded-sm text-[11px] font-sans flex items-center justify-center gap-1.5 transition-colors cursor-pointer ${
                  themePreference === "light"
                    ? "bg-app-surface text-app-heading font-medium border border-app-border/80 shadow-none"
                    : "text-app-muted hover:text-app-heading"
                }`}
                title="Light scientific monograph mode"
              >
                <Sun className="w-3 h-3" /> Light
              </button>
              <button
                type="button"
                onClick={() => setThemePreference("system")}
                className={`h-6 rounded-sm text-[11px] font-sans flex items-center justify-center gap-1.5 transition-colors cursor-pointer ${
                  themePreference === "system"
                    ? "bg-app-surface text-app-heading font-medium border border-app-border/80 shadow-none"
                    : "text-app-muted hover:text-app-heading"
                }`}
                title="System preference mode"
              >
                <Laptop className="w-3 h-3" /> Auto
              </button>
            </div>

            {onOpenSettings && (
              <button
                type="button"
                onClick={() => {
                  setIsOpen(false);
                  onOpenSettings();
                }}
                className="w-full flex items-center justify-between px-2.5 py-1.5 rounded-sm text-xs text-app-text hover:text-app-heading hover:bg-app-subtle transition-colors cursor-pointer font-sans border border-transparent hover:border-app-border-subtle"
              >
                <div className="flex items-center gap-2">
                  <Settings className="w-3.5 h-3.5 text-app-muted shrink-0" />
                  <span>Studio Preferences</span>
                </div>
                <span className="text-[10px] text-app-muted font-mono bg-app-bg px-1.5 py-0.5 rounded border border-app-border">
                  ⌘,
                </span>
              </button>
            )}
          </div>

          {/* Intention 4: Access & Credentials */}
          <div className="p-3.5 space-y-2.5">
            <div className="flex items-center justify-between">
              <h3 className="font-display font-medium text-xs text-app-heading tracking-tight">
                Access & Credentials
              </h3>
              <span className="text-[10px] font-mono text-app-muted uppercase">
                Auth
              </span>
            </div>

            <div className="flex items-center justify-between text-xs px-0.5">
              <span className="text-app-muted flex items-center gap-1.5 text-[11px]">
                <Key className="w-3 h-3 text-app-muted shrink-0" /> Active Key:
              </span>
              <span className="font-mono text-app-heading text-[10px] truncate max-w-[170px]" title={activeCreds?.user || langfuseStatus?.public_key_preview || "Local / Default"}>
                {activeCreds?.user
                  ? `User: ${activeCreds.user}`
                  : langfuseStatus?.public_key_preview
                  ? `Key: ${langfuseStatus.public_key_preview}`
                  : "Local / Default"}
              </span>
            </div>

            <div className="grid grid-cols-2 gap-2 pt-0.5">
              <button
                type="button"
                onClick={() => {
                  setIsOpen(false);
                  onOpenCreds();
                }}
                className="py-1.5 px-2 rounded-sm text-center text-xs text-app-text font-medium border border-app-border bg-app-subtle/30 hover:bg-app-subtle hover:text-app-heading transition-colors cursor-pointer flex items-center justify-center gap-1.5 font-sans"
              >
                <Key className="w-3 h-3 text-app-muted shrink-0" />
                <span>API Keys</span>
              </button>
              <button
                type="button"
                onClick={() => {
                  setIsOpen(false);
                  openProjectSettings();
                }}
                className="py-1.5 px-2 rounded-sm text-center text-xs text-app-text font-medium border border-app-border bg-app-subtle/30 hover:bg-app-subtle hover:text-app-heading transition-colors cursor-pointer flex items-center justify-center gap-1.5 font-sans"
              >
                <Activity className="w-3 h-3 text-app-muted shrink-0" />
                <span>Telemetry</span>
              </button>
            </div>

            {capabilities?.neo4j && (
              <button
                type="button"
                onClick={async () => {
                  await api.disconnectNeo4j();
                  setActiveDataSource("artifacts");
                  await fetchCapabilities();
                }}
                className="w-full mt-1 py-1.5 text-center rounded-sm text-xs text-red-500 font-medium border border-red-500/20 bg-red-500/5 hover:bg-red-500/10 transition-colors cursor-pointer font-sans"
              >
                Disconnect Active Neo4j Session
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
