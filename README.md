# KLN Timetable System

A comprehensive web-based timetable generator and management system for the Faculty of Science, University of Kelaniya.

## Project Overview

This system generates optimized timetables considering:
- Lecturer availability and preferences
- Classroom capacity and availability
- Student class sizes
- Minimizing gaps and consecutive classes for both students and lecturers
- CP-SAT constraint solver for optimization

## Tech Stack

- **Frontend**: React.js 18
- **Backend**: FastAPI
- **Database**: MySQL
- **Optimization**: Google OR-Tools (CP-SAT)
- **Authentication**: JWT

## Project Structure

```
KLN_Timetable/
├── frontend/               # React.js application
│   ├── public/
│   ├── src/
│   │   ├── pages/         # Login, Dashboard pages
│   │   ├── components/    # Reusable components
│   │   ├── services/      # API services
│   │   └── styles/        # CSS styles
│   ├── package.json
│   └── .env
├── backend/               # FastAPI application
│   ├── app/
│   │   ├── models/        # SQLAlchemy models
│   │   ├── schemas/       # Pydantic schemas
│   │   ├── routes/        # API routes
│   │   ├── core/          # Config, security, database
│   │   └── main.py       # FastAPI app
│   ├── requirements.txt
│   ├── .env
│   └── main.py           # Entry point
└── README.md
```

## Features

### User Roles
1. **Admin**: Manage all departments, lecturers, classrooms, students, and generate timetables
2. **Department Head**: Manage department's timetable and view faculty timetable
3. **Lecturer**: View personal timetable and update availability
4. **Student**: View personal timetable and faculty timetable

### Current Features
- ✅ User authentication and authorization
- ✅ JWT-based token authentication
- ✅ Role-based access control
- ✅ Login/Dashboard UI
- ✅ MySQL database integration

### Upcoming Features
- Timetable generation with constraint solving
- Department management
- Classroom management
- Lecturer and Student management
- Availability management
- Timetable optimization using OR-Tools CP-SAT

## Installation & Setup

### Prerequisites
- Node.js (v14 or higher)
- Python 3.8+
- MySQL Server
- Git

### Backend Setup

1. Navigate to the backend directory:
```bash
cd backend
```

2. Create a virtual environment:
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Mac/Linux
python3 -m venv venv
source venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure database connection:
   - Edit `.env` file with your MySQL credentials
   - Default: `mysql://root:password@localhost:3306/kln_timetable`

5. Create the database:
```sql
CREATE DATABASE kln_timetable;
```

6. Run the backend server:
```bash
python main.py
```

The backend will start at `http://localhost:8000`

### Frontend Setup

1. Navigate to the frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

3. Configure API endpoint:
   - Edit `.env` file
   - Default: `REACT_APP_API_URL=http://localhost:8000`

4. Start the development server:
```bash
npm start
```

The frontend will open at `http://localhost:3000`

## Database Schema

### Users Table
```sql
CREATE TABLE users (
    id INT PRIMARY KEY AUTO_INCREMENT,
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    role ENUM('admin', 'department_head', 'lecturer', 'student') DEFAULT 'student',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

## API Endpoints

### Authentication
- `POST /api/auth/register` - Register new user
- `POST /api/auth/login` - Login and get JWT token
- `GET /api/auth/me` - Get current user info

## Test Credentials

After database setup, you can create test users:

```bash
# Admin user
Email: admin@kln.edu.lk
Password: admin123

# Lecturer user
Email: lecturer@kln.edu.lk
Password: lecturer123

# Student user
Email: student@kln.edu.lk
Password: student123
```

## Running the Application

### Terminal 1 - Backend:
```bash
cd backend
venv\Scripts\activate  # or source venv/bin/activate
python main.py
```

### Terminal 2 - Frontend:
```bash
cd frontend
npm start
```

Access the application at `http://localhost:3000`

## Development

### Adding New Routes (Backend)
1. Create a new route file in `backend/app/routes/`
2. Import and include the router in `app/main.py`

### Adding New Pages (Frontend)
1. Create a new component in `frontend/src/pages/`
2. Add route in `frontend/src/App.js`

## Environment Variables

### Backend (.env)
```
DATABASE_URL=mysql+pymysql://user:password@localhost:3306/kln_timetable
SECRET_KEY=your-secret-key-for-jwt
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

### Frontend (.env)
```
REACT_APP_API_URL=http://localhost:8000
```

## Git Workflow

- **Main Branch**: Production-ready code (Admin only)
- **Dev Branch**: Development branch for all developers
- **Feature Branches**: Create from dev for new features

```bash
# Create feature branch
git checkout -b feature/feature-name

# Commit changes
git add .
git commit -m "Add feature description"

# Push to dev
git push origin dev
```

## Troubleshooting

### MySQL Connection Error
- Verify MySQL service is running
- Check DATABASE_URL in .env matches your MySQL setup
- Ensure database exists: `CREATE DATABASE kln_timetable;`

### CORS Error
- Backend CORS is configured to accept all origins
- For production, update CORS origins in `backend/app/main.py`

### Port Already in Use
- Backend: Change port in `main.py` (default 8000)
- Frontend: Change port in package.json (default 3000)

## Support

For issues or questions, contact the development team or create an issue in the repository.

## License

© 2026 Faculty of Science, University of Kelaniya
