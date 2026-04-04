/** Questions list page with filter and "Ask Question" button. */

import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { Question } from "../types";
import QuestionCard from "../components/QuestionCard";
import { questionsApi } from "../api/client";
import { useAuth } from "../context/AuthContext";

export default function QuestionsListPage() {
  const [questions, setQuestions] = useState<Question[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>("");
  const [error, setError] = useState("");
  const { isAuthenticated } = useAuth();

  const loadQuestions = async (statusFilter?: string) => {
    setLoading(true);
    try {
      const res = await questionsApi.list(statusFilter || undefined);
      setQuestions(res.data);
    } catch {
      setError("Failed to load questions");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadQuestions(filter);
  }, [filter]);

  return (
    <div className="questions-list-page">
      <div className="list-header">
        <h1>Questions</h1>
        {isAuthenticated && (
          <Link to="/questions/new" className="btn-primary">
            Ask Question
          </Link>
        )}
      </div>

      <div className="filters">
        {["", "analyzing", "open", "answered"].map((s) => (
          <button
            key={s}
            className={filter === s ? "active" : ""}
            onClick={() => setFilter(s)}
          >
            {s || "All"}
          </button>
        ))}
      </div>

      {error && <div className="error">{error}</div>}

      {loading ? (
        <p className="loading">Loading...</p>
      ) : questions.length === 0 ? (
        <p className="empty">No questions yet. {isAuthenticated && "Be the first to ask!"}</p>
      ) : (
        <div className="questions-grid">
          {questions.map((q) => (
            <QuestionCard key={q.id} question={q} />
          ))}
        </div>
      )}
    </div>
  );
}
