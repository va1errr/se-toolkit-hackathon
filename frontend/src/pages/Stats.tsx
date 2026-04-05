/** Stats dashboard — forum analytics page. */

import { useState, useEffect } from "react";
import { Link } from "react-router-dom";

interface StatsData {
  total_questions: number;
  status_breakdown: Record<string, number>;
  total_users: number;
  total_tas: number;
  total_labs: number;
  ai_answers: number;
  ai_avg_confidence: number;
  ai_high_confidence: number;
  ai_low_confidence: number;
  ai_reasoning_time: { min: number | null; max: number | null; avg: number | null };
  ratings: { helpful: number; not_helpful: number };
  top_users: { username: string; role: string; questions: number }[];
}

function formatReasoningTime(seconds: number | null): string {
  if (seconds == null) return "—";
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`;
}

export default function StatsPage() {
  const [stats, setStats] = useState<StatsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const loadStats = async () => {
      try {
        const token = localStorage.getItem("token");
        const res = await fetch("/api/v1/stats", {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (res.ok) setStats(await res.json());
        else setError("Failed to load stats");
      } catch {
        setError("Failed to load stats");
      } finally {
        setLoading(false);
      }
    };
    loadStats();
  }, []);

  if (loading) return <div className="stats-page"><p className="loading">Loading stats...</p></div>;
  if (error) return <div className="stats-page"><p className="error">{error}</p></div>;
  if (!stats) return null;

  const helpfulRate = stats.ratings.helpful + stats.ratings.not_helpful > 0
    ? Math.round((stats.ratings.helpful / (stats.ratings.helpful + stats.ratings.not_helpful)) * 100)
    : 0;

  return (
    <div className="stats-page">
      <h1>📊 Forum Statistics</h1>

      <div className="stats-grid">
        {/* Overview cards */}
        <div className="stat-card">
          <div className="stat-value">{stats.total_questions}</div>
          <div className="stat-label">Total Questions</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{stats.total_users}</div>
          <div className="stat-label">Users</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{stats.total_tas}</div>
          <div className="stat-label">TAs / Admins</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{stats.total_labs}</div>
          <div className="stat-label">Lab Documents</div>
        </div>

        {/* Question status breakdown */}
        <div className="stat-card stat-card-wide">
          <h3>Question Status</h3>
          <div className="status-bars">
            {Object.entries(stats.status_breakdown).map(([status, count]) => (
              <div key={status} className="status-bar-item">
                <span className={`status-dot status-${status}`} />
                <span className="status-name">{status}</span>
                <span className="status-count">{count}</span>
              </div>
            ))}
          </div>
        </div>

        {/* AI Performance */}
        <div className="stat-card stat-card-wide">
          <h3>🤖 AI Performance</h3>
          <div className="ai-stats">
            <div className="ai-stat">
              <div className="ai-stat-value">{stats.ai_answers}</div>
              <div className="ai-stat-label">AI Answers</div>
            </div>
            <div className="ai-stat">
              <div className="ai-stat-value">{stats.ai_avg_confidence > 0 ? `${Math.round(stats.ai_avg_confidence * 100)}%` : "—"}</div>
              <div className="ai-stat-label">Avg Confidence</div>
            </div>
            <div className="ai-stat">
              <div className="ai-stat-value success">{stats.ai_high_confidence}</div>
              <div className="ai-stat-label">High Conf. (≥50%)</div>
            </div>
            <div className="ai-stat">
              <div className="ai-stat-value danger">{stats.ai_low_confidence}</div>
              <div className="ai-stat-label">Low Conf. (&lt;50%)</div>
            </div>
            <div className="ai-stat">
              <div className="ai-stat-value">{formatReasoningTime(stats.ai_reasoning_time?.avg ?? null)}</div>
              <div className="ai-stat-label">Avg Time</div>
            </div>
            <div className="ai-stat">
              <div className="ai-stat-value">{formatReasoningTime(stats.ai_reasoning_time?.min ?? null)}</div>
              <div className="ai-stat-label">Min Time</div>
            </div>
            <div className="ai-stat">
              <div className="ai-stat-value">{formatReasoningTime(stats.ai_reasoning_time?.max ?? null)}</div>
              <div className="ai-stat-label">Max Time</div>
            </div>
          </div>
        </div>

        {/* Rating quality */}
        <div className="stat-card stat-card-wide">
          <h3>👍 Rating Quality</h3>
          <div className="rating-quality">
            <div className="rating-bar">
              <div
                className="rating-bar-fill good"
                style={{ width: `${helpfulRate}%` }}
              />
              <div
                className="rating-bar-fill bad"
                style={{ width: `${100 - helpfulRate}%` }}
              />
            </div>
            <div className="rating-labels">
              <span>👍 {stats.ratings.helpful} helpful ({helpfulRate}%)</span>
              <span>👎 {stats.ratings.not_helpful} not helpful</span>
            </div>
          </div>
        </div>

        {/* Top users */}
        <div className="stat-card stat-card-wide">
          <h3>🏆 Most Active Users</h3>
          {stats.top_users.length === 0 ? (
            <p className="empty">No questions posted yet.</p>
          ) : (
            <table className="top-users-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>User</th>
                  <th>Role</th>
                  <th>Questions</th>
                </tr>
              </thead>
              <tbody>
                {stats.top_users.map((u, i) => (
                  <tr key={u.username}>
                    <td>{i + 1}</td>
                    <td>{u.username}</td>
                    <td><span className={`role-badge role-${u.role}`}>{u.role}</span></td>
                    <td>{u.questions}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      <div className="stats-footer">
        <Link to="/" className="btn-back-home">← Back to Questions</Link>
      </div>
    </div>
  );
}
