import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  THEME_INIT_SCRIPT,
  THEME_STORAGE_KEY,
  applyTheme,
  getAppliedTheme,
  getPreferredTheme,
  subscribeToTheme,
} from "./theme";

/**
 * These tests run in the `node` environment (the project does not ship jsdom),
 * so the handful of browser globals theme.ts touches are stubbed explicitly.
 * That keeps the coverage meaningful without adding a heavy dependency.
 */

function stubMatchMedia(dark: boolean) {
  const impl = (query: string) => ({
    matches: dark && query.includes("dark"),
    media: query,
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
    onchange: null,
    dispatchEvent: () => false,
  });
  // theme.ts calls window.matchMedia, not the bare global, so the stub has to
  // land on the stubbed window object.
  const win = (globalThis as unknown as { window?: { matchMedia?: unknown } }).window;
  if (win) win.matchMedia = impl;
  else vi.stubGlobal("matchMedia", impl);
}

function stubStorage(value: string | null) {
  vi.stubGlobal("localStorage", {
    getItem: () => value,
    setItem: () => {},
    removeItem: () => {},
    clear: () => {},
    key: () => null,
    length: 0,
  });
}

/** Minimal document.documentElement.classList stand-in with real semantics. */
function stubDocument() {
  const classes = new Set<string>();
  const classList = {
    add: (name: string) => classes.add(name),
    remove: (name: string) => classes.delete(name),
    contains: (name: string) => classes.has(name),
    toggle: (name: string, force?: boolean) => {
      const on = force ?? !classes.has(name);
      if (on) classes.add(name);
      else classes.delete(name);
      return on;
    },
  };
  vi.stubGlobal("document", { documentElement: { classList } });
  return classes;
}

function stubWindow() {
  const listeners = new Map<string, Set<() => void>>();
  vi.stubGlobal("window", {
    addEventListener: (type: string, fn: () => void) => {
      if (!listeners.has(type)) listeners.set(type, new Set());
      listeners.get(type)!.add(fn);
    },
    removeEventListener: (type: string, fn: () => void) => {
      listeners.get(type)?.delete(fn);
    },
    dispatchEvent: (event: Event) => {
      for (const fn of listeners.get(event.type) ?? []) fn();
      return true;
    },
  });
  vi.stubGlobal(
    "Event",
    class {
      type: string;
      constructor(type: string) {
        this.type = type;
      }
    }
  );
  return listeners;
}

beforeEach(() => {
  stubDocument();
  stubWindow();
  stubStorage(null);
  stubMatchMedia(false);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("getPreferredTheme", () => {
  it("honors an explicit stored preference over the OS setting", () => {
    stubStorage("light");
    stubMatchMedia(true);
    expect(getPreferredTheme()).toBe("light");
  });

  it("uses the stored dark preference", () => {
    stubStorage("dark");
    stubMatchMedia(false);
    expect(getPreferredTheme()).toBe("dark");
  });

  it("falls back to the OS preference when nothing is stored", () => {
    stubStorage(null);
    stubMatchMedia(true);
    expect(getPreferredTheme()).toBe("dark");
    stubMatchMedia(false);
    expect(getPreferredTheme()).toBe("light");
  });

  it("ignores a junk stored value", () => {
    stubStorage("purple");
    stubMatchMedia(false);
    expect(getPreferredTheme()).toBe("light");
  });

  it("survives localStorage throwing (private mode)", () => {
    vi.stubGlobal("localStorage", {
      getItem: () => {
        throw new Error("blocked");
      },
    });
    stubMatchMedia(true);
    expect(getPreferredTheme()).toBe("dark");
  });
});

describe("applyTheme", () => {
  it("toggles the dark class and notifies subscribers", () => {
    const listener = vi.fn();
    const unsubscribe = subscribeToTheme(listener);

    applyTheme("dark");
    expect(getAppliedTheme()).toBe("dark");
    expect(listener).toHaveBeenCalledTimes(1);

    applyTheme("light");
    expect(getAppliedTheme()).toBe("light");
    expect(listener).toHaveBeenCalledTimes(2);

    unsubscribe();
    applyTheme("dark");
    expect(listener).toHaveBeenCalledTimes(2);
  });
});

describe("getAppliedTheme", () => {
  it("reads the class that is actually applied", () => {
    expect(getAppliedTheme()).toBe("light");
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (document.documentElement.classList as any).add("dark");
    expect(getAppliedTheme()).toBe("dark");
  });
});

describe("THEME_INIT_SCRIPT", () => {
  it("uses the same storage key as the module", () => {
    expect(THEME_INIT_SCRIPT).toContain(`"${THEME_STORAGE_KEY}"`);
  });

  it("is self-contained and swallows storage errors", () => {
    expect(THEME_INIT_SCRIPT).toContain("try{");
    expect(THEME_INIT_SCRIPT).toContain("catch(e){}");
    expect(THEME_INIT_SCRIPT).not.toContain("import");
  });

  it("applies the dark class when run with a dark preference", () => {
    stubStorage("dark");
    new Function(THEME_INIT_SCRIPT)();
    expect(getAppliedTheme()).toBe("dark");
  });

  it("does not add the dark class for a light preference", () => {
    stubStorage("light");
    stubMatchMedia(false);
    new Function(THEME_INIT_SCRIPT)();
    expect(getAppliedTheme()).toBe("light");
  });

  it("does not throw when storage is unavailable", () => {
    vi.stubGlobal("localStorage", {
      getItem: () => {
        throw new Error("blocked");
      },
    });
    expect(() => new Function(THEME_INIT_SCRIPT)()).not.toThrow();
  });
});
