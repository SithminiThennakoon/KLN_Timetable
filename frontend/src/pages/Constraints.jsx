import React, { useEffect, useState } from "react";
import "../styles/App.css";
import "../styles/DatabaseManagement.css";
import axios from "axios";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000/api";

const gearIcon = (
  <svg height="32" width="32" viewBox="0 0 24 24" fill="currentColor" style={{marginRight: '10px'}}>
    <path d="M19.14,12.94c.04-.31.06-.62.06-.94s-.02-.63-.06-.94l2.03-1.58c.18-.14.23-.41,.12-.61l-1.92-3.32c-.11-.2-.35-.26-.55-.2l-2.39,.96c-.5-.38-1.05-.7-1.66-.94l-.36-2.53c-.03-.22-.22-.39-.45-.39h-3.84c-.23,0-.42,.16-.45,.39l-.36,2.53c-.61,.24-1.17,.56-1.66,.94l-2.39-.96c-.21-.07-.44,0-.55,.2l-1.92,3.32c-.11,.2-.06,.47,.12,.61l2.03,1.58c-.04,.31-.06,.62-.06,.94s.02,.63,.06,.94l-2.03,1.58c-.18,.14-.23,.41-.12,.61l1.92,3.32c.11,.2,.35,.26,.55,.20l2.39-.96c.5,.38,1.05,.7,1.66,.94l.36,2.53c.03,.22,.22,.39,.45,.39h3.84c.23,0,.42-.16,.45-.39l.36-2.53c.61-.24,1.17-.56,1.66-.94l2.39,.96c.21,.07,.44,0,.55-.20l1.92-3.32c.11-.2,.06-.47-.12-.61l-2.03-1.58ZM12,15.5c-1.93,0-3.5-1.57-3.5-3.5s1.57-3.5,3.5-3.5,3.5,1.57,3.5,3.5-1.57,3.5-3.5,3.5Z" />
  </svg>
);

const Constraints = () => {
  const [showAddModal, setShowAddModal] = useState(false);
  const [addForm, setAddForm] = useState({ name: '', description: '' });
  const [addError, setAddError] = useState('');
  const [addLoading, setAddLoading] = useState(false);
  const [constraints, setConstraints] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchConstraints();
  }, []);

  function fetchConstraints() {
    setLoading(true);
    axios.get(`${API_BASE}/constraints`).then(res => {
      setConstraints(res.data);
      setLoading(false);
    }).catch(err => {
      setError("Error fetching constraints");
      setLoading(false);
    });
  }

  function handleToggle(constraint) {
    axios.patch(`${API_BASE}/constraints/${constraint.Constraint_ID}`, { enabled: !constraint.enabled })
      .then(res => {
        setConstraints(constraints => constraints.map(c =>
          c.Constraint_ID === constraint.Constraint_ID ? {...c, enabled: res.data.enabled} : c
        ));
      });
  }

  function handleDelete(constraint) {
    if (!window.confirm(`Delete "${constraint.name}"?`)) return;
    axios.delete(`${API_BASE}/constraints/${constraint.Constraint_ID}`).then(() => {
      setConstraints(constraints => constraints.filter(c => c.Constraint_ID !== constraint.Constraint_ID));
    });
  }

  return (
    <div className="content">
      {/* Nav is globally included */}
      <div className="section-header">
        <h2>Constraints</h2>
        <button className="add-button" onClick={() => setShowAddModal(true)}>+ Add Constraint</button>
      </div>

      {showAddModal && (
        <div className="modal-overlay" onClick={() => setShowAddModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Add Constraint</h3>
              <button className="modal-close" onClick={() => setShowAddModal(false)}>×</button>
            </div>
            <div className="modal-body">
              <div className="form-group">
                <label>Name</label>
                <input
                  type="text"
                  name="name"
                  value={addForm.name}
                  onChange={e => setAddForm(f => ({ ...f, name: e.target.value }))}
                  placeholder="Enter constraint name"
                  required
                />
              </div>
              <div className="form-group">
                <label>Description</label>
                <input
                  type="text"
                  name="description"
                  value={addForm.description}
                  onChange={e => setAddForm(f => ({ ...f, description: e.target.value }))}
                  placeholder="Enter constraint description"
                />
              </div>
              {addError && <div style={{color: '#dc2626', marginTop: 4}}>{addError}</div>}
            </div>
            <div className="modal-footer">
              <button className="modal-btn cancel" onClick={() => setShowAddModal(false)}>Cancel</button>
              <button className="modal-btn save" onClick={async () => {
                setAddError('');
                if (!addForm.name.trim()) {
                  setAddError('Name is required.');
                  return;
                }
                setAddLoading(true);
                try {
                  await axios.post(`${API_BASE}/constraints`, { name: addForm.name.trim(), description: addForm.description.trim() });
                  setShowAddModal(false);
                  setAddForm({ name: '', description: '' });
                  fetchConstraints();
                } catch (err) {
                  setAddError('Failed to add constraint.');
                }
                setAddLoading(false);
              }} disabled={addLoading}>
                {addLoading ? 'Saving...' : 'Save'}
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="table-container">
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Description</th>
              <th>Enabled</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan="4">Loading...</td></tr>
            ) : error ? (
              <tr><td colSpan="4">{error}</td></tr>
            ) : constraints.length === 0 ? (
              <tr><td colSpan="4">No constraints found.</td></tr>
            ) : (
              constraints.map(constraint => (
                <tr key={constraint.Constraint_ID}>
                  <td>{constraint.name}</td>
                  <td>{constraint.description}</td>
                  <td>
                    <button className={"toggle-btn"} onClick={() => handleToggle(constraint)}>
                      {constraint.enabled ? "Yes" : "No"}
                    </button>
                  </td>
                  <td>
                    <button className="action-btn edit-btn" title="Edit/View">
                      <span className="edit-icon">✏️</span>
                    </button>
                    <button className="action-btn delete-btn" title="Delete" onClick={() => handleDelete(constraint)}>
                      <span className="delete-icon">🗑️</span>
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default Constraints;
