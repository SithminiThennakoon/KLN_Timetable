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
  }
};

export const lecturerService = {
  getAll: async () => {
    const response = await fetch(`${LECTURER_API_BASE_URL}/`);
    if (!response.ok) {
      throw new Error('Failed to fetch lecturers');
    }
    return await response.json();
  }
};
