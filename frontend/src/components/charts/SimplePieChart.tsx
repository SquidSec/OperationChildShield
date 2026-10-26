import type { PieSegment } from "@/lib/vote-counts";

interface SimplePieChartProps {
  segments: PieSegment[];
  size?: number;
  className?: string;
  ariaLabel: string;
}

function polar(cx: number, cy: number, radius: number, angleDeg: number) {
  const angle = ((angleDeg - 90) * Math.PI) / 180;
  return {
    x: cx + radius * Math.cos(angle),
    y: cy + radius * Math.sin(angle),
  };
}

function arcPath(
  cx: number,
  cy: number,
  radius: number,
  startAngle: number,
  endAngle: number
): string {
  const start = polar(cx, cy, radius, endAngle);
  const end = polar(cx, cy, radius, startAngle);
  const largeArc = endAngle - startAngle > 180 ? 1 : 0;
  return `M ${cx} ${cy} L ${start.x} ${start.y} A ${radius} ${radius} 0 ${largeArc} 0 ${end.x} ${end.y} Z`;
}

export function SimplePieChart({
  segments,
  size = 120,
  className = "",
  ariaLabel,
}: SimplePieChartProps) {
  const total = segments.reduce((sum, segment) => sum + segment.value, 0);
  const cx = size / 2;
  const cy = size / 2;
  const radius = size / 2 - 2;

  if (total <= 0) {
    return (
      <div
        className={`flex items-center justify-center rounded-full bg-surface-muted text-xs text-muted ${className}`}
        style={{ width: size, height: size }}
        role="img"
        aria-label={`${ariaLabel}: no data`}
      >
        N/A
      </div>
    );
  }

  // Accumulate start angles without mutating a shared cursor during render.
  const bounds = segments.reduce<number[]>((acc, segment, index) => {
    const previous = index === 0 ? 0 : acc[index - 1];
    acc.push(previous + (segment.value / total) * 360);
    return acc;
  }, []);

  const slices = segments.map((segment, index) => {
    const end = bounds[index];
    const start = index === 0 ? 0 : bounds[index - 1];
    const sweep = end - start;
    return {
      ...segment,
      path:
        sweep >= 359.99
          ? `M ${cx} ${cy} m -${radius} 0 a ${radius} ${radius} 0 1 0 ${radius * 2} 0 a ${radius} ${radius} 0 1 0 -${radius * 2} 0`
          : arcPath(cx, cy, radius, start, end),
    };
  });

  return (
    <svg
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      className={className}
      role="img"
      aria-label={ariaLabel}
    >
      {slices.map((slice) => (
        <path key={slice.label} d={slice.path} fill={slice.color}>
          <title>
            {slice.label}: {slice.value}
          </title>
        </path>
      ))}
    </svg>
  );
}

interface PieLegendProps {
  segments: PieSegment[];
  total?: number;
  compact?: boolean;
}

export function PieLegend({ segments, total, compact = false }: PieLegendProps) {
  const sum = total ?? segments.reduce((acc, segment) => acc + segment.value, 0);

  return (
    <ul
      className={`m-0 list-none p-0 ${compact ? "space-y-1 text-[10px]" : "space-y-2 text-sm"}`}
    >
      {segments.map((segment) => (
        <li key={segment.label} className="flex items-center gap-2 text-muted">
          <span
            className="inline-block h-2.5 w-2.5 shrink-0 rounded-full"
            style={{ backgroundColor: segment.color }}
            aria-hidden
          />
          <span>
            <span className="font-semibold text-foreground">{segment.label}</span>
            {": "}
            {segment.value}
            {sum > 0 && (
              <span className="text-muted">
                {" "}
                ({Math.round((segment.value / sum) * 100)}%)
              </span>
            )}
          </span>
        </li>
      ))}
    </ul>
  );
}