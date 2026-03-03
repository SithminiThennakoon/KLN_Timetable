okay here is the deal

i am creating a timetable generator app for university of kelaniya science faculty 

this app should be able to generate timetables for the whole faculty 


- the lecture halls available for science faculty . the types of lectures or practical those halls can accommodate (e.g. lecture halls, computer labs, science labs, etc.) . For example physics lab can only be used for physics practicals, while a lecture hall can be used for lectures of any module. for each lecture hall there is a number of students it can accommodate. 
- the lecturers . we will have to get the list of lecturers and the modules they teach. but this is not simple as recoding the module and the lectuere because some modules are taught by multiple lecturers. for example for some modules first few weeks will be taught by one lecturer and the rest of the weeks will be taught by another lecturer. or sometimes 2h per weeks will be taught by one lecturer and 1h per week will be taught by another lecturer. or sometimes for some practical modules the same practical at the same time will be conducted by multiple lecturers in different halls. 
- so for stunts there are few pathways in uok . a pathway is a subject combination . a student can only choose one pathway. for example 1st path is physics, pure math, applied math . a pathway only has 3 subjects . another example is 2nd path is chemistry, pure math, applied math . there are 10 pathways in total for physical science . but under science faculty there are other departments as well like biological science, computer science, etc. therefore we will have to get the list of all the pathways . 
- so for a session there is frequncy of occurence per week . for example for ordinary differential equation module there is only one 2 hour session for week . but for thermodynamics and solid state physics module there are two sessions and one session is 2 hours and the other session is 1 hour. so we will have to get the frequency of occurrence and the leacture hours for each occurrence. if allocated time per session is 2h then that session cannot be broken down into 2 sessions of 1h each.
- for practical sometimes first year physics lab can only be used for first year physics practicals only . 
- from 12pm to 1pm there is a lunch break for all students and lecturers . so no sessions can be allocated during that time .
- lectures can only be allocated from 8am to 6pm on weekdays . no sessions can be allocated outside of these hours or on weekends .
- another things is if there are 200 2nd year physics students if the physics lab can only accommodate 100 students then we will have to allocate 2 sessions for the physics practicals and split the students into 2 groups of 100 each. 
- if for some reason admin  decided to generate the timetable for 3rd year manually . then admin should have the ability to check if that timetable is valid or not


This is a significantly more complex system than what's currently implemented. Let me analyze the gap between your requirements and the current codebase.

---

## Current State vs. Your Requirements

| Requirement | Current Status | Gap |
|-------------|----------------|-----|
| **Room Types** | Simple: roomName, roomType, capacity, isLaboratory | ❌ No specialization (physics lab only for physics) |
| **Lecturers** | Simple: name, email, max_teaching_hours | ❌ No multi-lecturer per module, no split hours, no concurrent practicals |
| **Modules/Courses** | Simple: course_code, name, hours, lecturer_id | ❌ No frequency per week, session duration, year-specific |
| **Pathways** | ❌ Not implemented | Needs new entity |
| **Years** | ❌ Not implemented | Needs new entity |
| **Group Splitting** | ❌ Not implemented | Auto-split by capacity |
| **Lunch Break** | ❌ Not in solver | Needs constraint |
| **Time Slots** | ❌ Not in solver | 8am-6pm weekdays only |
| **Year-specific labs** | ❌ Not implemented | Needs constraint |
| **Manual Timetable Validation** | ❌ Not implemented | Needs new feature |

---

## Questions to Clarify

Before planning, I need some clarifications:

1. **Pathways**: Should pathways be pre-defined (hardcoded 10 for physical science) or should admin be able to add/edit/delete pathways dynamically?

2. **Module-Year Relationship**: Is the year tied to the module (e.g., "First Year Physics" is a different entry from "Second Year Physics") or is there a separate year attribute?

3. **Lecturer Split Scenarios**: For the split hours (e.g., 2h + 1h by different lecturers), should we record:
   - Which lecturer teaches which portion?
   - Or just list multiple lecturers per module?

4. **Validation Only vs Generation**: For the "manual timetable + validate" feature - should this be:
   - A read-only check that reports conflicts?
   - Or allow admin to override and save anyway?

5. **Practical Types**: Should practicals be categorized by subject (Physics Lab, Chemistry Lab, Computer Lab) to enforce the "physics lab for physics only" rule?

6. **Current Data**: Do you have any existing data (pathways list, room list, lecturer list) or is this starting from scratch?

---

## High-Level Plan

Based on your requirements, here's what needs to be built:

### Phase 1: Data Model Extensions
- Add **Years** entity
- Add **Pathways** entity with subject associations
- Extend **Rooms** with specialization (subject tag)
- Extend **Courses/Modules** with: year, frequency_per_week, session_duration, practical_type
- Extend **Lecturer-Module** relationship (many-to-many)

### Phase 2: Enhanced Solver
- Add lunch break constraint (12-1pm)
- Add time window constraint (8am-6pm weekdays)
- Add year-specific lab constraints
- Add capacity-based group splitting
- Handle multi-lecturer module scenarios

### Phase 3: UI Extensions
- Pathway management page
- Year management
- Enhanced room management with specialization
- Enhanced course/module management
- Timetable display view
- Manual timetable entry + validation

---

Want me to create a detailed technical specification document for this? Or do you have answers to the questions above first?




another thing i forgot to add . the admin said they will give us the data . but we have no clue in what format they will give us the data 

so until that we should create a place to add data manually through the UI . and the systemm should check if the data is enough and valid 

another thing i forgot to mention is that 

even though we create the timetable for wholde faculty we should have the ability to view that timetable by pathway and year

