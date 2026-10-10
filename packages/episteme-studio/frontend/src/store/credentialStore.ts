import {create} from "zustand";

export interface RunNeo4jCredentials {
  url: string;
  user?: string;
  password?: string;
  database?: string;
  savedAt?: string;
}

interface CredentialState {
  credentialsMap: Record<string, RunNeo4jCredentials>;
  lastUsedCredentials: RunNeo4jCredentials | null;
  getRunCredentials: (runId: string) => RunNeo4jCredentials | null;
  saveRunCredentials: (runId: string, creds: RunNeo4jCredentials) => void;
  deleteRunCredentials: (runId: string) => void;
  hasRunCredentials: (runId: string) => boolean;
  setLastUsedCredentials: (creds: RunNeo4jCredentials) => void;
  findRunsForDatabase: (database: string, excludeRunId?: string | null) => string[];
}

const STORAGE_KEY = "glp-studio-run-neo4j-credentials";
const LAST_USED_KEY = "glp-studio-last-used-neo4j-credentials";

const loadFromStorage = (): Record<string, RunNeo4jCredentials> => {
  if (typeof window === "undefined") return {};
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    return JSON.parse(raw);
  } catch (err) {
    console.warn("Failed to load Neo4j credentials from localStorage:", err);
    return {};
  }
};

const loadLastUsed = (): RunNeo4jCredentials | null => {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(LAST_USED_KEY);
    if (!raw) return null;
    return JSON.parse(raw);
  } catch {
    return null;
  }
};

export const useCredentialStore = create<CredentialState>((set, get) => ({
  credentialsMap: loadFromStorage(),
  lastUsedCredentials: loadLastUsed(),

  getRunCredentials: (runId: string) => {
    return get().credentialsMap[runId] || null;
  },

  saveRunCredentials: (runId: string, creds: RunNeo4jCredentials) => {
    const enriched = {
      ...creds,
      savedAt: new Date().toISOString(),
    };
    const updated = {
      ...get().credentialsMap,
      [runId]: enriched,
    };
    try {
      if (typeof window !== "undefined" && window.localStorage) {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
        localStorage.setItem(LAST_USED_KEY, JSON.stringify(enriched));
      }
    } catch (err) {
      console.error("Failed to persist credentials to localStorage:", err);
    }
    set({ credentialsMap: updated, lastUsedCredentials: enriched });
  },

  deleteRunCredentials: (runId: string) => {
    const updated = { ...get().credentialsMap };
    delete updated[runId];
    try {
      if (typeof window !== "undefined" && window.localStorage) {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
      }
    } catch (err) {
      console.error("Failed to delete credentials from localStorage:", err);
    }
    set({ credentialsMap: updated });
  },

  hasRunCredentials: (runId: string) => {
    return Boolean(get().credentialsMap[runId]);
  },

  setLastUsedCredentials: (creds: RunNeo4jCredentials) => {
    set({ lastUsedCredentials: creds });
    try {
      localStorage.setItem(LAST_USED_KEY, JSON.stringify(creds));
    } catch {}
  },

  findRunsForDatabase: (dbName: string, excludeRunId?: string | null): string[] => {
    const target = (dbName || "neo4j").trim().toLowerCase();
    const map = get().credentialsMap;
    return Object.entries(map)
      .filter(([rId, creds]) => {
        if (excludeRunId && rId === excludeRunId) return false;
        const db = (creds.database || "neo4j").trim().toLowerCase();
        return db === target;
      })
      .map(([rId]) => rId);
  },
}));
