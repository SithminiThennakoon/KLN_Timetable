const API_BASE_URL = 'http://localhost:8000/api/admin';

export const roomService = {
  getAll: async () => {
    const response = await fetch(`${API_BASE_URL}/rooms`);
    if (!response.ok) {
      const error = await response.json();
      const detail = error?.detail;
      const message = Array.isArray(detail)
        ? detail.map(item => item?.msg || JSON.stringify(item)).join(', ')
        : typeof detail === 'string'
          ? detail
          : detail
            ? JSON.stringify(detail)
            : 'Failed to fetch rooms';
      throw new Error(message);
    }
    return await response.json();
  },

  create: async (roomData) => {
    const response = await fetch(`${API_BASE_URL}/rooms`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(roomData),
    });

    if (!response.ok) {
      const error = await response.json();
      const detail = error?.detail;
      const message = Array.isArray(detail)
        ? detail.map(item => item?.msg || JSON.stringify(item)).join(', ')
        : typeof detail === 'string'
          ? detail
          : detail
            ? JSON.stringify(detail)
            : 'Failed to create room';
      throw new Error(message);
    }

    return await response.json();
  },

  update: async (roomId, roomData) => {
    const response = await fetch(`${API_BASE_URL}/rooms/${roomId}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(roomData),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to update room');
    }

    return await response.json();
  },

  delete: async (roomId) => {
    const response = await fetch(`${API_BASE_URL}/rooms/${roomId}`, {
      method: 'DELETE',
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to delete room');
    }

    return await response.json();
  }
};
