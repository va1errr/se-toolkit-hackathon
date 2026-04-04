/** TA review queue — shows questions with 👎 flagged AI answers. */

import { useState, useEffect, FormEvent } from "react";
import { Link } from "react-router-dom";
import { answersApi } from "../api/client";
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
  answer_created: string;
  thumbs_down: number;
  thumbs_up: number;
}

export default function TAQueuePage() {
  const { isTA } = useAuth();
  const [flagged, setFlagged] = useState<FlaggedItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [answerBody, setAnswerBody] = useState("");
  const [activeQuestion, setActiveQuestion] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const loadFlagged = async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/v1/ta/flagged", {
        headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
      });
      if (res.ok) setFlagged(await res.json());
    } catch {
      setError("Failed to load flagged answers");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadFlagged();
  }, []);

  const handleSubmit = async (questionId: string, e: FormEvent) => {
    e.preventDefault();
    if (!answerBody.trim()) return;

    setSubmitting(true);
    try {
      await answersApi.add(questionId, answerBody);
      setAnswerBody("");
      setActiveQuestion(null);
      await loadFlagged();
    } catch {
      setError("Failed to add answer");
    } finally {
      setSubmitting(false);
    }
  };

  if (!isTA) {
    return <div className="ta-queue-page"><p className="error">Access denied. TA role required.</p></div>;
  }

  return (
    <div className="ta-queue-page">
      <h1>🔍 TA Review Queue</h1>
      <p className="help-text">
        Questions with AI answers that students rated 👎 unhelpful.
      </p>

      {error && <div className="error">{error}</div>}

      {loading ? (
        <p className="loading">Loading...</p>
      ) : flagged.length === 0 ? (
        <p className="empty">✅ No flagged answers. All AI answers are performing well!</p>
      ) : (
        <div className="flagged-list">
          {flagged.map((item) => (
            <div key={item.question_id} className="flagged-card">
              <div className="card-header">
                <Link to={`/questions/${item.question_id}`} className="question-link">
                  <h3>{item.title}</h3>
                </Link>
                <div className="rating-badges">
                  <span className="badge thumbs-down">👎 {item.thumbs_down}</span>
                  <span className="badge thumbs-up">👍 {item.thumbs_up}</span>
                  <span className="badge confidence">
                    AI confidence: {item.ai_confidence != null ? Math.round(item.ai_confidence * 100) : "?"}%
                  </span>
                </div>
              </div>

              <div className="card-body">
                <h4>Student's question:</h4>
                <p className="question-text">{item.body}</p>

                <h4>🤖 AI answer:</h4>
                <div className="ai-answer">
                  <ReactMarkdown>{item.ai_answer_body}</ReactMarkdown>
                </div>
              </div>

              {activeQuestion === item.question_id ? (
                <form
                  className="ta-answer-form"
                  onSubmit={(e) => handleSubmit(item.question_id, e)}
                >
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
                    <button
                      type="button"
                      className="btn-cancel"
                      onClick={() => setActiveQuestion(null)}
                    >
                      Cancel
                    </button>
                  </div>
                </form>
              ) : (
                <button
                  className="btn-reply"
                  onClick={() => {
                    setActiveQuestion(item.question_id);
                    setAnswerBody("");
                  }}
                >
                  ✏️ Add TA Answer
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
