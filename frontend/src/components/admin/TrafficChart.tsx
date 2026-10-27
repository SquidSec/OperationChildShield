"use client";

import type { TrafficPoint } from "@/lib/admin-types";

/**
 * Dependency-free SVG line chart. Bars would work too, but a line keeps 90
 * points readable on mobile without horizontal scrolling.
 */
export function TrafficChart({ points }: { points: TrafficPoint[] }) {
  const width = 720;
  const height = 220;
  const padding = { top: 12, right: 12, bottom: 24, left: 36 };

  if (points.length === 0) {
    return <p className="m-0 text-sm text-muted">No page views recorded in this range.</p>;
  }

  const max = Math.max(...points.map((point) => point.views), 1);
  const innerWidth = width - padding.left - padding.right;
  const innerHeight = height - padding.top - padding.bottom;

  const x = (index: number) =>
    padding.left +
    (points.length === 1 ? innerWidth / 2 : (index / (points.length - 1)) * innerWidth);
  const y = (value: number) => padding.top + innerHeight - (value / max) * innerHeight;

  const line = points
    .map((point, index) => `${index === 0 ? "M" : "L"} ${x(index).toFixed(1)} ${y(point.views).toFixed(1)}`)
    .join(" ");
  const area = `${line} L ${x(points.length - 1).toFixed(1)} ${padding.top + innerHeight} L ${x(0).toFixed(1)} ${padding.top + innerHeight} Z`;

  const tickIndexes = [0, Math.floor((points.length - 1) / 2), points.length - 1].filter(
    (value, index, list) => list.indexOf(value) === index
  );
  const gridValues = [0, Math.round(max / 2), max].filter(
    (value, index, list) => list.indexOf(value) === index
  );

  return (
    <div className="w-full">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="h-auto w-full"
        role="img"
        aria-label={`Page views per day, ${points.length} days, peak ${max}`}
      >
        {gridValues.map((value) => (
          <g key={value}>
            <line
              x1={padding.left}
              x2={width - padding.right}
              y1={y(value)}
              y2={y(value)}
              stroke="currentColor"
              className="text-card-border"
              strokeWidth={1}
            />
            <text
              x={padding.left - 6}
              y={y(value) + 4}
              textAnchor="end"
              className="fill-current text-muted"
              fontSize={10}
            >
              {value}
            </text>
          </g>
        ))}

        <path d={area} fill="currentColor" className="text-blue/10" />
        <path
          d={line}
          fill="none"
          stroke="currentColor"
          className="text-blue"
          strokeWidth={2}
          strokeLinejoin="round"
          strokeLinecap="round"
        />

        {tickIndexes.map((index) => (
          <text
            key={index}
            x={x(index)}
            y={height - 6}
            textAnchor={index === 0 ? "start" : index === points.length - 1 ? "end" : "middle"}
            className="fill-current text-muted"
            fontSize={10}
          >
            {new Date(`${points[index].date}T00:00:00Z`).toLocaleDateString("en-US", {
              timeZone: "UTC",
              month: "short",
              day: "numeric",
            })}
          </text>
        ))}
      </svg>

      <table className="sr-only">
        <caption>Page views per day</caption>
        <thead>
          <tr>
            <th scope="col">Date</th>
            <th scope="col">Views</th>
          </tr>
        </thead>
        <tbody>
          {points.map((point) => (
            <tr key={point.date}>
              <td>{point.date}</td>
              <td>{point.views}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
