"use client";

/**
 * A single-series price sparkline with a hover crosshair.
 *
 * One series, so there is no legend: the caption names it. Direction is carried
 * by the line colour *and* by the signed trend the caller renders beside it, so
 * polarity is never colour-alone.
 */

import { useMemo, useState } from "react";

const WIDTH = 600;
const HEIGHT = 120;
const PAD = 6;

interface Props {
  values: number[];
  /** Tick number of the first value, used to label the hover tooltip. */
  startTick?: number;
  /** Rising or falling — drives the accent colour. */
  rising?: boolean;
}

export default function Sparkline({
  values,
  startTick = 1,
  rising = true,
}: Props) {
  const [hover, setHover] = useState<number | null>(null);

  const geometry = useMemo(() => {
    if (values.length === 0) return null;
    const min = Math.min(...values);
    const max = Math.max(...values);
    // A flat series would divide by zero; give it a centred line instead.
    const span = max - min || 1;
    const step =
      values.length > 1 ? (WIDTH - PAD * 2) / (values.length - 1) : 0;

    const points = values.map((value, i) => ({
      x: PAD + i * step,
      y:
        PAD +
        (HEIGHT - PAD * 2) *
          (max === min ? 0.5 : 1 - (value - min) / span),
      value,
    }));
    return { points, min, max };
  }, [values]);

  if (!geometry) {
    return (
      <p className="py-8 text-center text-xs text-muted">
        No price history yet — run a tick.
      </p>
    );
  }

  const { points, min, max } = geometry;
  const accent = rising ? "#3ddc97" : "#ff5c72";
  const line = points.map((p) => `${p.x},${p.y}`).join(" ");
  const area = `${PAD},${HEIGHT - PAD} ${line} ${points[points.length - 1].x},${HEIGHT - PAD}`;
  const active = hover !== null ? points[hover] : null;

  return (
    <figure className="m-0">
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        className="h-32 w-full"
        role="img"
        aria-label={`$BOT price over the last ${values.length} ticks, from ${values[0].toFixed(2)} to ${values[values.length - 1].toFixed(2)}.`}
        onMouseLeave={() => setHover(null)}
        onMouseMove={(e) => {
          const box = e.currentTarget.getBoundingClientRect();
          const ratio = (e.clientX - box.left) / box.width;
          const index = Math.round(ratio * (points.length - 1));
          setHover(Math.min(points.length - 1, Math.max(0, index)));
        }}
      >
        <defs>
          <linearGradient id="spark-fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={accent} stopOpacity="0.22" />
            <stop offset="100%" stopColor={accent} stopOpacity="0" />
          </linearGradient>
        </defs>

        <polygon points={area} fill="url(#spark-fill)" />
        <polyline
          points={line}
          fill="none"
          stroke={accent}
          strokeWidth={2}
          strokeLinecap="round"
          strokeLinejoin="round"
        />

        {active && (
          <g>
            {/* Recessive crosshair — the data stays the loudest thing here. */}
            <line
              x1={active.x}
              y1={PAD}
              x2={active.x}
              y2={HEIGHT - PAD}
              stroke="#1f2a44"
              strokeWidth={1}
            />
            <circle
              cx={active.x}
              cy={active.y}
              r={4}
              fill={accent}
              stroke="#0d1220"
              strokeWidth={2}
            />
          </g>
        )}
      </svg>

      <figcaption className="flex justify-between px-1 text-xs text-muted">
        <span>low {min.toFixed(2)}</span>
        <span aria-live="polite">
          {active
            ? `tick ${startTick + (hover ?? 0)} · ${active.value.toFixed(2)}`
            : `$BOT · last ${values.length} ticks`}
        </span>
        <span>high {max.toFixed(2)}</span>
      </figcaption>
    </figure>
  );
}
