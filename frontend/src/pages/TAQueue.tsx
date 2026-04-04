/** TA review queue — shows questions with 👎 flagged AI answers. */

import { useState, useEffect, FormEvent } from "react";
import { Link } from "react-router-dom";
import { taApi } from "../api/client";
import { useAuth } from "../context/AuthContext";
import ReactMarkdown from "react-markdown";

interface FlaggedItem {
  question_id: string;
  title: string;
  body: string;
  status: string;
  question_created: string;
  ai_answer_id: string;
  ai_answer_body: string;
  ai_confidence: number | null;
  ai_edited: boolean;
  hidden: boolean;
  answer_created: string;
  thumbs_down: number;
  thumbs_up: number;
}

export default function TAQueuePage() {
  const { isTA, user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [flagged, setFlagged] = useState<FlaggedItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [answerBody, setAnswerBody] = useState("");
  const [activeQuestion, setActiveQuestion] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const loadFlagged = async () => {
    try {
      const res = await taApi.flagged();
      setFlagged(res.data);
    } catch {
      setError("Failed to load flagged answers");
    }
    setLoading(false);
  };

  useEffect(() => {
    loadFlagged();
    const interval = setInterval(loadFlagged, 3000);
    return () => clearInterval(interval);
  }, []);

  const handleSubmit = async (questionId: string, e: FormEvent) => {
    e.preventDefault();
    if (!answerBody.trim()) return;
    setSubmitting(true);
    try {
      await taApi.addAnswer(questionId, answerBody);
      setAnswerBody("");
      setActiveQuestion(null);
      await loadFlagged();
    } catch {
      setError("Failed to add answer");
    } finally {
      setSubmitting(false);
    }
  };

  const handleHide = async (questionId: string) => {
    try {
      await taApi.hideQuestion(questionId);
      setFlagged((prev) => prev.filter((q) => q.question_id !== questionId));
    } catch (err: any) {
      const status = err.response?.status;
      const detail = err.response?.data?.detail;
      if (status === 403) setError("Only admins can hide questions");
      else setError(detail || "Failed to hide question");
    }
  };

  const handleShow = async (questionId: string) => {
    try {
      await taApi.unhideQuestion(questionId);
      // Update local state: mark as not hidden (it'll stay in the list)
      setFlagged((prev) =>
        prev.map((q) =>
          q.question_id === questionId ? { ...q, hidden: false } : q
        )
      );
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to show question");
    }
  };

  if (!isTA) {
    return <div className="ta-queue-page"><p className="error">Access denied. TA role required.</p></div>;
  }

  return (
    <div className="ta-queue-page">
      <div className="queue-header">
        <h1>🔍 TA Review Queue</h1>
        <button className="btn-refresh" onClick={loadFlagged}>
          🔄 Refresh
        </button>
      </div>
      <p className="help-text">
        AI answers students rated 👎 unhelpful, plus AI answers with low confidence (status "open").
        Questions are auto-removed when a TA answer gets a 👍.
        {isAdmin && " Admins can hide questions from this view."}
      </p>

      {error && <div className="error">{error}</div>}

      {loading ? (
        <p className="loading">Loading...</p>
      ) : flagged.length === 0 ? (
        <p className="empty">✅ No flagged answers. All AI answers are performing well!</p>
      ) : (
        <div className="flagged-list">
          {flagged.map((item) => (
            <div key={item.question_id} className={`flagged-card ${item.hidden ? "hidden-card" : ""}`}>
              <div className="card-header">
                <Link to={`/questions/${item.question_id}`} className="question-link">
                  <h3>{item.title}</h3>
                </Link>
                <div className="rating-badges">
                  {item.hidden && <span className="badge badge-hidden">Hidden</span>}
                  <span className="badge thumbs-down">👎 {item.thumbs_down}</span>
                  <span className="badge confidence">
                    AI: {item.ai_confidence != null ? Math.round(item.ai_confidence * 100) : "?"}%
                  </span>
                </div>
              </div>

              <div className="card-body">
                <h4>Student's question:</h4>
                <p className="question-text">{item.body}</p>

                <h4>🤖 AI answer{item.ai_edited ? " (edited)" : ""}:</h4>
                <div className="ai-answer">
                  <ReactMarkdown>{item.ai_answer_body}</ReactMarkdown>
                </div>
              </div>

              <div className="card-actions">
                <button className="btn-reply" onClick={() => { setActiveQuestion(item.question_id); setAnswerBody(""); }}>
                  💬 Add TA Answer
                </button>
                {isAdmin && (
                  item.hidden ? (
                    <button className="btn-show" onClick={() => handleShow(item.question_id)} title="Show in queue">
                      👁️ Show
                    </button>
                  ) : (
                    <button className="btn-hide" onClick={() => handleHide(item.question_id)} title="Hide from queue">
                      👁️‍🗨️ Hide
                    </button>
                  )
                )}
              </div>

              {activeQuestion === item.question_id && (
                <form className="ta-answer-form" onSubmit={(e) => handleSubmit(item.question_id, e)}>
                  <h4>✏️ Your answer:</h4>
                  <textarea
                    value={answerBody}
                    onChange={(e) => setAnswerBody(e.target.value)}
                    placeholder="Write a corrected answer..."
                    required
                    rows={4}
                  />
                  <div className="form-actions">
                    <button type="submit" disabled={submitting}>
                      {submitting ? "Submitting..." : "Submit Answer"}
                    </button>
                    <button type="button" className="btn-cancel" onClick={() => setActiveQuestion(null)}>
                      Cancel
                    </button>
                  </div>
                </form>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
