import {create} from "zustand";
import {api} from "../api/client";
import {LangfuseStatusResponse} from "../api/types";

interface ProjectSettingsState {
  langfuseHost: string;
  langfusePublicKey: string;
  langfuseSecretKey: string;
  langfuseStatus: LangfuseStatusResponse | null;
  isTesting: boolean;
  testFeedback: { success: boolean; message: string } | null;
  promptProvider: "default" | "langfuse";
  promptLabel: string;
  isProjectSettingsOpen: boolean;

  setLangfuseHost: (host: string) => void;
  setLangfusePublicKey: (key: string) => void;
  setLangfuseSecretKey: (key: string) => void;
  setPromptProvider: (provider: "default" | "langfuse") => void;
  setPromptLabel: (label: string) => void;
  stageRefreshIntervalSeconds: number;
  setStageRefreshIntervalSeconds: (seconds: number) => void;
  advancedVisualizations: boolean;
  setAdvancedVisualizations: (enabled: boolean) => void;
  confidenceProgressionInterval: number;
  setConfidenceProgressionInterval: (interval: number) => void;
  openProjectSettings: () => void;
  closeProjectSettings: () => void;
  fetchLangfuseStatus: () => Promise<void>;
  testConnection: () => Promise<void>;
}

const STORAGE_HOST_KEY = "glp-studio-langfuse-host";
const STORAGE_PUB_KEY = "glp-studio-langfuse-public-key";
const STORAGE_SEC_KEY = "glp-studio-langfuse-secret-key";
const STORAGE_PROV_KEY = "glp-studio-prompt-provider";
const STORAGE_LABEL_KEY = "glp-studio-prompt-label";
const STORAGE_INTERVAL_KEY = "glp-studio-stage-refresh-interval";
const STORAGE_ADV_VIS_KEY = "glp-studio-advanced-visualizations";
const STORAGE_PROG_INTERVAL_KEY = "glp-studio-progression-interval";

const getSaved = (key: string, fallback: string): string => {
  if (typeof window === "undefined") return fallback;
  try {
    return localStorage.getItem(key) || fallback;
  } catch {
    return fallback;
  }
};

const getSavedNumber = (key: string, fallback: number): number => {
  if (typeof window === "undefined") return fallback;
  try {
    const val = localStorage.getItem(key);
    if (!val) return fallback;
    const parsed = parseInt(val, 10);
    return isNaN(parsed) || parsed < 5 ? fallback : parsed;
  } catch {
    return fallback;
  }
};

const getSavedBoolean = (key: string, fallback: boolean): boolean => {
  if (typeof window === "undefined") return fallback;
  try {
    const val = localStorage.getItem(key);
    if (val === null) return fallback;
    return val === "true";
  } catch {
    return fallback;
  }
};

export const useProjectSettingsStore = create<ProjectSettingsState>((set, get) => ({
  langfuseHost: getSaved(STORAGE_HOST_KEY, "http://localhost:3000"),
  langfusePublicKey: getSaved(STORAGE_PUB_KEY, ""),
  langfuseSecretKey: getSaved(STORAGE_SEC_KEY, ""),
  langfuseStatus: null,
  isTesting: false,
  testFeedback: null,
  promptProvider: (getSaved(STORAGE_PROV_KEY, "default") as "default" | "langfuse") || "default",
  promptLabel: getSaved(STORAGE_LABEL_KEY, "production"),
  stageRefreshIntervalSeconds: getSavedNumber(STORAGE_INTERVAL_KEY, 30),
  advancedVisualizations: getSavedBoolean(STORAGE_ADV_VIS_KEY, true),
  confidenceProgressionInterval: getSavedNumber(STORAGE_PROG_INTERVAL_KEY, 20),
  isProjectSettingsOpen: false,

  setAdvancedVisualizations: (enabled: boolean) => {
    try {
      localStorage.setItem(STORAGE_ADV_VIS_KEY, String(enabled));
    } catch {}
    set({ advancedVisualizations: enabled });
  },

  setConfidenceProgressionInterval: (interval: number) => {
    const valid = Math.max(5, Math.min(200, Math.round(interval)));
    try {
      localStorage.setItem(STORAGE_PROG_INTERVAL_KEY, String(valid));
    } catch {}
    set({ confidenceProgressionInterval: valid });
  },

  setStageRefreshIntervalSeconds: (seconds: number) => {
    const valid = Math.max(5, Math.min(300, Math.round(seconds)));
    try {
      localStorage.setItem(STORAGE_INTERVAL_KEY, String(valid));
    } catch {}
    set({ stageRefreshIntervalSeconds: valid });
  },

  setLangfuseHost: (host: string) => {
    try {
      localStorage.setItem(STORAGE_HOST_KEY, host);
    } catch {}
    set({ langfuseHost: host });
  },

  setLangfusePublicKey: (key: string) => {
    try {
      localStorage.setItem(STORAGE_PUB_KEY, key);
    } catch {}
    set({ langfusePublicKey: key });
  },

  setLangfuseSecretKey: (key: string) => {
    try {
      localStorage.setItem(STORAGE_SEC_KEY, key);
    } catch {}
    set({ langfuseSecretKey: key });
  },

  setPromptProvider: (provider: "default" | "langfuse") => {
    try {
      localStorage.setItem(STORAGE_PROV_KEY, provider);
    } catch {}
    set({ promptProvider: provider });
  },

  setPromptLabel: (label: string) => {
    try {
      localStorage.setItem(STORAGE_LABEL_KEY, label);
    } catch {}
    set({ promptLabel: label });
  },

  openProjectSettings: () => set({ isProjectSettingsOpen: true }),
  closeProjectSettings: () => set({ isProjectSettingsOpen: false, testFeedback: null }),

  fetchLangfuseStatus: async () => {
    try {
      const status = await api.getLangfuseStatus();
      set((state) => ({
        langfuseStatus: status,
        langfuseHost: status.host || state.langfuseHost,
        langfusePublicKey: state.langfusePublicKey || status.public_key_preview || "",
      }));
    } catch (err) {
      console.warn("Failed to fetch Langfuse status:", err);
    }
  },

  testConnection: async () => {
    const { langfuseHost, langfusePublicKey, langfuseSecretKey } = get();
    set({ isTesting: true, testFeedback: null });
    try {
      const res = await api.testLangfuseConnection({
        host: langfuseHost,
        public_key: langfusePublicKey || undefined,
        secret_key: langfuseSecretKey || undefined,
      });
      set({
        langfuseStatus: res,
        isTesting: false,
        testFeedback: {
          success: res.connected,
          message:
            res.message ||
            (res.connected
              ? `Connected successfully to ${res.host}`
              : `Connection probe failed for ${res.host}`),
        },
      });
    } catch (err: any) {
      set({
        isTesting: false,
        testFeedback: {
          success: false,
          message: String(err?.message || err?.detail || "Network error communicating with server"),
        },
      });
    }
  },
}));
