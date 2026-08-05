"use client";

/**
 * The "acting agent" the dashboard operates as.
 *
 * Every write endpoint is scoped to an agent, so the dashboard has to know who
 * it is acting as before it can trade, tip, launch a coin or vote. The choice
 * is kept in localStorage so a reload does not lose it.
 *
 * The provider also owns a `revision` counter. Anything that mutates the world
 * calls `refresh()`, which bumps the counter; every `useResource` hook watches
 * it, so one action refreshes the whole page rather than just the panel that
 * triggered it.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { api, ApiError, type Agent } from "@/lib/api";

const STORAGE_KEY = "botmarket.actor";

interface ActorValue {
  actorId: number | null;
  setActorId: (id: number | null) => void;
  actor: Agent | null;
  agents: Agent[];
  revision: number;
  refresh: () => void;
  offline: boolean;
}

const ActorContext = createContext<ActorValue | null>(null);

export function ActorProvider({ children }: { children: React.ReactNode }) {
  const [actorId, setActorIdState] = useState<number | null>(null);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [revision, setRevision] = useState(0);
  const [offline, setOffline] = useState(false);

  // localStorage is only available in the browser, so restore after mount.
  useEffect(() => {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored) setActorIdState(Number(stored));
  }, []);

  useEffect(() => {
    let cancelled = false;
    api
      .agents()
      .then((rows) => {
        if (cancelled) return;
        setAgents(rows);
        setOffline(false);
        // Drop a stored actor that no longer exists (e.g. after a reset).
        setActorIdState((current) =>
          current !== null && !rows.some((a) => a.id === current)
            ? null
            : (current ?? rows[0]?.id ?? null),
        );
      })
      .catch(() => {
        if (!cancelled) setOffline(true);
      });
    return () => {
      cancelled = true;
    };
  }, [revision]);

  const setActorId = useCallback((id: number | null) => {
    setActorIdState(id);
    if (id === null) window.localStorage.removeItem(STORAGE_KEY);
    else window.localStorage.setItem(STORAGE_KEY, String(id));
  }, []);

  const refresh = useCallback(() => setRevision((r) => r + 1), []);

  const value = useMemo<ActorValue>(
    () => ({
      actorId,
      setActorId,
      actor: agents.find((a) => a.id === actorId) ?? null,
      agents,
      revision,
      refresh,
      offline,
    }),
    [actorId, setActorId, agents, revision, refresh, offline],
  );

  return (
    <ActorContext.Provider value={value}>{children}</ActorContext.Provider>
  );
}

export function useActor(): ActorValue {
  const value = useContext(ActorContext);
  if (!value) throw new Error("useActor must be used inside an ActorProvider");
  return value;
}

interface Resource<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
}

/**
 * Fetch a value from the API, refetching whenever the world changes.
 *
 * @param load Fetcher, stable across renders (wrap it in `useCallback`).
 */
export function useResource<T>(load: () => Promise<T>): Resource<T> {
  const { revision } = useActor();
  const [state, setState] = useState<Resource<T>>({
    data: null,
    error: null,
    loading: true,
  });

  useEffect(() => {
    let cancelled = false;
    setState((prev) => ({ ...prev, loading: true }));
    load()
      .then((data) => {
        if (!cancelled) setState({ data, error: null, loading: false });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        const message =
          err instanceof ApiError
            ? err.message
            : "Backend unreachable. Start the API and reload.";
        setState({ data: null, error: message, loading: false });
      });
    return () => {
      cancelled = true;
    };
  }, [load, revision]);

  return state;
}
