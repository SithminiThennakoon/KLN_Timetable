const COURSE_API_BASE_URL = 'http://localhost:8000/api/courses';
const LECTURER_API_BASE_URL = 'http://localhost:8000/api/lecturers';

export const courseService = {
  getAll: async () => {
    const response = await fetch(`${COURSE_API_BASE_URL}/`);
    if (!response.ok) {
      throw new Error('Failed to fetch courses');
    }
    return await response.json();
  },

  create: async (courseData) => {
    const response = await fetch(`${COURSE_API_BASE_URL}/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(courseData),
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to create course');
    }
    return await response.json();
  },

  update: async (courseId, courseData) => {
    const response = await fetch(`${COURSE_API_BASE_URL}/${courseId}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(courseData),
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to update course');
    }
    return await response.json();
  },

  delete: async (courseId) => {
    const response = await fetch(`${COURSE_API_BASE_URL}/${courseId}`, {
      method: 'DELETE',
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to delete course');
    }
    return await response.json();
  }
};

export const lecturerService = {
  getAll: async () => {
    const response = await fetch(`${LECTURER_API_BASE_URL}/`);
    if (!response.ok) {
      const text = await response.text();
      let error;
      try {
        const json = JSON.parse(text);
        error = json.detail || JSON.stringify(json);
      } catch {
        error = text || 'Failed to fetch lecturers';
      }
      throw new Error(error);
    }
    const text = await response.text();
    return text ? JSON.parse(text) : [];
  },

  create: async (lecturerData) => {
    const response = await fetch(`${LECTURER_API_BASE_URL}/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(lecturerData),
    });

    if (!response.ok) {
      const text = await response.text();
      let error;
      try {
        const json = JSON.parse(text);
        error = json.detail || JSON.stringify(json);
      } catch {
        error = text || 'Failed to create lecturer';
      }
      throw new Error(error);
    }

    const text = await response.text();
    return text ? JSON.parse(text) : {};
  },

  delete: async (lecturerId) => {
    const response = await fetch(`${LECTURER_API_BASE_URL}/${lecturerId}`, {
      method: 'DELETE',
    });

    if (!response.ok) {
      const text = await response.text();
      let error;
      try {
        const json = JSON.parse(text);
        error = json.detail || JSON.stringify(json);
      } catch {
        error = text || 'Failed to delete lecturer';
      }
      throw new Error(error);
    }

    const text = await response.text();
    return text ? JSON.parse(text) : {};
  },

  update: async (lecturerId, lecturerData) => {
    const response = await fetch(`${LECTURER_API_BASE_URL}/${lecturerId}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(lecturerData),
    });

    if (!response.ok) {
      const text = await response.text();
      let error;
      try {
        const json = JSON.parse(text);
        error = json.detail || JSON.stringify(json);
      } catch {
        error = text || 'Failed to update lecturer';
      }
      throw new Error(error);
    }

    const text = await response.text();
    return text ? JSON.parse(text) : {};
  }
};
