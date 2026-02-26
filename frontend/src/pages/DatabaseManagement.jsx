import React, { useState, useEffect } from 'react';
import '../styles/DatabaseManagement.css';
import { groupService } from '../services/groupService';
import { semesterService } from '../services/semesterService';

const DatabaseManagement = () => {
  const [activeTab, setActiveTab] = useState('batch');
  const [showModal, setShowModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [showSaveModal, setShowSaveModal] = useState(false);
  const [editingBatch, setEditingBatch] = useState(null);
  const [deletingBatch, setDeletingBatch] = useState(null);
  const [formData, setFormData] = useState({
    groupName: '',
    semesterId: '',
    studentCount: ''
  });

  const [batches, setBatches] = useState([]);
  const [selectedBatches, setSelectedBatches] = useState([]);
  const [semesters, setSemesters] = useState([]);

  const [showSemesterModal, setShowSemesterModal] = useState(false);
  const [semesterFormData, setSemesterFormData] = useState({
    semesterName: '',
    academicYear: ''
  });

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handleAddBatch = () => {
    const semester = semesters.find(s => s.id === parseInt(formData.semesterId));

    const newBatch = {
      id: Date.now(),
      groupName: formData.groupName,
      academicYear: semester?.academicYear || '',
      semesterName: semester?.name || '',
      studentCount: formData.studentCount
    };

    setBatches([...batches, newBatch]);
    setShowModal(false);
    setFormData({
      groupName: '',
      semesterId: '',
      studentCount: ''
    });
  };

  const handleSemesterInputChange = (e) => {
    const { name, value } = e.target;
    setSemesterFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handleAddSemester = async () => {
    try {
      const newSemester = await semesterService.create(semesterFormData);
      await fetchSemesters();
      setShowSemesterModal(false);
      setSemesterFormData({
        semesterName: '',
        academicYear: ''
      });
    } catch (err) {
      console.error('Error creating semester:', err);
    }
  };

  const handleCloseSemesterModal = () => {
    setShowSemesterModal(false);
    setSemesterFormData({
      semesterName: '',
      academicYear: ''
    });
  };

  const handleEditClick = (batch) => {
    setEditingBatch(batch);
    const semester = semesters.find(s => s.name === batch.semesterName);

    setFormData({
      groupName: batch.groupName,
      semesterId: semester?.id?.toString() || '',
      studentCount: batch.studentCount
    });
    setShowEditModal(true);
  };

  const handleUpdateBatch = () => {
    const semester = semesters.find(s => s.id === parseInt(formData.semesterId));

    const updatedBatches = batches.map(batch =>
      batch.id === editingBatch.id
        ? {
            ...batch,
            groupName: formData.groupName,
            academicYear: semester?.academicYear || batch.academicYear,
            semesterName: semester?.name || batch.semesterName,
            studentCount: formData.studentCount
          }
        : batch
    );

    setBatches(updatedBatches);
    setShowEditModal(false);
    setEditingBatch(null);
    setFormData({
      groupName: '',
      semesterId: '',
      studentCount: ''
    });
  };

  const handleDeleteClick = (batch) => {
    setDeletingBatch(batch);
    setShowDeleteModal(true);
  };

  const handleConfirmDelete = () => {
    const updatedBatches = batches.filter(batch => batch.id !== deletingBatch.id);
    setBatches(updatedBatches);
    setSelectedBatches(selectedBatches.filter(id => id !== deletingBatch.id));
    setShowDeleteModal(false);
    setDeletingBatch(null);
  };

  const handleToggleSelection = (batchId) => {
    if (selectedBatches.includes(batchId)) {
      setSelectedBatches(selectedBatches.filter(id => id !== batchId));
    } else {
      setSelectedBatches([...selectedBatches, batchId]);
    }
  };

  const handleSaveToTimeTable = () => {
    const selectedBatchData = batches.filter(batch => selectedBatches.includes(batch.id));
    console.log('Saving to time_table:', selectedBatchData);
    setShowSaveModal(false);
    setSelectedBatches([]);
  };

  const handleCancel = () => {
    setSelectedBatches([]);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handleCloseModal = () => {
    setShowModal(false);
    setShowEditModal(false);
    setShowDeleteModal(false);
    setShowSaveModal(false);
    setFormData({
      groupName: '',
      semesterId: '',
      studentCount: ''
    });
    setEditingBatch(null);
    setDeletingBatch(null);
  };

  return (
    <div className="database-management">
      <div className="header">
        <div className="logo">
          <img src="https://placehold.co/40x40/4a5568/ffffff?text=FS" alt="Faculty of Science logo" />
          <div className="title">
            <h1>Faculty of Science</h1>
            <p>University of Kelaniya - Timetable Generator</p>
          </div>
        </div>
        <nav className="main-nav">
          <ul>
            <li className="active">Database</li>
            <li>Constraints</li>
            <li>Generate</li>
            <li>View</li>
          </ul>
        </nav>
      </div>

      <div className="content">
        <div className="section-header">
          <h2>Database Management</h2>
          <p>Manage batches, courses, faculty, and rooms</p>
          <button className="add-button add-semester-button" onClick={() => setShowSemesterModal(true)}>
            + Add Semester
          </button>
        </div>

        <div className="tabs">
          <div className="tab-container">
            {tabs.map(tab => (
              <button
                key={tab.id}
                className={`tab ${activeTab === tab.id ? 'active' : ''}`}
                onClick={() => setActiveTab(tab.id)}
              >
                {tab.label}
              </button>
            ))}
          </div>

          <div className="tab-content">
            {activeTab === 'batch' && (
              <div className="batches-section">
                <div className="section-header">
                  <h3>Batches</h3>
                  <button className="add-button" onClick={() => setShowModal(true)}>+ Add Batch</button>
                </div>
                <div className="table-container">
                  <table className="batches-table">
                    <thead>
                      <tr>
                        <th className="select-column">Select</th>
                        <th>Batch Name</th>
                        <th>Academic Year</th>
                        <th>Semester</th>
                        <th>Strength</th>
                        <th className="actions-column">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {batches.length === 0 ? (
                        <tr>
                          <td colSpan="6" className="no-data">
                            No data available. Click "Add Batch" to create.
                          </td>
                        </tr>
                      ) : (
                        batches.map(batch => (
                          <tr key={batch.id} className={selectedBatches.includes(batch.id) ? 'selected-row' : ''}>
                            <td className="select-column">
                              <input
                                type="checkbox"
                                checked={selectedBatches.includes(batch.id)}
                                onChange={() => handleToggleSelection(batch.id)}
                                className="batch-checkbox"
                              />
                            </td>
                            <td>{batch.groupName}</td>
                            <td>{batch.academicYear}</td>
                            <td>{batch.semesterName}</td>
                            <td>{batch.studentCount}</td>
                            <td className="actions-column">
                              <button className="action-btn edit-btn" onClick={() => handleEditClick(batch)}>
                                <span className="edit-icon">✎</span>
                              </button>
                              <button className="action-btn delete-btn" onClick={() => handleDeleteClick(batch)}>
                                <span className="delete-icon">🗑</span>
                              </button>
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
                <div className="bottom-actions">
                  <button className="bottom-btn cancel" onClick={handleCancel}>
                    Cancel
                  </button>
                  <button
                    className="bottom-btn save"
                    onClick={() => selectedBatches.length > 0 ? setShowSaveModal(true) : null}
                    disabled={selectedBatches.length === 0}
                  >
                    Save
                  </button>
                </div>
              </div>
            )}

            {activeTab === 'courses' && (
              <div className="courses-section">
                <div className="section-header">
                  <h3>Courses</h3>
                  <button className="add-button">+ Add Course</button>
                </div>
                <div className="table-container">
                  <table className="courses-table">
                    <thead>
                      <tr>
                        <th>Course Code</th>
                        <th>Type</th>
                        <th>Course Name</th>
                        <th>Credits</th>
                        <th>Hours for Week</th>
                        <th>Lecturer</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr>
                        <td colSpan="6" className="no-data">
                          No data available. Click "Add" to create.
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {activeTab === 'departments' && (
              <div className="departments-section">
                <div className="section-header">
                  <h3>Departments</h3>
                  <button className="add-button">+ Add Department</button>
                </div>
                <div className="table-container">
                  <table className="departments-table">
                    <thead>
                      <tr>
                        <th>Departments</th>
                        <th>Departments</th>
                        <th>Departments</th>
                        <th>Departments</th>
                        <th>Departments</th>
                        <th>Departments</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr>
                        <td colSpan="6" className="no-data">
                          No data available. Click "Add" to create.
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {activeTab === 'rooms' && (
              <div className="rooms-section">
                <div className="section-header">
                  <h3>Rooms</h3>
                  <button className="add-button">+ Add Room</button>
                </div>
                <div className="table-container">
                  <table className="rooms-table">
                    <thead>
                      <tr>
                        <th>Rooms</th>
                        <th>Rooms</th>
                        <th>Rooms</th>
                        <th>Rooms</th>
                        <th>Rooms</th>
                        <th>Rooms</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr>
                        <td colSpan="6" className="no-data">
                          No data available. Click "Add" to create.
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {showModal && (
        <div className="modal-overlay" onClick={handleCloseModal}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Add Batch</h3>
              <button className="modal-close" onClick={handleCloseModal}>×</button>
            </div>
            <div className="modal-body">
              <div className="form-group">
                <label>Batch Name</label>
                <input
                  type="text"
                  name="groupName"
                  value={formData.groupName}
                  onChange={handleInputChange}
                  placeholder="Enter batch name (e.g., 21/22)"
                />
              </div>
              <div className="form-group">
                <label>Semester</label>
                <select
                  name="semesterId"
                  value={formData.semesterId}
                  onChange={handleInputChange}
                  className="batch-select"
                >
                  <option value="">Select Semester</option>
                  {semesters.map(semester => (
                    <option key={semester.id} value={semester.id}>
                      {semester.name} ({semester.academicYear})
                    </option>
                  ))}
                </select>
              </div>
              <div className="form-group">
                <label>Student Count (Strength)</label>
                <input
                  type="number"
                  name="studentCount"
                  value={formData.studentCount}
                  onChange={handleInputChange}
                  placeholder="Enter number of students"
                  min="1"
                />
              </div>
            </div>
            <div className="modal-footer">
              <button className="modal-btn cancel" onClick={handleCloseModal}>Cancel</button>
              <button className="modal-btn save" onClick={handleAddBatch}>Save</button>
            </div>
          </div>
        </div>
      )}

      {showEditModal && (
        <div className="modal-overlay" onClick={handleCloseModal}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Edit Batch</h3>
              <button className="modal-close" onClick={handleCloseModal}>×</button>
            </div>
            <div className="modal-body">
              <div className="form-group">
                <label>Batch Name</label>
                <input
                  type="text"
                  name="groupName"
                  value={formData.groupName}
                  onChange={handleInputChange}
                  placeholder="Enter batch name"
                />
              </div>
              <div className="form-group">
                <label>Semester</label>
                <select
                  name="semesterId"
                  value={formData.semesterId}
                  onChange={handleInputChange}
                  className="batch-select"
                >
                  <option value="">Select Semester</option>
                  {semesters.map(semester => (
                    <option key={semester.id} value={semester.id}>
                      {semester.name} ({semester.academicYear})
                    </option>
                  ))}
                </select>
              </div>
              <div className="form-group">
                <label>Student Count (Strength)</label>
                <input
                  type="number"
                  name="studentCount"
                  value={formData.studentCount}
                  onChange={handleInputChange}
                  placeholder="Enter number of students"
                  min="1"
                />
              </div>
            </div>
            <div className="modal-footer">
              <button className="modal-btn cancel" onClick={handleCloseModal}>Cancel</button>
              <button className="modal-btn save" onClick={handleUpdateBatch}>Update</button>
            </div>
          </div>
        </div>
      )}

      {showDeleteModal && (
        <div className="modal-overlay" onClick={() => setShowDeleteModal(false)}>
          <div className="modal confirm-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Confirm Delete</h3>
              <button className="modal-close" onClick={() => setShowDeleteModal(false)}>×</button>
            </div>
            <div className="modal-body">
              <p className="confirm-message">
                Are you sure you want to delete batch "{deletingBatch?.groupName}"? This action cannot be undone.
              </p>
            </div>
            <div className="modal-footer">
              <button className="modal-btn cancel" onClick={() => setShowDeleteModal(false)}>Cancel</button>
              <button className="modal-btn delete" onClick={handleConfirmDelete}>Delete</button>
            </div>
          </div>
        </div>
      )}

      {showSaveModal && (
        <div className="modal-overlay" onClick={() => setShowSaveModal(false)}>
          <div className="modal confirm-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Save</h3>
              <button className="modal-close" onClick={() => setShowSaveModal(false)}>×</button>
            </div>
            <div className="modal-body">
              <p className="confirm-message">
                Are you sure you want to save {selectedBatches.length} selected batch(es)? This will create entries in time_table using group_ID.
              </p>
            </div>
            <div className="modal-footer">
              <button className="modal-btn cancel" onClick={() => setShowSaveModal(false)}>Cancel</button>
              <button className="modal-btn save" onClick={handleSaveToTimeTable}>Confirm</button>
            </div>
          </div>
        </div>
      )}

      {showSemesterModal && (
        <div className="modal-overlay" onClick={handleCloseSemesterModal}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Add Semester</h3>
              <button className="modal-close" onClick={handleCloseSemesterModal}>×</button>
            </div>
            <div className="modal-body">
              <div className="form-group">
                <label>Semester Name</label>
                <input
                  type="text"
                  name="semesterName"
                  value={semesterFormData.semesterName}
                  onChange={handleSemesterInputChange}
                  placeholder="Enter semester name (e.g., Semester 1)"
                />
              </div>
              <div className="form-group">
                <label>Academic Year</label>
                <input
                  type="text"
                  name="academicYear"
                  value={semesterFormData.academicYear}
                  onChange={handleSemesterInputChange}
                  placeholder="Enter academic year (e.g., 2024/2025)"
                />
              </div>
            </div>
            <div className="modal-footer">
              <button className="modal-btn cancel" onClick={handleCloseSemesterModal}>Cancel</button>
              <button className="modal-btn save" onClick={handleAddSemester}>Save</button>
            </div>
          </div>
        </div>
      )}
     </div>
   );
 };

export default DatabaseManagement;