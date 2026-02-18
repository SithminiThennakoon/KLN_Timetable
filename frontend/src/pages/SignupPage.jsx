import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { register } from '../services/authService';
import '../styles/LoginPage.css';

function SignupPage({ onLogin }) {
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [name, setName] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState('student');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [usernameError, setUsernameError] = useState('');
  const [emailError, setEmailError] = useState('');
  const navigate = useNavigate();

  const validateUsername = (value) => {
    const pattern = /^[A-Z]{2}\/[A-Z]{4}\/[A-Z]{3}$/;
    return pattern.test(value);
  };

  const validateEmail = (value) => {
    const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailPattern.test(value);
  };

  const handleUsernameChange = (e) => {
    const value = e.target.value.toUpperCase();
    setUsername(value);
    if (value && !validateUsername(value)) {
      setUsernameError('Username must be in format **/****/*** (e.g., AB/CDEF/GHI)');
    } else {
      setUsernameError('');
    }
  };

  const handleEmailChange = (e) => {
    const value = e.target.value;
    setEmail(value);
    if (role === 'student') {
      if (!value.endsWith('@stuln.ac.lk')) {
        setEmailError('Student email must end with @stuln.ac.lk');
      } else {
        setEmailError('');
      }
    } else {
      if (value && !validateEmail(value)) {
        setEmailError('Please enter a valid email address');
      } else {
        setEmailError('');
      }
    }
  };

  const handleRoleChange = (e) => {
    setRole(e.target.value);
    if (e.target.value === 'student' && email && !email.endsWith('@stuln.ac.lk')) {
      setEmailError('Student email must end with @stuln.ac.lk');
    } else {
      setEmailError('');
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setUsernameError('');
    setEmailError('');

    if (!validateUsername(username)) {
      setUsernameError('Username must be in format **/****/*** (e.g., AB/CDEF/GHI)');
      return;
    }

    if (role === 'student' && !email.endsWith('@stuln.ac.lk')) {
      setEmailError('Student email must end with @stuln.ac.lk');
      return;
    }

    if (!validateEmail(email)) {
      setEmailError('Please enter a valid email address');
      return;
    }

    setLoading(true);

    try {
      const response = await register(username, email, password, name, role);
      const { access_token, role: userRole } = response.data;
      onLogin(access_token, userRole);
      navigate('/dashboard');
    } catch (err) {
      setError(err.response?.data?.detail || 'Registration failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-container">
      <div className="login-card">
        <div className="login-header">
          <h1>KLN Timetable</h1>
          <p>Faculty of Science, University of Kelaniya</p>
        </div>

        <form onSubmit={handleSubmit} className="login-form">
          <div className="form-group">
            <label htmlFor="username">Username</label>
            <input
              type="text"
              id="username"
              value={username}
              onChange={handleUsernameChange}
              required
              placeholder="AB/CDEF/GHI"
              maxLength={11}
            />
            {usernameError && <div className="field-error">{usernameError}</div>}
          </div>

          <div className="form-group">
            <label htmlFor="email">Email Address</label>
            <input
              type="email"
              id="email"
              value={email}
              onChange={handleEmailChange}
              required
              placeholder="Enter your email"
            />
            {emailError && <div className="field-error">{emailError}</div>}
          </div>

          <div className="form-group">
            <label htmlFor="name">Full Name</label>
            <input
              type="text"
              id="name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              placeholder="Enter your full name"
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
              placeholder="Enter your password"
              minLength={6}
            />
          </div>

          <div className="form-group">
            <label htmlFor="role">Role</label>
            <select
              id="role"
              value={role}
              onChange={handleRoleChange}
              required
            >
              <option value="student">Student</option>
              <option value="lecturer">Lecturer</option>
              <option value="department_head">Department Head</option>
              <option value="admin">Admin</option>
            </select>
          </div>

          {error && <div className="error-message">{error}</div>}

          <button type="submit" disabled={loading} className="login-button">
            {loading ? 'Creating Account...' : 'Sign Up'}
          </button>
        </form>

        <div className="login-footer">
          <p>© 2026 Faculty of Science, University of Kelaniya</p>
        </div>
      </div>
    </div>
  );
}

export default SignupPage;