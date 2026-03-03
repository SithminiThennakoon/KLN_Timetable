import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { login } from '../services/authService';
import { DEMO_CREDENTIALS } from '../config/demoCredentials';
import '../styles/LoginPage.css';

function LoginPage({ onLogin }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const response = await login(username, password);
      const { access_token, role } = response.data;
      onLogin(access_token, role);
      navigate('/dashboard');
    } catch (err) {
      setError(err.response?.data?.detail || 'Login failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-container">
      <div className="login-card">
        <div className="login-header">
          <h1>KelaniyaFOS</h1>
          <p>Timetable Management Portal</p>
        </div>

        <form onSubmit={handleSubmit} className="login-form">
          <div className="form-group">
            <label htmlFor="username">Username</label>
            <input
              type="text"
              id="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              placeholder={DEMO_CREDENTIALS.email}
            />
          </div>

          <div className="form-group">
            <label htmlFor="password">Password</label>
            <input
              type="password"
              id="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              placeholder={DEMO_CREDENTIALS.password}
            />
          </div>

          {error && <div className="error-message">{error}</div>}

          <button type="submit" disabled={loading} className="login-button">
            {loading ? 'Logging in...' : 'Log in'}
          </button>
        </form>

        <div className="helper-link">
          <button type="button" className="text-link">Lost password?</button>
        </div>

        <div className="demo-credentials">
          <span>Example login: {DEMO_CREDENTIALS.email} / {DEMO_CREDENTIALS.password}</span>
        </div>

        <div className="login-footer">
          <p>© 2026 Faculty of Science, University of Kelaniya</p>
        </div>
      </div>
    </div>
  );
}

export default LoginPage;
