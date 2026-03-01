from datetime import time
from sqlalchemy.orm import Session
from app.models.timeslot import Timeslot


def seed_timeslots(db: Session) -> int:
    existing = db.query(Timeslot).count()
    if existing > 0:
        return 0

    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    slots = [
        (time(8, 0), time(9, 0), False),
        (time(9, 0), time(10, 0), False),
        (time(10, 0), time(11, 0), False),
        (time(11, 0), time(12, 0), False),
        (time(12, 0), time(13, 0), True),
        (time(13, 0), time(14, 0), False),
        (time(14, 0), time(15, 0), False),
        (time(15, 0), time(16, 0), False),
        (time(16, 0), time(17, 0), False),
        (time(17, 0), time(18, 0), False),
    ]

    count = 0
    for day in days:
        for start, end, is_lunch in slots:
            db.add(Timeslot(day=day, start_time=start, end_time=end, is_lunch=is_lunch))
            count += 1
    db.commit()
    return count
