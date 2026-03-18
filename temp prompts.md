well that is not it 

even the current version is not up to my satisfaction


so here is the deal 

the reason we had to develop this in stages is because instructions and data was not available to us at the time of development

the lecturer kept saying that they will provide us with data 

so we had to develop this to enter every single data point manually

since that is not practical we also implemented a demo data set to test the functionality of the system

then they provided us students_processed_TT_J.csv

even that only provided only a porttion of data we needed

but since the beggining even before we had this csv we had a right idea about the way the system should work 

so the solver logic was already in a good shape compared to data entry phase 

that being said we improved the solver logic. not saying it was perfect . but compared to the data entry phase it was always ahead 

and i belive now it is in a better stable state 

but we will still have to have proper data to be highly confident about the solver logic


but we already have pretty high confidence about the solver logic because i have implemented 3 totally sperate systems to verify the results of the solver logic 

one in elixir

i do not remember about the other two 


anyway what we have to do is fix this setup phase aka data entry phase


since the admin is not giving us the data structure they can get from the system we have to create import data strcture our self and then create few sample csvs for testing

they have alredy given us students_processed_TT_J.csv 

we know the structure of that csv

so we can and might already have created  a import feature for that csv 




what i am ssaying is 

in the f end there will be the ability to import csv files 

students_processed_TT_J.csv will also be a csv file that can be imported

for other csv files we have to decide the schema our self 

we will have to make sure these are in a format that is easy for the admin to export from the system they are using to manage the data

====================================================================================================================