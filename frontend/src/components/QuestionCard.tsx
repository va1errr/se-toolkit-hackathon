/** Card showing a question summary in the list view. */

import { Link } from "react-router-dom";
import { Question } from "../types";

interface Props {
  question: Question;
}

export default function QuestionCard({ question }: Props) {
  const statusConfig: Record<string, { color: string; label: string }> = {
    analyzing: { color: "#f39c12", label: "🤖 Analyzing" },
    open: { color: "#e74c3c", label: "🔍 In TA queue" },
    answered: { color: "#27ae60", label: "✅ Answered" },
  };

  const config = statusConfig[question.status] || { color: "#ccc", label: question.status };

  // Override label with answer_label for answered questions
  const displayLabel = (question as any).answer_label || config.label;

  return (
    <Link to={`/questions/${question.id}`} className="question-card">
      <div className="card-header">
        <h3>{question.title}</h3>
        <span
          className={`status-badge ${question.status === "analyzing" ? "analyzing" : ""}`}
          style={{ backgroundColor: config.color }}
        >
          {displayLabel}
        </span>
      </div>
      <p className="card-body">{question.body.slice(0, 120)}...</p>
      <div className="card-footer">
        <span className="card-date">
          {new Date(question.created_at).toLocaleDateString()}
        </span>
        {question.ai_answer_id && question.ai_reasoning_time_seconds != null && (
          <span className="ai-badge">
            🤖 AI ({question.ai_reasoning_time_seconds < 60
              ? `${question.ai_reasoning_time_seconds.toFixed(1)}s`
              : `${Math.floor(question.ai_reasoning_time_seconds / 60)}m ${Math.round(question.ai_reasoning_time_seconds % 60)}s`})
          </span>
        )}
      </div>
    </Link>
  );
}
