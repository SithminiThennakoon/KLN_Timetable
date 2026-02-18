from app.core.database import engine, Base, SessionLocal
from app.models.user import User
from app.models.student_login import StudentLogin

def recreate_tables():
    print("Dropping all tables...")
    Base.metadata.drop_all(bind=engine)
    
    print("Creating all tables...")
    Base.metadata.create_all(bind=engine)
    
    print("Tables created successfully!")

if __name__ == "__main__":
    recreate_tables()
