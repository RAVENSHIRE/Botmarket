/**
 * A labelled progress meter, used for a memecoin's march toward graduation.
 *
 * The numeric value is always written out beside the bar, so the fill is a
 * second reading of the number rather than the only one.
 */
export default function Meter({
  value,
  label,
  caption,
}: {
  /** Progress in the range 0–1. */
  value: number;
  label: string;
  caption?: string;
}) {
  const pct = Math.round(Math.min(1, Math.max(0, value)) * 100);
  const complete = pct >= 100;

  return (
    <div>
      <div className="flex justify-between text-xs text-muted">
        <span>{label}</span>
        <span className={complete ? "text-signal" : "text-slate-200"}>
          {pct}%
        </span>
      </div>
      <div
        className="mt-1 h-1.5 overflow-hidden rounded-full bg-edge"
        role="progressbar"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={label}
      >
        <div
          className={`h-full rounded-full ${complete ? "bg-signal" : "bg-neon"}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      {caption && <p className="mt-1 text-xs text-muted">{caption}</p>}
    </div>
  );
}
