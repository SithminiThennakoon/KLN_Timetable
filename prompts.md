okay here are the requirements 

we will have to think about this from ground up because current codebase is a mess in both code level and the business logic level.

there are few degrees under the science faculty

there is physical science degree, biological science degree, environmental conservation and management degree, applied chemistry degree, electronics and computer science degree and physics and electronics degree.

we have to create a timetable generator for university of kelaniya science faculty 

some degrees are 3 year degrees and some are 4 year degrees.

In the Faculty of Science (FoS), students' subject choices depend on their initial intake stream (PS or BS) or if they are in a specialized direct-entry program (ENCM, AC, ECS, PE). [1] 
PS (Physical Science) Students
Physical Science students select a combination of three main subjects from a set list. [2, 3] 

* Core Subjects: Pure Mathematics, Applied Mathematics, Physics, Chemistry, Statistics, Computer Science, Computer Studies, and Electronics.
* Additional Units: All PS students can take introductory Computer Science (COSC 11014) and management-related units specifically for physical science (MAPS).
* Selection: Students choose their specific subject combinations (e.g., Physics, Mathematics, and Statistics) at the start of the first year. [2, 3, 4, 5, 6] 

BS (Biological Science) Students
Biological Science students follow a similar structure, choosing three subjects from the biological sciences group. [1, 2, 7, 8] 

* Core Subjects: Botany (Plant Biology), Zoology, Chemistry, Microbiology, Molecular Biology & Plant Biotechnology, Biochemistry, and Computer Studies.
* Compulsory Units: In the first semester, all BS students take broad "BIOL" units covering Genetics, Basic Biochemistry, Animal Form & Function, and Microbiology.
* Limited Enrolment: Subjects like Biochemistry and Microbiology have limited seats based on first-semester performance. [1, 5, 9, 10] 

ENCM (Environmental Conservation and Management) Students
This is a multidisciplinary stream focused on applied environmental sciences. [11, 12] 

* Major Subjects: Evolution & Biogeography, Ecology, Hydrology & Meteorology, Environmental Pollution, and Environmental Economics.
* Applied Topics: Students study GIS (Geographic Information Systems), Wildlife & Protected Area Management, Wetland Management, and Ecotourism.
* Cross-Faculty Support: Includes specific course units from the departments of Chemistry, Botany, and Microbiology. [11, 12, 13, 14, 15] 

AC (Applied Chemistry) Students
Applied Chemistry is a 4-year Honours program specifically for industrial and analytical applications. [16, 17] 

* Core Modules: Calculations in Chemistry, Atomic Structure, Chemical Bonding, and Chemistry of Main Group/Transition Elements.
* Industrial Focus: Advanced Analytical Chemistry, Chemical Technology, Industrial Training, and Quality Management/Quality Assurance.
* Skills: Students also cover basic Electronics and Management skills relevant to the chemical industry. [16, 17, 18, 19] 

ECS (Electronics and Computer Science) Students
Formally known as BECS, this stream bridges hardware and software. [4, 6] 

* Core Subjects: A mix of Electronics (ELEC) and Computer Science (COSC) course units.
* Key Areas: Digital electronics, circuit design, programming, data structures, and computer architecture. [4, 6] 

PE (Physics and Electronics) Students
This 3-year degree is designed for students who focused on Physics, Mathematics, and ICT. [20] 

* Major Subjects: Physics and Electronics are the two main subjects.
* Supporting Subjects: Students must also take either Mathematics and Management or Mathematics and Computer Studies.
* Specific Modules: Mechanics, Electric Circuits, Modern Physics, and Solid State Physics. [20, 21, 22] 


even though these are organized as separate degrees with seperate ugc intakes and z scores 

there are common subjects across these degrees and there are also some subjects that are only offered to specific degrees.

when scheduling all the students doing a certain subject participates in the same class for that subject regardless of their degree.

for example if for  chemistry module sessions there are students from physical science, biological science , environmental conservation and management and applied chemistry degree all these students will be in the same class for that chemistry module session.

so when enroling to each degree students have to select their subject combinations . it is called the path 

for degrees like physical science and biological science students have to select 3 subjects from a list of subjects offered for that degree. but not all the combinations are allowed.

but for some degrees there are no subject combinations to choose from. 

under those subjects there are different modules 

most of the times modules are for semesters

but some modules span over a whole year

under a module there can be single or multiple sessions per week and they can have different durations. 

also there are situations where the same real teaching event is recognized as different modules for different degrees or pathways. our data model and algorithms should support that.

that means a single shared lecture or shared lab session can belong to multiple curriculum modules at the same time.

for example one common lecture may be followed by students from several physical science pathways under one module identity, by another pathway under a different module identity, and by a completely different degree under yet another module identity.

so we should not assume that one scheduled session always maps to exactly one module for all attending students.

instead we should support one scheduled teaching session being linked to one or more modules while still keeping the actual attending student groups, lecturers, room requirements and conflict logic attached to the shared session itself.

student overlap and clash detection should be based on the actual student groups attending the session, not only on a single module code.

the data collection flow should therefore allow the user to define a shared teaching session once and then associate that session with one or more module identities where needed.


so we should think of constraints as having two levels

1. the most basic constraints that will make a timetable coherant and functional for the students and the faculty. 
2. the constraints that are more of nice to have but not strictly necessary for the timetable to be functional.

for the most basic constraints we have to consider

1. the classroom should be capable of accomodating the number of students in the session
2. the classroom should be compatible with the requirements of the session (for example a chemistry lab should be used for chemistry lab sessions)
3. this lab thing has some other constraints as well because for example first year physics lab can be held in first year physics lab only. that session cannot be held any other lab. not even in second year physics lab. so as inputs for timetable generation we should have a list of sessions with their requirements and the number of students enrolled in that session. 
4. same classroom cannot be used for two sessions at the same time. no overlapping sessions in the same classroom.
5. students cannot attend two sessions at the same time. so if there are two sessions that have common students they cannot be scheduled at the same time.
6. sessions should be scheduled within the working hours of the university . 
7. we are generating weekly timetables .
8. timetable should be 5 days a week and from 8 am to 6 pm.
9. from 12 pm to 1 pm is a lunch break so no sessions should be scheduled during that time.
10. same teacher cannot teach two sessions at the same time. no overlapping sessions for the same teacher.


for the nice to have constraints we can consider

1. for modules that have multiple sessions per week, those sessions should be scheduled on different days. for example if a module has two sessions per week those sessions should not be scheduled on the same day.

in addition to that base nice to have rule, it is also okay to support extra optional preferences as explicit extensions if they help reduce the search space and still preserve a realistic faculty timetable.

explicit nice to have extension examples:

2. prefer theory sessions such as lectures and tutorials to be scheduled in the morning and to finish before lunch when possible.
3. prefer practical and laboratory sessions to be scheduled after lunch when possible, so the morning can be used more for large shared theory sessions.
4. avoid late afternoon starts when possible, so the timetable does not become too compressed near the end of the day.
5. avoid Friday sessions when possible, so the faculty week stays lighter and more of the teaching load is concentrated from Monday to Thursday.
6. prefer standard faculty block starts when possible, so sessions begin on common timetable boundaries instead of arbitrary half-hour placements.
7. balance the teaching load across the week when possible, so the full timetable does not bunch heavily at the start of the week.
8. avoid overloading Monday when possible, so Monday does not carry significantly more teaching than the rest of the week.

these extension constraints are optional and should be clearly presented as nice to have preferences, not as mandatory functional rules.

the shape of the timetable i have in mind is this 


this is a weekly timetable with days of the week as columns and time slots as rows. 
for every time slot the session in that time slot and the location of that session is mentioned.
it should also mention all the degree+path combinations that are attending that session.
it should display the teacher for that session as well.
it should also display the number of students attending that session as well.
from 12 pm to 1 pm there should be a lunch break and no sessions should be scheduled during that time.
sessions should be scheduled from 8 am to 6 pm and the timetable should be for 5 days a week.

session lenghts can vary . but most often they are multiple of 30 minutes. 

for session overlaps 

here is a exaple 

so path 1 is pure mathematics, physics and applied mathematics. 
so pure mathematics module sessions and physics module sessions cannot be scheduled at the same time because there are students who are doing both pure mathematics and physics. pure mathematics module sessions and applied mathematics module sessions cannot be scheduled at the same time because there are students who are doing both pure mathematics and applied mathematics. 

no big deal

basically if there is a overlap between two sessions then there cant be any student who is doing both those sessions. simple as that 

instead of student we can simplfy that as degree+year+path combination. 

even though there are year long modules their times can be different for different semesters. so we do not have to worry about that. 

we are generating weekly timetable for a semester

that is all this app is doing 

for some sessions there are some special requirements. our data and algorithm should be able to handle those requirements as well. 

sometimes for example for physics lab sessions there are more students than the capacity of the lab. in such cases those students are divided into groups and each group attends the lab session at a different time. that is perfectly fine 

but for some sessions students are higer than the capacity of a single classroom but we cannot hold multiple sessions at different times 

in such cases we can hold multiple sessions at the same time in different classrooms. so multiple classrooms and multiple lecturers but same time slot. 

we should collect this data when we are gathering data from the user. 

btw we are only tasked with creating a web app to do only this . we do not need to worry about loggin , user management etc . 

there should be a place to enter data manually 

we should decide the most efficient way gather data from the user . it should be super comfortable for the user to enter data while also ensuring that all the data we need is collected in a structured way that can be easily used for timetable generation.

then user can select nice to have constraints . the must have constraints will not be shown to the user because those are mandatory to make a functional coherent timetable.

then there should be a button to generate the timetable and then the generated timetable 


then it should generate all the possible timetables that satisfy the constraints and the data entered by the user 

but the system can break if there are too many possible timetables because of the combinatorial nature of the problem. in such case if it exceeds a certain threshold (for example 1000) then it should display a message saying that there are too many possible timetables and it cannot generate all of them. i do not know what is the best stop condition for it could be time it takes to generate the timetables . if it takes more than 60 seconds to generate the timetables then it should stop and display the message that there are too many possible timetables and it cannot generate all of them. or it should count the number of generated timetables and if it exceeds 1000 then it should stop and display the message that there are too many possible timetables and it cannot generate all of them.




system does not have to necessarily display all the possible timetables but it should generate all the possible timetables 

then it should display how many possible timetables are there 

if it is above 100 then it should force the user to select some of the nice to have constraints to reduce the number of possible timetables.

if all the nice to have constraints are selected and there are still more than 100 possible timetables then it should display a random one but it should specify that there are more than 100 possible timetables and that the displayed timetable is just one of them.

and also on the other end if there are no possible timetables that satisfy the must have constraints and the data entered by the user then it should display a message saying that there are no possible timetables that satisfy the constraints and the data entered by the user

if there are possible timetables that satisfy the must have constraints and the data entered by the user but none of them satisfy the nice to have constraints user have selected then it should display the nice to have constraint combinations that are possible and ask the user to select one from those combinations 

so after the user select a faculty time table 

it should be set as the default until it is changed by the user. 

this is important because next phase is displaying the timetable 

to do that we should have a agreed upon timetable 

now that we have an agreed upon timetable for all the modules , for all the students without any conflicts we can move on to the next phase which is displaying the timetable in a user friendly way.

for this there are multiple options and sub-options

first the admin view has all the details all the sessions, all the students, all the teachers, all the classrooms etc. 

then there is the lecturer view where a lecturer can see only the sessions they are teaching and the students attending those sessions. since we do not have user based authentication it should be possible to select the lecturer view then it should ask to select the lecturer from a list of lecturers and then it should display the timetable for that lecturer. 

then there is the student view where a student can see only the sessions they are attending and the teachers teaching those sessions. for that first the student should select student view then it should ask to select the degree and then the path (subject combination) and then it should display the timetable for that degree and path combination.

all of these views should be exportable to pdf , csv , xls, png etc.

all the years and all the degrees and all the subject combinations and all the modules and all the sessions and all the classrooms and all the teachers and all the students should be displayed in the faculty timetable.

for things like how many students are enrolled in each degree and how many students are enrolled in each subject combination will have to be taken as input from the user. 

for now those are manually entered but in the future we can think about data import feature 

but for that we have to know the structure the university is going to give us the data in.

if we know exact colomns and data format then we can create a csv import feature that can read the data and populate the system with that data.

but for now we will just have a manual data entry form for that.

and also a seeder script to populate the system with some dummy data for testing and development purposes.

but this seeder script should be able to generate data that that matches the system capabilities

even though year + degree + path combination is good at identifying a group of students it is not sufficient because of elective modules. 

therefore when importing data we will have to use that year + degree + path combination as a base but when storing the data we will have to think about better data storing structure that can handle elective modules as well. 
