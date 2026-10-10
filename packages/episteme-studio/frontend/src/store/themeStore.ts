import {create} from "zustand";

export type Theme = "dark" | "light";
export type ThemePreference = "dark" | "light" | "system";

interface ThemeState {
  theme: Theme;
  themePreference: ThemePreference;
  setTheme: (theme: Theme) => void;
  setThemePreference: (pref: ThemePreference) => void;
  toggleTheme: () => void;
}

const resolveSystemTheme = (): Theme => {
  if (typeof window === "undefined") return "dark";
  return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
};

const applyThemeToDOM = (theme: Theme) => {
  if (typeof document === "undefined") return;
  document.documentElement.setAttribute("data-theme", theme);
  if (theme === "light") {
    document.documentElement.classList.add("light");
    document.documentElement.classList.remove("dark");
  } else {
    document.documentElement.classList.add("dark");
    document.documentElement.classList.remove("light");
  }
  document.documentElement.style.colorScheme = theme;
};

const getInitialPreference = (): ThemePreference => {
  if (typeof window === "undefined") return "dark";
  try {
    const stored = localStorage.getItem("glp-studio-theme-pref") as ThemePreference | null;
    if (stored === "dark" || stored === "light" || stored === "system") return stored;
    const legacy = localStorage.getItem("glp-studio-theme") as Theme | null;
    if (legacy === "dark" || legacy === "light") return legacy;
    return "dark";
  } catch {
    return "dark";
  }
};

const initialPref = getInitialPreference();
const initialResolved: Theme = initialPref === "system" ? resolveSystemTheme() : initialPref;
applyThemeToDOM(initialResolved);

export const useThemeStore = create<ThemeState>((set, get) => {
  // Listen for system theme changes if preference is "system"
  if (typeof window !== "undefined") {
    const media = window.matchMedia("(prefers-color-scheme: light)");
    const handler = (e: MediaQueryListEvent) => {
      if (get().themePreference === "system") {
        const next: Theme = e.matches ? "light" : "dark";
        applyThemeToDOM(next);
        set({ theme: next });
      }
    };
    if (media.addEventListener) {
      media.addEventListener("change", handler);
    } else {
      media.addListener(handler);
    }
  }

  return {
    theme: initialResolved,
    themePreference: initialPref,

    setThemePreference: (pref: ThemePreference) => {
      try {
        localStorage.setItem("glp-studio-theme-pref", pref);
        if (pref !== "system") {
          localStorage.setItem("glp-studio-theme", pref);
        }
      } catch {
        // ignore storage errors
      }

      const resolved: Theme = pref === "system" ? resolveSystemTheme() : pref;
      applyThemeToDOM(resolved);
      set({ themePreference: pref, theme: resolved });
    },

    setTheme: (theme: Theme) => {
      get().setThemePreference(theme);
    },

    toggleTheme: () => {
      const next = get().theme === "dark" ? "light" : "dark";
      get().setThemePreference(next);
    },
  };
});
