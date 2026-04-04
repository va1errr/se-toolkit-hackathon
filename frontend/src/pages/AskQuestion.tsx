/** Create new question page with semantic duplicate detection. */

import { useState, useEffect, FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { Link } from "react-router-dom";
import { questionsApi } from "../api/client";

interface SimilarQuestion {
  id: string;
  title: string;
  body: string;
  status: string;
  similarity: number;
}

export default function AskQuestionPage() {
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [similar, setSimilar] = useState<SimilarQuestion[]>([]);
  const [searching, setSearching] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const navigate = useNavigate();

  // Search for similar questions as user types
  useEffect(() => {
    if (title.length < 5) {
      setSimilar([]);
      return;
    }

    const timer = setTimeout(async () => {
      setSearching(true);
      try {
        const res = await fetch(
          `/api/v1/questions/search?q=${encodeURIComponent(title)}`
        );
        if (res.ok) {
          const data = await res.json();
          // Only show questions with decent similarity
          setSimilar(data.filter((q: any) => q.similarity > 0.3));
        }
      } catch {
        // Ignore search errors
      } finally {
        setSearching(false);
      }
    }, 500); // Debounce

    return () => clearTimeout(timer);
  }, [title]);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    try {
      const res = await questionsApi.create(title, body);
      navigate(`/questions/${res.data.id}`);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to create question");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="ask-question-page">
      <h1>Ask a Question</h1>
      <p className="help-text">
        Your question will be answered instantly by AI based on lab materials.
      </p>

      <form onSubmit={handleSubmit}>
        {error && <div className="error">{error}</div>}

        <div className="form-group">
          <label>Title</label>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Brief description of your question"
            required
            autoFocus
            maxLength={200}
          />
          <span className="char-count">{title.length}/200</span>
        </div>

        {/* Similar questions suggestions */}
        {similar.length > 0 && (
          <div className="similar-questions">
            <h3>🔍 Similar questions (consider these first):</h3>
            <ul>
              {similar.map((q) => (
                <li key={q.id}>
                  <Link to={`/questions/${q.id}`}>{q.title}</Link>
                  <span className="similarity-badge">
                    {Math.round(q.similarity * 100)}% match
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
        {searching && <p className="loading">Searching for similar questions...</p>}

        <div className="form-group">
          <label>Details</label>
          <textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            placeholder="Describe your problem in detail..."
            required
            rows={6}
          />
        </div>

        <div className="form-actions">
          <button type="submit" disabled={loading}>
            {loading ? "Submitting..." : "Post Question"}
          </button>
          <button
            type="button"
            className="btn-cancel"
            onClick={() => navigate(-1)}
          >
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}
