import React, { useState, useEffect } from 'react';
import '../styles/DatabaseManagement.css';
import { groupService } from '../services/groupService';
import { semesterService } from '../services/semesterService';
import { courseService, lecturerService } from '../services/courseService';

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
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

const [showSemesterModal, setShowSemesterModal] = useState(false);
const [semesterFormData, setSemesterFormData] = useState({
  semesterName: '',
  academicYear: ''
});

// Courses and lecturers state
const [courses, setCourses] = useState([]);
const [lecturers, setLecturers] = useState([]);
const [coursesLoading, setCoursesLoading] = useState(false);
const [coursesError, setCoursesError] = useState(null);

// Lecturer modal state
const [showAddLecturerModal, setShowAddLecturerModal] = useState(false);
const [addLecturerForm, setAddLecturerForm] = useState({ name: '', email: '', max_teaching_hours: '' });
const [addLecturerError, setAddLecturerError] = useState(null);
const [addLecturerLoading, setAddLecturerLoading] = useState(false);

// Add Course modal state
const [showAddCourseModal, setShowAddCourseModal] = useState(false);
const [addCourseForm, setAddCourseForm] = useState({
  course_code: '',
  course_name: '',
  hours_per_week: '',
  lecturer_id: '',
  is_practical: false
});
const [addCourseError, setAddCourseError] = useState(null);
const [addCourseLoading, setAddCourseLoading] = useState(false);

useEffect(() => {
  fetchBatches();
  fetchSemesters();
  fetchCourses();
  fetchLecturers();
}, []);

const fetchCourses = async () => {
  try {
    setCoursesLoading(true);
    setCoursesError(null);
    const data = await courseService.getAll();
    setCourses(data);
  } catch (err) {
    setCoursesError(err.message);
    setCourses([]);
  } finally {
    setCoursesLoading(false);
  }
};

const fetchLecturers = async () => {
  try {
    const data = await lecturerService.getAll();
    setLecturers(data);
  } catch (err) {
    setLecturers([]);
  }
};

  const fetchBatches = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await groupService.getAll();
      setBatches(data);
    } catch (err) {
      setError(err.message);
      console.error('Error fetching batches:', err);
    } finally {
      setLoading(false);
    }
  };

  const fetchSemesters = async () => {
    try {
      const data = await semesterService.getAll();
      setSemesters(data);
    } catch (err) {
      setError(err.message);
      console.error('Error fetching semesters:', err);
    }
  };

  const handleSemesterInputChange = (e) => {
    const { name, value } = e.target;
    setSemesterFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handleAddSemester = async () => {
    console.log('Adding semester:', semesterFormData);
    if (!semesterFormData.semesterName || !semesterFormData.academicYear) {
      alert('Please fill in all fields');
      return;
    }
    try {
      const newSemester = await semesterService.create(semesterFormData);
      console.log('Semester created:', newSemester);
      await fetchSemesters();
      setShowSemesterModal(false);
      setSemesterFormData({
        semesterName: '',
        academicYear: ''
      });
      alert('Semester created successfully!');
    } catch (err) {
      console.error('Error creating semester:', err);
      setError(err.message);
      // Provide more specific error messages
      if (err.message.includes('Network error')) {
        alert('Network error: Could not connect to the server. Please ensure the backend is running and try again.');
      } else {
        alert('Failed to create semester: ' + (err.message || 'Unknown error occurred'));
      }
    }
  };

  const handleCloseSemesterModal = () => {
    setShowSemesterModal(false);
    setSemesterFormData({
      semesterName: '',
      academicYear: ''
    });
  };

  const tabs = [
    { id: 'batch', label: 'Batch' },
    { id: 'lecturers', label: 'Lecturer' },
    { id: 'courses', label: 'Courses' },
    { id: 'departments', label: 'Departments' },
    { id: 'rooms', label: 'Rooms' }
  ];

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handleAddBatch = async () => {
    // Validate form data
    if (!formData.groupName || !formData.semesterId || !formData.studentCount) {
      alert('Please fill in all required fields');
      return;
    }

    try {
      const newBatch = await groupService.create({
        groupName: formData.groupName,
        semesterId: parseInt(formData.semesterId),
        studentCount: parseInt(formData.studentCount)
      });

      await fetchBatches();
      setShowModal(false);
      setFormData({
        groupName: '',
        semesterId: '',
        studentCount: ''
      });
      alert('Batch created successfully!');
    } catch (err) {
      setError(err.message);
      console.error('Error creating batch:', err);
      alert('Failed to create batch: ' + (err.message || 'Unknown error'));
    }
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

  const handleUpdateBatch = async () => {
    try {
      await groupService.update(editingBatch.id, {
        groupName: formData.groupName,
        semesterId: parseInt(formData.semesterId),
        studentCount: parseInt(formData.studentCount)
      });

      await fetchBatches();
      setShowEditModal(false);
      setEditingBatch(null);
      setFormData({
        groupName: '',
        semesterId: '',
        studentCount: ''
      });
    } catch (err) {
      setError(err.message);
      console.error('Error updating batch:', err);
    }
  };

  const handleDeleteClick = (batch) => {
    setDeletingBatch(batch);
    setShowDeleteModal(true);
  };

  const handleConfirmDelete = async () => {
    try {
      await groupService.delete(deletingBatch.id);
      await fetchBatches();
      setSelectedBatches(selectedBatches.filter(id => id !== deletingBatch.id));
      setShowDeleteModal(false);
      setDeletingBatch(null);
    } catch (err) {
      setError(err.message);
      console.error('Error deleting batch:', err);
    }
  };

  const handleToggleSelection = (batchId) => {
    if (selectedBatches.includes(batchId)) {
      setSelectedBatches(selectedBatches.filter(id => id !== batchId));
    } else {
      setSelectedBatches([...selectedBatches, batchId]);
    }
  };

  const handleSaveToTimeTable = async () => {
    try {
      const result = await groupService.saveToTimetable(selectedBatches);
      console.log('Saved to timetable:', result);
      setShowSaveModal(false);
      setSelectedBatches([]);
      alert(`Successfully saved ${result.count} batches to timetable`);
    } catch (err) {
      setError(err.message);
      console.error('Error saving to timetable:', err);
    }
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

      <div className="content">
        <div className="db-section">
        <h2 className="db-management-header">Database Management</h2>
        <p className="db-management-subhead">Manage batches, courses, faculty, and rooms</p>
        <button className="db-add-btn" onClick={() => setShowSemesterModal(true)}>
          + Add Semester
        </button>
      </div>

        <div className="db-tabs">
          {tabs.map(tab => (
            <button
              key={tab.id}
              className={`db-tab-btn${activeTab === tab.id ? ' active' : ''}`}
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
                  <button className="db-add-btn" onClick={() => setShowModal(true)}>+ Add Batch</button>
                </div>
                <div className="table-container">
                  <table className="db-table batches-table">
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
                  <button className="db-cancel-btn" onClick={handleCancel}>
                    Cancel
                  </button>
                  <button
                    className="db-save-btn"
                    onClick={() => selectedBatches.length > 0 ? setShowSaveModal(true) : null}
                    disabled={selectedBatches.length === 0}
                  >
                    Save
                  </button>
                </div>
              </div>
            )}

            {activeTab === 'lecturers' && (
              <div className="lecturers-section">
                <div className="section-header">
                  <h3>Lecturers</h3>
                  <button className="db-add-btn" onClick={() => setShowAddLecturerModal(true)}>+ Add Lecturer</button>
                </div>
                <div className="table-container">
<table className="db-table lecturers-table">
  <thead>
    <tr>
      <th className="select-column">Select</th>
      <th>Name</th>
      <th>Email</th>
      <th>Max Teaching Hours</th>
      <th className="actions-column">Actions</th>
    </tr>
  </thead>
  <tbody>
                      {lecturers === undefined || lecturers.length === 0 ? (
                        <tr><td colSpan="4" className="no-data">No data available. Click "Add Lecturer" to create.</td></tr>
                      ) : (
                        lecturers.map(l => (
                          <tr key={l.id}>
                            <td className="select-column"><input type="checkbox" className="batch-checkbox" disabled /></td>
<td>{l.name}</td>
<td>{l.email}</td>
<td>{l.max_teaching_hours || '-'}</td>
<td className="actions-column">{/* (Future) Edit/Delete buttons here */}</td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {activeTab === 'courses' && (
  <>
    <div className="section-header">
      <h3>Courses</h3>
      <button className="add-button" onClick={() => setShowAddCourseModal(true)}>+ Add Course</button>
    </div>
    <div className="table-container">
      <table className="courses-table">
        <thead>
          <tr>
            <th className="select-column">Select</th>
            <th>Course Code</th>
            <th>Course Name</th>
            <th>Hours for Week</th>
            <th>Lecturer</th>
            <th>Practical</th>
            <th className="actions-column">Actions</th>
          </tr>
        </thead>
        <tbody>
          {coursesLoading ? (
            <tr>
              <td colSpan="7" className="no-data">Loading courses...</td>
            </tr>
          ) : coursesError ? (
            <tr>
              <td colSpan="7" className="no-data">Error: {coursesError}</td>
            </tr>
          ) : courses.length === 0 ? (
            <tr>
              <td colSpan="7" className="no-data">
                No data available. Click "Add Course" to create.
              </td>
            </tr>
          ) : (
            courses.map(course => (
              <tr key={course.id}>
                <td className="select-column">
                  <input type="checkbox" className="batch-checkbox" disabled />
                </td>
                <td>{course.course_code}</td>
                <td>{course.course_name}</td>
                <td>
                  {course.is_practical
                    ? course.practical_hours_per_week
                    : course.lecture_hours_per_week}
                </td>
                <td>{course.lecturer_name || course.lecturer?.name || ''}</td>
                <td>{course.is_practical ? 'Yes' : 'No'}</td>
                <td className="actions-column">
                  {/* Future: Add Edit/Delete here */}
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  </>
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

      {showAddLecturerModal && (
  <div className="modal-overlay" onClick={() => setShowAddLecturerModal(false)}>
    <div className="modal" onClick={e => e.stopPropagation()}>
      <div className="modal-header">
        <h3>Add Lecturer</h3>
        <button className="modal-close" onClick={() => setShowAddLecturerModal(false)}>×</button>
      </div>
      <div className="modal-body">
        <div className="form-group">
          <label>Name</label>
          <input type="text" name="name" value={addLecturerForm.name} onChange={e => setAddLecturerForm(f => ({ ...f, name: e.target.value }))} placeholder="Enter lecturer name" />
        </div>
        <div className="form-group">
          <label>Email</label>
          <input type="email" name="email" value={addLecturerForm.email} onChange={e => setAddLecturerForm(f => ({ ...f, email: e.target.value }))} placeholder="Enter lecturer email" />
        </div>
        <div className="form-group">
          <label>Max Teaching Hours</label>
          <input type="number" name="max_teaching_hours" min="0" value={addLecturerForm.max_teaching_hours} onChange={e => setAddLecturerForm(f => ({ ...f, max_teaching_hours: e.target.value }))} placeholder="Enter max hours" />
        </div>
        {addLecturerError && (<div className="form-error">{addLecturerError}</div>)}
      </div>
      <div className="modal-footer">
        <button className="modal-btn cancel" onClick={() => setShowAddLecturerModal(false)} disabled={addLecturerLoading}>Cancel</button>
        <button className="modal-btn save" onClick={async () => {
          setAddLecturerLoading(true);
          setAddLecturerError(null);
          if (!addLecturerForm.name || !addLecturerForm.email) {
            setAddLecturerError('Please fill all required fields');
            setAddLecturerLoading(false);
            return;
          }
          try {
            // Temporarily alert instead of API call. Add API call to add lecturer here (see below for note).
            // await lecturerService.create({ ...addLecturerForm });
            alert('Lecturer would be added with:\n' + JSON.stringify(addLecturerForm));
            setShowAddLecturerModal(false);
            setAddLecturerForm({ name: '', email: '' });
            // await fetchLecturers();
          } catch (err) {
            setAddLecturerError(err.message);
          } finally {
            setAddLecturerLoading(false);
          }
        }} disabled={addLecturerLoading}>Save</button>
      </div>
    </div>
  </div>
)}

{showAddCourseModal && (
  <div className="modal-overlay" onClick={() => setShowAddCourseModal(false)}>
    <div className="modal" onClick={e => e.stopPropagation()}>
      <div className="modal-header">
        <h3>Add Course</h3>
        <button className="modal-close" onClick={() => setShowAddCourseModal(false)}>×</button>
      </div>
      <div className="modal-body">
        <div className="form-group">
          <label>Course Code</label>
          <input type="text" name="course_code" value={addCourseForm.course_code} onChange={e => setAddCourseForm(f => ({ ...f, course_code: e.target.value }))} placeholder="Enter the course code" />
        </div>
        <div className="form-group">
          <label>Course Name</label>
          <input type="text" name="course_name" value={addCourseForm.course_name} onChange={e => setAddCourseForm(f => ({ ...f, course_name: e.target.value }))} placeholder="Enter the course name" />
        </div>
        <div className="form-group">
          <label>Hours for Week</label>
          <input type="number" name="hours_per_week" min="1" value={addCourseForm.hours_per_week} onChange={e => setAddCourseForm(f => ({ ...f, hours_per_week: e.target.value }))} placeholder="Enter hours (eg. 3)" />
        </div>
        <div className="form-group">
          <label>Lecturer</label>
          <select name="lecturer_id" value={addCourseForm.lecturer_id} onChange={e => setAddCourseForm(f => ({ ...f, lecturer_id: e.target.value }))}>
            <option value="">Select Lecturer</option>
            {lecturers.map(l => (
              <option key={l.id} value={l.id}>{l.name}</option>
            ))}
          </select>
        </div>
<div className="form-group practical-checkbox-group" style={{display: 'flex', alignItems: 'center', gap: '0.75rem', whiteSpace: 'nowrap'}}>
  <input type="checkbox" name="is_practical" id="is_practical" checked={addCourseForm.is_practical} onChange={e => setAddCourseForm(f => ({ ...f, is_practical: e.target.checked }))} />
  <label htmlFor="is_practical" style={{margin: 0, cursor: 'pointer', whiteSpace: 'nowrap', fontWeight: 500}}>
    Practical Course (Requires Laboratory)
  </label>
</div>
        {addCourseError && <div className="form-error">{addCourseError}</div>}
      </div>
      <div className="modal-footer">
        <button className="modal-btn cancel" onClick={() => setShowAddCourseModal(false)} disabled={addCourseLoading}>Cancel</button>
        <button className="modal-btn save" onClick={async () => {
          setAddCourseLoading(true);
          setAddCourseError(null);
          if (!addCourseForm.course_code || !addCourseForm.course_name || !addCourseForm.hours_per_week || !addCourseForm.lecturer_id) {
            setAddCourseError('Please fill all required fields');
            setAddCourseLoading(false);
            return;
          }
          try {
            await courseService.create({
              ...addCourseForm,
              hours_per_week: Number(addCourseForm.hours_per_week),
              lecturer_id: Number(addCourseForm.lecturer_id)
            });
            setShowAddCourseModal(false);
            setAddCourseForm({ course_code: '', course_name: '', hours_per_week: '', lecturer_id: '', is_practical: false });
            await fetchCourses();
          } catch (err) {
            setAddCourseError(err.message);
          } finally {
            setAddCourseLoading(false);
          }
        }} disabled={addCourseLoading}>Save</button>
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