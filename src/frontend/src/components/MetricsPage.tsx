import { useMemo } from "react";
import {
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";

import type { MetricsData } from "../types/messages";

interface Props {
  metrics: MetricsData | null;
}

function formatTime(seconds: number): string {
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins}m ${secs.toFixed(0)}s`;
}

function formatTokens(n: number): string {
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return String(n);
}

// Fixed palette indexed by sorted agent name so the same agent gets the
// same slice color across renders even as new agents enter the chart.
const PIE_COLORS = [
  "#6366f1",
  "#10b981",
  "#f59e0b",
  "#ef4444",
  "#8b5cf6",
  "#06b6d4",
  "#ec4899",
  "#84cc16",
  "#f97316",
  "#14b8a6",
  "#a855f7",
  "#3b82f6",
];

export default function MetricsPage({ metrics }: Props) {
  const hasData =
    metrics !== null &&
    (Object.keys(metrics.agents).length > 0 || metrics.steps.length > 0);

  const agentRows = useMemo(() => {
    if (!metrics) return [];
    return Object.entries(metrics.agents)
      .map(([name, m]) => ({
        name,
        ...m,
        total: m.input_tokens + m.output_tokens,
      }))
      .sort((a, b) => b.total - a.total);
  }, [metrics]);

  const pieData = useMemo(
    () =>
      agentRows
        .filter((row) => row.total > 0)
        .map((row) => ({ name: row.name, value: row.total })),
    [agentRows],
  );

  const totals = useMemo(() => {
    let input = 0;
    let output = 0;
    let time = 0;
    let calls = 0;
    for (const row of agentRows) {
      input += row.input_tokens;
      output += row.output_tokens;
      time += row.time_seconds;
      calls += row.llm_calls;
    }
    return { input, output, time, calls };
  }, [agentRows]);

  if (!hasData) {
    return (
      <div className="metrics-page">
        <h2 className="metrics-title">Session Metrics</h2>
        <p className="metrics-empty">
          No metrics yet. Send a message to begin tracking.
        </p>
      </div>
    );
  }

  return (
    <div className="metrics-page">
      <h2 className="metrics-title">Session Metrics</h2>

      <section className="metrics-section">
        <h3 className="metrics-heading">Totals</h3>
        <div className="metrics-totals">
          <div className="metrics-stat">
            <span className="metrics-label">Input tokens</span>
            <span className="metrics-value">{formatTokens(totals.input)}</span>
          </div>
          <div className="metrics-stat">
            <span className="metrics-label">Output tokens</span>
            <span className="metrics-value">{formatTokens(totals.output)}</span>
          </div>
          <div className="metrics-stat">
            <span className="metrics-label">LLM calls</span>
            <span className="metrics-value">{totals.calls}</span>
          </div>
          <div className="metrics-stat">
            <span className="metrics-label">Total time</span>
            <span className="metrics-value">{formatTime(totals.time)}</span>
          </div>
        </div>
      </section>

      {pieData.length > 0 && (
        <section className="metrics-section">
          <h3 className="metrics-heading">Tokens by agent</h3>
          <div className="metrics-chart">
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={pieData}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  outerRadius={100}
                  label={(entry: { name?: string; value?: number }) =>
                    entry.name ?? ""
                  }
                >
                  {pieData.map((entry, idx) => (
                    <Cell
                      key={entry.name}
                      fill={PIE_COLORS[idx % PIE_COLORS.length]}
                    />
                  ))}
                </Pie>
                <Tooltip
                  formatter={(value) => [
                    formatTokens(Number(value ?? 0)),
                    "Tokens",
                  ]}
                />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </section>
      )}

      <section className="metrics-section">
        <h3 className="metrics-heading">Per agent</h3>
        <table className="metrics-table">
          <thead>
            <tr>
              <th>Agent</th>
              <th>Input</th>
              <th>Output</th>
              <th>Calls</th>
              <th>Time</th>
            </tr>
          </thead>
          <tbody>
            {agentRows.map((row) => (
              <tr key={row.name}>
                <td className="metrics-agent-name">{row.name}</td>
                <td>{formatTokens(row.input_tokens)}</td>
                <td>{formatTokens(row.output_tokens)}</td>
                <td>{row.llm_calls}</td>
                <td>{formatTime(row.time_seconds)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {metrics && metrics.steps.length > 0 && (
        <section className="metrics-section">
          <h3 className="metrics-heading">Per plan step</h3>
          <table className="metrics-table">
            <thead>
              <tr>
                <th>Step</th>
                <th>Agent</th>
                <th>Tokens</th>
                <th>Calls</th>
                <th>Time</th>
              </tr>
            </thead>
            <tbody>
              {metrics.steps.map((step) => (
                <tr key={step.step_id}>
                  <td>{step.step_id}</td>
                  <td className="metrics-agent-name">{step.agent_name}</td>
                  <td>
                    {formatTokens(step.input_tokens + step.output_tokens)}
                  </td>
                  <td>{step.llm_calls}</td>
                  <td>{formatTime(step.time_seconds)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </div>
  );
}
