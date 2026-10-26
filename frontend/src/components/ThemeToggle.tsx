"use client";

import { useSyncExternalStore } from "react";
import {
  applyTheme,
  getAppliedTheme,
  subscribeToTheme,
  THEME_STORAGE_KEY,
  type Theme,
} from "@/lib/theme";

function SunIcon() {
  return (
    <svg
      aria-hidden
      className="h-4 w-4"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" />
    </svg>
  );
}

function MoonIcon() {
  return (
    <svg
      aria-hidden
      className="h-4 w-4"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M12 3a7 7 0 1 0 9 9 9 9 0 0 1-9-9Z" />
    </svg>
  );
}

const subscribeNoop = () => () => {};

export function ThemeToggle() {
  // <html class="dark"> is already set by the inline init script before
  // hydration, so read the applied theme instead of copying it into state.
  // The server snapshot is "light" to keep the first paint consistent.
  const theme = useSyncExternalStore(
    subscribeToTheme,
    getAppliedTheme,
    () => "light" as Theme
  );

  // false during SSR/first client render, true afterwards.
  const mounted = useSyncExternalStore(
    subscribeNoop,
    () => true,
    () => false
  );

  function toggleTheme() {
    const next: Theme = theme === "dark" ? "light" : "dark";
    applyTheme(next);
    try {
      localStorage.setItem(THEME_STORAGE_KEY, next);
    } catch {
      /* localStorage unavailable */
    }
  }

  const label =
    theme === "dark" ? "Switch to light mode" : "Switch to dark mode";

  return (
    <button
      type="button"
      onClick={toggleTheme}
      aria-label={label}
      title={label}
      className="inline-flex items-center justify-center gap-2 min-w-[2.75rem] h-10 px-3 rounded-full text-sm font-semibold text-white bg-white/10 border border-white/25 backdrop-blur-sm hover:bg-white/20 hover:border-white/40 transition-colors cursor-pointer"
    >
      {mounted ? (theme === "dark" ? <SunIcon /> : <MoonIcon />) : <MoonIcon />}
      <span className="hidden sm:inline">{theme === "dark" ? "Light" : "Dark"}</span>
    </button>
  );
}