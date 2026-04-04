/** Question detail page with answers and TA reply form. */

import { useState, useEffect, FormEvent } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Question, Answer } from "../types";
import AnswerCard from "../components/AnswerCard";
import { questionsApi, answersApi } from "../api/client";
import { useAuth } from "../context/AuthContext";

export default function QuestionDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [question, setQuestion] = useState<Question | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const { isTA } = useAuth();
  const navigate = useNavigate();

  // TA answer form
  const [answerBody, setAnswerBody] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const loadQuestion = async () => {
    if (!id) return;
    setLoading(true);
    try {
      const res = await questionsApi.get(id);
      setQuestion(res.data);
    } catch {
      setError("Question not found");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadQuestion();
  }, [id]);

  // Poll for AI answer if question is still open (no AI answer yet)
  const hasAiAnswer = question?.answers?.some((a: Answer) => a.source === "ai");
  useEffect(() => {
    if (!id || hasAiAnswer) return;

    const poll = setInterval(() => {
      loadQuestion();
    }, 2000);

    return () => clearInterval(poll);
  }, [id, hasAiAnswer]);

  const handleTASubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!id || !answerBody.trim()) return;

    setSubmitting(true);
    try {
      await answersApi.add(id, answerBody);
      setAnswerBody("");
      await loadQuestion();
    } catch {
      setError("Failed to add answer");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) return <p className="loading">Loading...</p>;
  if (error && !question) return <div className="error">{error}</div>;
  if (!question) return null;

  return (
    <div className="question-detail-page">
      <button className="btn-back" onClick={() => navigate("/")}>
        ← Back to questions
      </button>

      <article className="question-full">
        <h1>{question.title}</h1>
        <p className="question-body">{question.body}</p>
        <div className="question-meta">
          <span className={`status ${question.status === "analyzing" ? "analyzing" : ""}`}>
            {question.status === "analyzing" ? "🤖 AI is analyzing..." : question.status}
          </span>
          <span className="date">
            {new Date(question.created_at).toLocaleString()}
          </span>
        </div>
      </article>

      <section className="answers-section">
        <h2>Answers ({question.answers?.length || 0})</h2>

        {!hasAiAnswer && !loading && (
          <div className="ai-analyzing">
            <div className="spinner"></div>
            <p>🤖 AI is reading the lab materials and crafting your answer...</p>
          </div>
        )}

        {question.answers?.length === 0 && hasAiAnswer && (
          <p className="empty">No answers yet.</p>
        )}

        {question.answers?.map((answer: Answer) => (
          <AnswerCard
            key={answer.id}
            answer={answer}
            onRate={loadQuestion}
          />
        ))}

        {isTA && (
          <form className="ta-answer-form" onSubmit={handleTASubmit}>
            <h3>Add TA Answer</h3>
            <textarea
              value={answerBody}
              onChange={(e) => setAnswerBody(e.target.value)}
              placeholder="Write your answer..."
              required
              rows={4}
            />
            <button type="submit" disabled={submitting || !answerBody.trim()}>
              {submitting ? "Submitting..." : "Submit Answer"}
            </button>
          </form>
        )}
      </section>

      {error && <div className="error">{error}</div>}
    </div>
  );
}
