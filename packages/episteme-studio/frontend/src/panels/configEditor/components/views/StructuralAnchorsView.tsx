import React, {useState} from "react";
import {
    BookOpen,
    Check,
    Compass,
    FileText,
    Loader2,
    Plus,
    RotateCcw,
    Sparkles,
    Tag,
    Trash2,
    Upload,
    X,
} from "lucide-react";
import {AvailableInputDoc, GlobalStructuralAnchor} from "../../../../api/types";
import {RunMetadataItem} from "../../types";

interface StructuralAnchorsViewProps {
  // Effective data
  effectiveSourcePaths: string[];
  effectiveMetadata: Record<string, string>;
  effectiveAnchor: GlobalStructuralAnchor | null;
  anchorPromptContextPreview: string;

  // Document & Bib sources state & callbacks
  executionMode: "single" | "corpus";
  selectedInputPath: string;
  setSelectedInputPath: (path: string) => void;
  multiSourcePaths: string[];
  setMultiSourcePaths: React.Dispatch<React.SetStateAction<string[]>>;
  availableInputs: AvailableInputDoc[];
  availableBibDocs: AvailableInputDoc[];
  selectedBibPaths: string[];
  setSelectedBibPaths: React.Dispatch<React.SetStateAction<string[]>>;

  // Upload handlers
  handleFileUpload: (e: React.ChangeEvent<HTMLInputElement>) => Promise<void>;
  isUploadingFile: boolean;
  uploadSuccessMessage: string | null;
  fileInputRef: React.RefObject<HTMLInputElement>;

  handleBibFileUpload: (e: React.ChangeEvent<HTMLInputElement>) => Promise<void>;
  isUploadingBib: boolean;
  bibUploadSuccessMessage: string | null;
  bibFileInputRef: React.RefObject<HTMLInputElement>;

  // Custom paths
  customSourceInput: string;
  setCustomSourceInput: (val: string) => void;
  customBibInput: string;
  setCustomBibInput: (val: string) => void;

  // Metadata state & callbacks
  runMetadata: RunMetadataItem[];
  setRunMetadata: React.Dispatch<React.SetStateAction<RunMetadataItem[]>>;
  newMetaKey: string;
  setNewMetaKey: (val: string) => void;
  newMetaValue: string;
  setNewMetaValue: (val: string) => void;

  // Structural anchor fields & callbacks
  globalThesis: string;
  setGlobalThesis: (val: string) => void;
  documentSummary: string;
  setDocumentSummary: (val: string) => void;
  tocStructure: string;
  setTocStructure: (val: string) => void;
}

export const StructuralAnchorsView: React.FC<StructuralAnchorsViewProps> = ({
  effectiveSourcePaths,
  effectiveMetadata,
  effectiveAnchor,
  anchorPromptContextPreview,
  executionMode,
  selectedInputPath,
  setSelectedInputPath,
  multiSourcePaths,
  setMultiSourcePaths,
  availableInputs,
  availableBibDocs,
  selectedBibPaths,
  setSelectedBibPaths,
  handleFileUpload,
  isUploadingFile,
  uploadSuccessMessage,
  fileInputRef,
  handleBibFileUpload,
  isUploadingBib,
  bibUploadSuccessMessage,
  bibFileInputRef,
  customSourceInput,
  setCustomSourceInput,
  customBibInput,
  setCustomBibInput,
  runMetadata,
  setRunMetadata,
  newMetaKey,
  setNewMetaKey,
  newMetaValue,
  setNewMetaValue,
  globalThesis,
  setGlobalThesis,
  documentSummary,
  setDocumentSummary,
  tocStructure,
  setTocStructure,
}) => {
  const [activeSubTab, setActiveSubTab] = useState<"sources" | "anchors" | "metadata">("sources");

  return (
    <div className="space-y-6">
      {/* Title & Description */}
      <div className="pb-5 border-b border-app-border/80">
        <div className="flex items-center justify-between gap-2">
          <h3 className="type-h1 text-app-heading">
            Pipeline Input & Structural Anchors
          </h3>
          <span className="type-caption text-app-muted">
            {effectiveSourcePaths.length} doc{effectiveSourcePaths.length === 1 ? "" : "s"} · {selectedBibPaths.length} bib · {runMetadata.length} tags
          </span>
        </div>
        <p className="type-body text-app-muted mt-1.5 max-w-2xl">
          Establishes ingested corpus documents (<code>source_paths</code>), literature bibliography references (<code>bib_paths</code>),
          and global macro-structural coordinates orienting downstream proposition synthesis.
        </p>
      </div>

      {/* Zero-Box Segmented Navigation Tabs */}
      <div className="flex items-center justify-between border-b border-app-border pb-2">
        <div className="p-0.5 inline-flex items-center bg-app-subtle rounded-md border border-app-border/60 gap-0.5">
          <button
            type="button"
            onClick={() => setActiveSubTab("sources")}
            className={`h-7 px-3 rounded text-xs transition-all cursor-pointer flex items-center gap-1.5 ${
              activeSubTab === "sources"
                ? "bg-app-surface font-semibold text-app-heading shadow-xs border border-app-border/80"
                : "text-app-muted hover:text-app-heading hover:bg-app-hover/50"
            }`}
          >
            <FileText className="w-3.5 h-3.5 text-blue-500" />
            <span>Primary Sources</span>
            <span className="type-caption text-app-muted font-mono ml-0.5">
              ({effectiveSourcePaths.length + selectedBibPaths.length})
            </span>
          </button>

          <button
            type="button"
            onClick={() => setActiveSubTab("anchors")}
            className={`h-7 px-3 rounded text-xs transition-all cursor-pointer flex items-center gap-1.5 ${
              activeSubTab === "anchors"
                ? "bg-app-surface font-semibold text-app-heading shadow-xs border border-app-border/80"
                : "text-app-muted hover:text-app-heading hover:bg-app-hover/50"
            }`}
          >
            <Compass className="w-3.5 h-3.5 text-cyan-500" />
            <span>Structural Anchors</span>
            {Boolean(globalThesis || documentSummary || tocStructure) && (
              <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 inline-block" />
            )}
          </button>

          <button
            type="button"
            onClick={() => setActiveSubTab("metadata")}
            className={`h-7 px-3 rounded text-xs transition-all cursor-pointer flex items-center gap-1.5 ${
              activeSubTab === "metadata"
                ? "bg-app-surface font-semibold text-app-heading shadow-xs border border-app-border/80"
                : "text-app-muted hover:text-app-heading hover:bg-app-hover/50"
            }`}
          >
            <Tag className="w-3.5 h-3.5 text-purple-500" />
            <span>Run Metadata</span>
            <span className="type-caption text-app-muted font-mono ml-0.5">
              ({runMetadata.length})
            </span>
          </button>
        </div>
      </div>

      {/* ───────────────────────────────────────────────────────────── */}
      {/* SUB-TAB 1: PRIMARY SOURCES (Documents & Bibliographies)       */}
      {/* ───────────────────────────────────────────────────────────── */}
      {activeSubTab === "sources" && (
        <div className="space-y-8 animate-in fade-in duration-150">
          {/* Section A: Candidate Source Documents */}
          <div className="space-y-3">
            <div className="flex items-center justify-between pb-1.5 border-b border-app-border">
              <div>
                <div className="flex items-center gap-2">
                  <h4 className="type-h2 text-app-heading">
                    Candidate Source Documents
                  </h4>
                  <span className="type-mono text-app-muted">source_paths</span>
                </div>
                <p className="type-caption text-app-muted mt-0.5">
                  Target text documents ingested and mapped into the epistemic property graph.
                </p>
              </div>

              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={isUploadingFile}
                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-blue-600 hover:bg-blue-700 text-white text-xs font-medium transition-colors cursor-pointer shrink-0 disabled:opacity-50"
              >
                {isUploadingFile ? <Loader2 className="w-3 h-3 animate-spin" /> : <Upload className="w-3 h-3" />}
                <span>{isUploadingFile ? "Uploading..." : "Upload File"}</span>
              </button>
            </div>

            <input
              ref={fileInputRef}
              type="file"
              className="hidden"
              onChange={handleFileUpload}
              accept=".md,.txt,.tex,.pdf"
            />

            {uploadSuccessMessage && (
              <div className="p-2 rounded bg-emerald-500/10 border border-emerald-500/20 text-emerald-600 dark:text-emerald-400 text-xs flex items-center gap-1.5">
                <Check className="w-3.5 h-3.5" />
                <span>{uploadSuccessMessage}</span>
              </div>
            )}

            {/* Document list with calm surface highlight */}
            <div className="rounded-md border border-app-border overflow-hidden bg-app-subtle/20 divide-y divide-app-border-subtle">
              {availableInputs
                .filter((doc) => !doc.path.endsWith(".bib"))
                .map((doc) => {
                  const isSelected =
                    executionMode === "single"
                      ? selectedInputPath === doc.path
                      : multiSourcePaths.includes(doc.path);

                  return (
                    <div
                      key={doc.path}
                      onClick={() => {
                        if (executionMode === "single") {
                          setSelectedInputPath(doc.path);
                        } else {
                          setMultiSourcePaths((prev) =>
                            prev.includes(doc.path)
                              ? prev.filter((p) => p !== doc.path)
                              : [...prev, doc.path]
                          );
                        }
                      }}
                      className={`flex items-center justify-between px-3 py-2 text-xs cursor-pointer transition-colors ${
                        isSelected
                          ? "bg-app-subtle font-medium text-app-heading"
                          : "hover:bg-app-subtle/50 text-app-muted"
                      }`}
                    >
                      <div className="flex items-center gap-2.5 min-w-0">
                        <input
                          type={executionMode === "single" ? "radio" : "checkbox"}
                          checked={isSelected}
                          readOnly
                          className="rounded text-blue-600 focus:ring-0 focus:ring-offset-0 cursor-pointer pointer-events-none"
                        />
                        <span className="type-mono truncate text-app-heading">{doc.name}</span>
                      </div>
                      <span className="type-caption text-app-muted shrink-0 ml-2 font-mono">
                        {doc.path}
                      </span>
                    </div>
                  );
                })}
            </div>

            {/* Inline Path Adder */}
            <div className="flex items-center gap-2 pt-1">
              <input
                type="text"
                value={customSourceInput}
                onChange={(e) => setCustomSourceInput(e.target.value)}
                placeholder="Enter custom path (e.g. data/my_paper.md)..."
                className="flex-1 h-8 px-3 rounded-md bg-app-subtle/50 hover:bg-app-subtle/80 focus:bg-app-surface text-app-heading border border-app-border text-xs font-mono transition-all focus:outline-none focus:border-blue-500/80"
                onKeyDown={(e) => {
                  if (e.key === "Enter" && customSourceInput.trim()) {
                    const val = customSourceInput.trim();
                    if (!multiSourcePaths.includes(val)) {
                      setMultiSourcePaths((prev) => [...prev, val]);
                    }
                    if (executionMode === "single") {
                      setSelectedInputPath(val);
                    }
                    setCustomSourceInput("");
                  }
                }}
              />
              <button
                type="button"
                onClick={() => {
                  if (!customSourceInput.trim()) return;
                  const val = customSourceInput.trim();
                  if (!multiSourcePaths.includes(val)) {
                    setMultiSourcePaths((prev) => [...prev, val]);
                  }
                  if (executionMode === "single") {
                    setSelectedInputPath(val);
                  }
                  setCustomSourceInput("");
                }}
                className="h-8 px-3 rounded-md bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium transition-colors cursor-pointer shrink-0 flex items-center gap-1"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Add Path</span>
              </button>
            </div>

            {/* Active source badges */}
            {effectiveSourcePaths.length > 0 && (
              <div className="flex flex-wrap gap-1.5 pt-1">
                {effectiveSourcePaths.map((p) => (
                  <span
                    key={p}
                    className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20 text-[11px] font-mono"
                  >
                    <FileText className="w-3 h-3 shrink-0" />
                    <span className="truncate max-w-[280px]">{p}</span>
                    {executionMode === "corpus" && (
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          setMultiSourcePaths((prev) => prev.filter((item) => item !== p));
                        }}
                        className="text-blue-400 hover:text-rose-500 transition-colors cursor-pointer"
                      >
                        <X className="w-3 h-3" />
                      </button>
                    )}
                  </span>
                ))}
              </div>
            )}
          </div>

          {/* Section B: Bibliography References */}
          <div className="space-y-3 pt-4 border-t border-app-border/80">
            <div className="flex items-center justify-between pb-1.5 border-b border-app-border">
              <div>
                <div className="flex items-center gap-2">
                  <h4 className="type-h2 text-app-heading">
                    Bibliography References
                  </h4>
                  <span className="type-mono text-app-muted">bib_paths</span>
                </div>
                <p className="type-caption text-app-muted mt-0.5">
                  BibTeX files used to ground citations and resolve literature cross-references.
                </p>
              </div>

              <button
                type="button"
                onClick={() => bibFileInputRef.current?.click()}
                disabled={isUploadingBib}
                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-medium transition-colors cursor-pointer shrink-0 disabled:opacity-50"
              >
                {isUploadingBib ? <Loader2 className="w-3 h-3 animate-spin" /> : <Upload className="w-3 h-3" />}
                <span>{isUploadingBib ? "Uploading..." : "Upload .bib"}</span>
              </button>
            </div>

            <input
              ref={bibFileInputRef}
              type="file"
              className="hidden"
              onChange={handleBibFileUpload}
              accept=".bib"
            />

            {bibUploadSuccessMessage && (
              <div className="p-2 rounded bg-emerald-500/10 border border-emerald-500/20 text-emerald-600 dark:text-emerald-400 text-xs flex items-center gap-1.5">
                <Check className="w-3.5 h-3.5" />
                <span>{bibUploadSuccessMessage}</span>
              </div>
            )}

            {/* Discovered workspace .bib files */}
            <div className="space-y-2">
              {availableBibDocs.length === 0 ? (
                <div className="p-4 rounded-md border border-dashed border-app-border bg-app-subtle/20 text-center type-caption text-app-muted font-mono">
                  No .bib files found in workspace. Upload a .bib file or enter a custom path below.
                </div>
              ) : (
                <div className="rounded-md border border-app-border overflow-hidden bg-app-subtle/20 divide-y divide-app-border-subtle">
                  {availableBibDocs.map((doc) => {
                    const isSelected = selectedBibPaths.includes(doc.path);
                    return (
                      <div
                        key={doc.path}
                        onClick={() => {
                          setSelectedBibPaths((prev) =>
                            isSelected ? prev.filter((p) => p !== doc.path) : [...prev, doc.path]
                          );
                        }}
                        className={`flex items-center justify-between px-3 py-2 text-xs cursor-pointer transition-colors ${
                          isSelected
                            ? "bg-app-subtle font-medium text-app-heading"
                            : "hover:bg-app-subtle/50 text-app-muted"
                        }`}
                      >
                        <div className="flex items-center gap-2.5 min-w-0">
                          <input
                            type="checkbox"
                            checked={isSelected}
                            readOnly
                            className="rounded text-emerald-600 focus:ring-0 focus:ring-offset-0 cursor-pointer pointer-events-none"
                          />
                          <span className="type-mono truncate text-app-heading">{doc.name}</span>
                        </div>
                        <span className="type-caption text-app-muted shrink-0 ml-2 font-mono">
                          {doc.path}
                        </span>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Inline Custom path adder */}
            <div className="flex items-center gap-2 pt-1">
              <input
                type="text"
                value={customBibInput}
                onChange={(e) => setCustomBibInput(e.target.value)}
                placeholder="Enter custom bibliography path (e.g. data/references.bib)..."
                className="flex-1 h-8 px-3 rounded-md bg-app-subtle/50 hover:bg-app-subtle/80 focus:bg-app-surface text-app-heading border border-app-border text-xs font-mono transition-all focus:outline-none focus:border-emerald-500/80"
                onKeyDown={(e) => {
                  if (e.key === "Enter" && customBibInput.trim()) {
                    const val = customBibInput.trim();
                    if (!selectedBibPaths.includes(val)) {
                      setSelectedBibPaths((prev) => [...prev, val]);
                    }
                    setCustomBibInput("");
                  }
                }}
              />
              <button
                type="button"
                onClick={() => {
                  if (!customBibInput.trim()) return;
                  const val = customBibInput.trim();
                  if (!selectedBibPaths.includes(val)) {
                    setSelectedBibPaths((prev) => [...prev, val]);
                  }
                  setCustomBibInput("");
                }}
                className="h-8 px-3 rounded-md bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-medium transition-colors cursor-pointer shrink-0 flex items-center gap-1"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Attach .bib</span>
              </button>
            </div>

            {/* Active bib badges */}
            {selectedBibPaths.length > 0 && (
              <div className="flex flex-wrap gap-1.5 pt-1">
                {selectedBibPaths.map((p) => (
                  <span
                    key={p}
                    className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20 text-[11px] font-mono"
                  >
                    <BookOpen className="w-3 h-3 shrink-0" />
                    <span className="truncate max-w-[280px]">{p}</span>
                    <button
                      type="button"
                      onClick={() => setSelectedBibPaths((prev) => prev.filter((item) => item !== p))}
                      className="text-emerald-400 hover:text-rose-500 transition-colors cursor-pointer"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ───────────────────────────────────────────────────────────── */}
      {/* SUB-TAB 2: STRUCTURAL ANCHORS (Coordinates & Outline)         */}
      {/* ───────────────────────────────────────────────────────────── */}
      {activeSubTab === "anchors" && (
        <div className="space-y-6 animate-in fade-in duration-150">
          <div className="flex items-center justify-between pb-1.5 border-b border-app-border">
            <div>
              <h4 className="type-h2 text-app-heading">
                Macro-Structural Coordinates
              </h4>
              <p className="type-caption text-app-muted mt-0.5">
                Macro-coordinates orienting argument mining and claim synthesis via <code>&#123;structural_anchor&#125;</code>.
              </p>
            </div>

            {effectiveAnchor && (
              <button
                type="button"
                onClick={() => {
                  setGlobalThesis("");
                  setDocumentSummary("");
                  setTocStructure("");
                }}
                className="inline-flex items-center gap-1 type-caption text-app-muted hover:text-rose-500 transition-colors cursor-pointer px-2 py-0.5 rounded hover:bg-app-subtle"
              >
                <RotateCcw className="w-3 h-3" />
                <span>Reset Coordinates</span>
              </button>
            )}
          </div>

          {/* Global Thesis Input */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <label className="text-xs font-medium text-app-heading">
                Global Thesis / Central Claim
              </label>
              <span className="type-mono text-app-muted/80">structural_anchor.global_thesis</span>
            </div>
            <input
              type="text"
              value={globalThesis}
              onChange={(e) => setGlobalThesis(e.target.value)}
              placeholder="e.g. Teacher expectations act as self-fulfilling prophecies impacting student intellectual development..."
              className="w-full h-9 px-3 rounded-md bg-app-subtle/50 hover:bg-app-subtle/80 focus:bg-app-surface text-app-heading border border-app-border text-xs font-mono transition-all focus:outline-none focus:border-blue-500/80"
            />
            <span className="type-caption text-app-muted block">
              Core conceptual thesis anchor to prevent epistemic drift during localized chunk processing.
            </span>
          </div>

          {/* Document Summary */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <label className="text-xs font-medium text-app-heading">
                Document Summary & Scope
              </label>
              <span className="type-mono text-app-muted/80">structural_anchor.document_summary</span>
            </div>
            <textarea
              rows={4}
              value={documentSummary}
              onChange={(e) => setDocumentSummary(e.target.value)}
              placeholder="Provide a concise 1-2 paragraph overview of the document context, scope, or methodology..."
              className="w-full p-3 rounded-md bg-app-subtle/50 hover:bg-app-subtle/80 focus:bg-app-surface text-app-heading border border-app-border text-xs font-mono transition-all focus:outline-none focus:border-blue-500/80 resize-y leading-relaxed"
            />
            <div className="flex items-center justify-between type-caption text-app-muted">
              <span>Concise summary of context, methodology, and domain boundary conditions.</span>
              <span className="type-mono text-app-muted">{documentSummary.length} chars</span>
            </div>
          </div>

          {/* Table of Contents Outline */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <label className="text-xs font-medium text-app-heading">
                Table of Contents Outline
              </label>
              <span className="type-mono text-app-muted/80">structural_anchor.toc_structure (one per line)</span>
            </div>
            <textarea
              rows={5}
              value={tocStructure}
              onChange={(e) => setTocStructure(e.target.value)}
              placeholder={"1. Introduction & Theoretical Foundation\n2. Experimental Setup and Pygmalion Effect\n3. Methodological Validation\n4. Discussion and Limitations"}
              className="w-full p-3 rounded-md bg-app-subtle/50 hover:bg-app-subtle/80 focus:bg-app-surface text-app-heading border border-app-border text-xs font-mono transition-all focus:outline-none focus:border-blue-500/80 resize-y leading-relaxed"
            />
            <div className="flex items-center justify-between type-caption text-app-muted">
              <span>Enforces structural section header tracking and alignment during proposition synthesis.</span>
              <span className="type-mono text-app-muted">
                {tocStructure.split("\n").filter((l) => l.trim()).length} outline items
              </span>
            </div>
          </div>

          {/* Live Context Preview (Prompt Code Style) - Only visible when populated */}
          {anchorPromptContextPreview ? (
            <div className="space-y-2 pt-2 border-t border-app-border/80 animate-in fade-in duration-150">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1.5 text-xs font-semibold text-app-heading">
                  <Sparkles className="w-3.5 h-3.5 text-blue-500" />
                  <span>Live Prompt Context Preview</span>
                </div>
                <span className="type-mono text-app-muted">
                  {anchorPromptContextPreview.length} chars
                </span>
              </div>

              <div className="rounded-md border border-app-border overflow-hidden bg-app-subtle/30">
                <div className="px-3 py-1.5 border-b border-app-border bg-app-subtle/50 flex items-center justify-between type-caption font-mono text-app-muted">
                  <span>structural_anchor_context</span>
                  <span>Injected into prompt template</span>
                </div>
                <pre className="p-3 font-mono text-[11px] text-app-heading whitespace-pre-wrap leading-relaxed max-h-56 overflow-y-auto">
                  {anchorPromptContextPreview}
                </pre>
              </div>
            </div>
          ) : null}
        </div>
      )}

      {/* ───────────────────────────────────────────────────────────── */}
      {/* SUB-TAB 3: RUN METADATA & PRESETS                             */}
      {/* ───────────────────────────────────────────────────────────── */}
      {activeSubTab === "metadata" && (
        <div className="space-y-6 animate-in fade-in duration-150">
          <div className="flex items-center justify-between pb-1.5 border-b border-app-border">
            <div>
              <div className="flex items-center gap-2">
                <h4 className="type-h2 text-app-heading">
                  Execution Run Metadata
                </h4>
                <span className="type-mono text-app-muted">metadata</span>
              </div>
              <p className="type-caption text-app-muted mt-0.5">
                Arbitrary key-value metadata strings saved into the pipeline run manifest.
              </p>
            </div>

            {/* Quick Presets */}
            <div className="flex items-center gap-1">
              <span className="type-caption text-app-muted mr-1">Presets:</span>
              {[
                { k: "domain", v: "philosophy" },
                { k: "author", v: "" },
                { k: "language", v: "en" },
              ].map((preset) => (
                <button
                  key={preset.k}
                  type="button"
                  onClick={() => {
                    if (!runMetadata.some((m) => m.key === preset.k)) {
                      setRunMetadata((prev) => [
                        ...prev,
                        { id: `meta-${Date.now()}-${Math.random()}`, key: preset.k, value: preset.v },
                      ]);
                    }
                  }}
                  className="px-2 py-0.5 rounded text-[10px] font-mono bg-app-surface hover:bg-app-subtle text-app-muted hover:text-app-heading border border-app-border transition-colors cursor-pointer"
                >
                  +{preset.k}
                </button>
              ))}
            </div>
          </div>

          {/* Metadata items list */}
          {runMetadata.length > 0 ? (
            <div className="rounded-md border border-app-border overflow-hidden bg-app-subtle/20 divide-y divide-app-border-subtle p-1 space-y-1">
              {runMetadata.map((item) => (
                <div key={item.id} className="flex items-center gap-2 p-1.5">
                  <input
                    type="text"
                    value={item.key}
                    placeholder="Key..."
                    onChange={(e) => {
                      const val = e.target.value;
                      setRunMetadata((prev) =>
                        prev.map((m) => (m.id === item.id ? { ...m, key: val } : m))
                      );
                    }}
                    className="w-1/3 h-8 px-2.5 rounded-md bg-app-surface text-app-heading border border-app-border text-xs font-mono focus:outline-none focus:border-purple-500"
                  />
                  <input
                    type="text"
                    value={item.value}
                    placeholder="Value..."
                    onChange={(e) => {
                      const val = e.target.value;
                      setRunMetadata((prev) =>
                        prev.map((m) => (m.id === item.id ? { ...m, value: val } : m))
                      );
                    }}
                    className="flex-1 h-8 px-2.5 rounded-md bg-app-surface text-app-heading border border-app-border text-xs font-mono focus:outline-none focus:border-purple-500"
                  />
                  <button
                    type="button"
                    onClick={() => setRunMetadata((prev) => prev.filter((m) => m.id !== item.id))}
                    className="p-1.5 text-app-muted hover:text-rose-500 transition-colors cursor-pointer rounded hover:bg-rose-500/10"
                    title="Remove entry"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              ))}
            </div>
          ) : (
            <div className="p-6 rounded-md border border-dashed border-app-border bg-app-subtle/20 text-center type-caption text-app-muted font-mono">
              No metadata entries. Use the presets above or add a key-value pair below.
            </div>
          )}

          {/* New row */}
          <div className="flex items-center gap-2 pt-1">
            <input
              type="text"
              value={newMetaKey}
              onChange={(e) => setNewMetaKey(e.target.value)}
              placeholder="New key (e.g. corpus_id, version)..."
              className="w-1/3 h-8 px-3 rounded-md bg-app-subtle/50 hover:bg-app-subtle/80 focus:bg-app-surface text-app-heading border border-app-border text-xs font-mono transition-all focus:outline-none focus:border-purple-500/80"
              onKeyDown={(e) => {
                if (e.key === "Enter" && newMetaKey.trim()) {
                  setRunMetadata((prev) => [
                    ...prev,
                    { id: `meta-${Date.now()}`, key: newMetaKey.trim(), value: newMetaValue.trim() },
                  ]);
                  setNewMetaKey("");
                  setNewMetaValue("");
                }
              }}
            />
            <input
              type="text"
              value={newMetaValue}
              onChange={(e) => setNewMetaValue(e.target.value)}
              placeholder="Value..."
              className="flex-1 h-8 px-3 rounded-md bg-app-subtle/50 hover:bg-app-subtle/80 focus:bg-app-surface text-app-heading border border-app-border text-xs font-mono transition-all focus:outline-none focus:border-purple-500/80"
              onKeyDown={(e) => {
                if (e.key === "Enter" && newMetaKey.trim()) {
                  setRunMetadata((prev) => [
                    ...prev,
                    { id: `meta-${Date.now()}`, key: newMetaKey.trim(), value: newMetaValue.trim() },
                  ]);
                  setNewMetaKey("");
                  setNewMetaValue("");
                }
              }}
            />
            <button
              type="button"
              onClick={() => {
                if (!newMetaKey.trim()) return;
                setRunMetadata((prev) => [
                  ...prev,
                  { id: `meta-${Date.now()}`, key: newMetaKey.trim(), value: newMetaValue.trim() },
                ]);
                setNewMetaKey("");
                setNewMetaValue("");
              }}
              className="h-8 px-3 rounded-md bg-purple-600 hover:bg-purple-500 text-white text-xs font-medium transition-colors cursor-pointer shrink-0 flex items-center gap-1"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Add Entry</span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
