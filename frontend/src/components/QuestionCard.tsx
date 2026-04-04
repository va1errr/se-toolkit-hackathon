/** Card showing a question summary in the list view. */

import { Link } from "react-router-dom";
import { Question } from "../types";

interface Props {
  question: Question;
}

export default function QuestionCard({ question }: Props) {
  const statusColors: Record<string, string> = {
    analyzing: "#f39c12",
    open: "#e74c3c",
    answered: "#27ae60",
  };

  return (
    <Link to={`/questions/${question.id}`} className="question-card">
      <div className="card-header">
        <h3>{question.title}</h3>
        <span
          className={`status-badge ${question.status === "analyzing" ? "analyzing" : ""}`}
          style={{ backgroundColor: statusColors[question.status] || "#ccc" }}
        >
          {question.status}
        </span>
      </div>
      <p className="card-body">{question.body.slice(0, 120)}...</p>
      <div className="card-footer">
        <span className="card-date">
          {new Date(question.created_at).toLocaleDateString()}
        </span>
        {question.ai_answer_id && (
          <span className="ai-badge">🤖 AI answered</span>
        )}
      </div>
    </Link>
  );
}
