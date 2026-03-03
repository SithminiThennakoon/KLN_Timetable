const API_BASE_URL = 'http://localhost:8000/api/admin';

export const semesterService = {
  getAll: async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/semesters`);
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to fetch semesters');
      }
      return await response.json();
    } catch (error) {
      console.error('Error in getAll:', error);
      // Check if it's a network error
      if (error.name === 'TypeError' && error.message.includes('Failed to fetch')) {
        throw new Error('Network error: Could not connect to the server. Please check if the backend is running.');
      }
      throw error;
    }
  },

  create: async (semesterData) => {
    try {
      const response = await fetch(`${API_BASE_URL}/semesters`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(semesterData),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to create semester');
      }

      const data = await response.json();
      console.log('Semester created:', data);
      return data;
    } catch (error) {
      console.error('Error in create:', error);
      // Check if it's a network error
      if (error.name === 'TypeError' && error.message.includes('Failed to fetch')) {
        throw new Error('Network error: Could not connect to the server. Please check if the backend is running.');
      }
      throw new Error('Failed to create semester: ' + error.message);
    }
  }
};
