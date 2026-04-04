/** Main App component with routing and auth provider. */

import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "./context/AuthContext";
import Navbar from "./components/Navbar";
import LoginPage from "./pages/Login";
import RegisterPage from "./pages/Register";
import QuestionsListPage from "./pages/QuestionsList";
import QuestionDetailPage from "./pages/QuestionDetail";
import AskQuestionPage from "./pages/AskQuestion";
import TAQueuePage from "./pages/TAQueue";
import StatsPage from "./pages/Stats";
import "./styles/global.css";

/** Protects routes that require authentication. Redirects to /login if not authenticated. */
function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuth();
  return isAuthenticated ? <>{children}</> : <Navigate to="/login" replace />;
}

function AppRoutes() {
  return (
    <>
      <Navbar />
      <main className="main-content">
        <Routes>
          <Route path="/" element={<QuestionsListPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/questions/new" element={
            <ProtectedRoute><AskQuestionPage /></ProtectedRoute>
          } />
          <Route path="/ta/queue" element={
            <ProtectedRoute><TAQueuePage /></ProtectedRoute>
          } />
          <Route path="/questions/:id" element={<QuestionDetailPage />} />
          <Route path="/stats" element={<StatsPage />} />
        </Routes>
      </main>
    </>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  );
}
