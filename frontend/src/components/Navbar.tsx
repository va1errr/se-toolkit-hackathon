/** Top navigation bar with auth-aware links. */

import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function Navbar() {
  const { user, isAuthenticated, isTA, logout } = useAuth();

  return (
    <nav className="navbar">
      <Link to="/" className="nav-brand">
        LabAssist
      </Link>
      <div className="nav-links">
        {isAuthenticated ? (
          <>
            {isTA && (
              <Link to="/ta/queue" className="nav-ta-queue">
                🔍 TA Queue
              </Link>
            )}
            <span className="nav-user">
              {user?.username} ({user?.role})
            </span>
            <button onClick={logout} className="nav-logout">
              Logout
            </button>
          </>
        ) : (
          <>
            <Link to="/login">Login</Link>
            <Link to="/register">Register</Link>
          </>
        )}
      </div>
    </nav>
  );
}
