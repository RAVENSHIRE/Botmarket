"use client";

/**
 * Small shared building blocks: stats, empty states, form fields, and the
 * action wrapper every write panel is built on.
 */

import { useState } from "react";
import { ApiError } from "@/lib/api";

/** Fallback shown when the backend is unreachable or a collection is empty. */
export function Empty({ message, hint }: { message: string; hint?: string }) {
  return (
    <div className="panel p-8 text-center text-sm text-muted">
      {message}
      {hint && <p className="mt-2 text-xs">{hint}</p>}
    </div>
  );
}

/** A single headline figure. */
export function Stat({
  label,
  value,
  accent = "text-slate-100",
  sub,
}: {
  label: string;
  value: string | number;
  accent?: string;
  sub?: string;
}) {
  return (
    <div className="panel p-4">
      <p className="text-xs text-muted">{label}</p>
      <p className={`mt-1 text-2xl font-bold ${accent}`}>{value}</p>
      {sub && <p className="mt-0.5 text-xs text-muted">{sub}</p>}
    </div>
  );
}

/** A labelled input. */
export function Field({
  label,
  ...props
}: { label: string } & React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <label className="block text-xs text-muted">
      {label}
      <input
        {...props}
        className="mt-1 w-full rounded-lg border border-edge bg-void px-3 py-2
                   text-sm text-slate-100 outline-none focus:border-neon"
      />
    </label>
  );
}

/** A labelled select. */
export function Select({
  label,
  children,
  ...props
}: { label: string } & React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <label className="block text-xs text-muted">
      {label}
      <select
        {...props}
        className="mt-1 w-full rounded-lg border border-edge bg-void px-3 py-2
                   text-sm text-slate-100 outline-none focus:border-neon"
      >
        {children}
      </select>
    </label>
  );
}

/**
 * Wraps a write action: runs it, disables the form while in flight, and shows
 * whatever the backend said when it refuses.
 *
 * Refusals are the interesting case here — "insufficient funds" and "already
 * voted" are normal outcomes in this economy, not bugs, so they are surfaced
 * verbatim rather than swallowed.
 */
export function ActionForm({
  children,
  submitLabel,
  onSubmit,
  secondary,
  onSettled,
  disabled,
  disabledReason,
}: {
  children?: React.ReactNode;
  submitLabel: string;
  /** Runs on submit; the string it resolves with is shown as confirmation. */
  onSubmit: () => Promise<string | void>;
  /** An optional second action over the same fields (e.g. sell beside buy). */
  secondary?: { label: string; onSubmit: () => Promise<string | void> };
  /**
   * Runs after every attempt, successful or not.
   *
   * A refused action still changes what the server has to say — a rejected
   * order leaves an audit row explaining why — so the view has to refresh on
   * failure too, not only on success.
   */
  onSettled?: () => void;
  disabled?: boolean;
  disabledReason?: string;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);

  const run = async (action: () => Promise<string | void>) => {
    setBusy(true);
    setError(null);
    setOk(null);
    try {
      setOk((await action()) || "Done.");
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Backend unreachable. Start the API and retry.",
      );
    } finally {
      setBusy(false);
      onSettled?.();
    }
  };

  return (
    <form
      className="space-y-3"
      onSubmit={(e) => {
        e.preventDefault();
        run(onSubmit);
      }}
    >
      <fieldset disabled={busy || disabled} className="space-y-3">
        {children}
        <div className="flex gap-2">
          <button type="submit" className="btn flex-1 disabled:opacity-50">
            {busy ? "Working…" : submitLabel}
          </button>
          {secondary && (
            <button
              type="button"
              className="btn flex-1 disabled:opacity-50"
              onClick={() => run(secondary.onSubmit)}
            >
              {secondary.label}
            </button>
          )}
        </div>
      </fieldset>
      {disabled && disabledReason && (
        <p className="text-xs text-muted">{disabledReason}</p>
      )}
      {error && <p className="text-xs text-danger">{error}</p>}
      {ok && !error && <p className="text-xs text-signal">{ok}</p>}
    </form>
  );
}
