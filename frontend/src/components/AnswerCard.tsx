/** Card showing an answer with source indicator, rating stats, and rating buttons. */

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import { Answer } from "../types";
import { answersApi, taApi } from "../api/client";
import { useAuth } from "../context/AuthContext";

interface Props {
  answer: Answer;
  onRate: () => void;
  onEdit?: () => void;
  onDelete?: () => void;
}

export default function AnswerCard({ answer, onRate, onEdit, onDelete }: Props) {
  const { user } = useAuth();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState(false);
  const [editBody, setEditBody] = useState(answer.body);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  // Derive state directly from props
  const userRating = answer.user_rating ?? null;
  const helpfulCount = answer.helpful_count ?? 0;
  const notHelpfulCount = answer.not_helpful_count ?? 0;

  // Permission: TA can edit/delete own, Admin can edit/delete any non-AI
  const canManage =
    user &&
    answer.source !== "ai" &&
    (user.role === "admin" || (user.role === "ta" && answer.user_id === user.id));

  const sourceLabels: Record<string, string> = {
    ai: "🤖 AI",
    ta: "👨‍🏫 TA",
    student: "🎓 Student",
  };

  const handleRate = async (helpful: boolean) => {
    if (loading) return;
    setLoading(true);
    setError("");

    try {
      await answersApi.rate(answer.id, helpful);
      onRate();
    } catch (err: any) {
      const msg = err.response?.data?.detail || "Failed to rate answer";
      setError(typeof msg === "string" ? msg : JSON.stringify(msg));
    } finally {
      setLoading(false);
    }
  };

  const handleSaveEdit = async () => {
    if (!editBody.trim() || loading) return;
    setLoading(true);
    setError("");

    try {
      await taApi.editAnswer(answer.id, editBody);
      setEditing(false);
      onEdit?.();
    } catch (err: any) {
      const msg = err.response?.data?.detail || "Failed to edit answer";
      setError(typeof msg === "string" ? msg : JSON.stringify(msg));
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async () => {
    if (loading) return;
    setLoading(true);
    setError("");

    try {
      await taApi.deleteAnswer(answer.id);
      setShowDeleteConfirm(false);
      onDelete?.();
    } catch (err: any) {
      const msg = err.response?.data?.detail || "Failed to delete answer";
      setError(typeof msg === "string" ? msg : JSON.stringify(msg));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={`answer-card ${answer.source === "ai" ? "ai-answer" : ""}`}>
      <div className="answer-header">
        <span className="source-badge">{sourceLabels[answer.source]}</span>
        {answer.confidence != null && (
          <span className={`confidence ${answer.confidence < 0.5 ? "low-confidence" : ""}`}>
            Confidence: {Math.round(answer.confidence * 100)}%
            {answer.confidence < 0.5 && " ⚠️"}
          </span>
        )}
        {answer.source === "ai" && answer.reasoning_time_seconds != null && (
          <span className="reasoning-time">
            ⏱️ {answer.reasoning_time_seconds < 60
              ? `${answer.reasoning_time_seconds.toFixed(1)}s`
              : `${Math.floor(answer.reasoning_time_seconds / 60)}m ${Math.round(answer.reasoning_time_seconds % 60)}s`}
          </span>
        )}
        {answer.edited && <span className="edited-badge">(edited)</span>}
      </div>

      {editing ? (
        <div className="edit-form">
          <textarea value={editBody} onChange={(e) => setEditBody(e.target.value)} rows={4} />
          <div className="edit-actions">
            <button onClick={handleSaveEdit} disabled={loading}>
              {loading ? "Saving..." : "Save"}
            </button>
            <button className="btn-cancel" onClick={() => { setEditing(false); setEditBody(answer.body); }}>
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <div className="answer-body">
          <ReactMarkdown>{answer.body}</ReactMarkdown>
        </div>
      )}

      <div className="answer-footer">
        <span className="answer-date">
          {new Date(answer.created_at).toLocaleString()}
        </span>

        {/* Edit / Delete icon buttons (above like/dislike) */}
        {canManage && !editing && (
          <div className="answer-admin-actions">
            <button className="icon-btn" onClick={() => setEditing(true)} title="Edit">
              ✏️
            </button>
            {showDeleteConfirm ? (
              <span className="delete-confirm-inline">
                <button className="icon-btn icon-btn-danger" onClick={handleDelete} title="Confirm delete">
                  🗑️
                </button>
                <button className="icon-btn" onClick={() => setShowDeleteConfirm(false)} title="Cancel">
                  ✖️
                </button>
              </span>
            ) : (
              <button className="icon-btn" onClick={() => setShowDeleteConfirm(true)} title="Delete">
                🗑️
              </button>
            )}
          </div>
        )}

        {/* Like / Dislike */}
        <div className="rating-section">
          <div className="rating-stats">
            <span className={`stat-item ${helpfulCount > 0 ? "positive" : ""}`}>
              👍 {helpfulCount}
            </span>
            <span className={`stat-item ${notHelpfulCount > 0 ? "negative" : ""}`}>
              👎 {notHelpfulCount}
            </span>
          </div>

          <div className="rating-buttons">
            <button
              className={`rate-btn ${userRating === true ? "active" : ""}`}
              onClick={() => handleRate(true)}
              disabled={loading}
            >
              👍
            </button>
            <button
              className={`rate-btn ${userRating === false ? "active" : ""}`}
              onClick={() => handleRate(false)}
              disabled={loading}
            >
              👎
            </button>
          </div>
        </div>

        {/* User's persistent vote */}
        {userRating !== null && (
          <span className={`user-rating ${userRating ? "positive" : "negative"}`}>
            You voted: {userRating ? "👍" : "👎"}
          </span>
        )}

        {error && <span className="error-text">{error}</span>}
      </div>
    </div>
  );
}
