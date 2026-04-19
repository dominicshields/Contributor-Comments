 I want a python program that is under a new foider called utilities, the program should be called generate_test_comments.py. It should create the number of comments specified as a command line parameter. 

 The fields should be populated as follows
 
 Reporting unit (ruref)
 Survey: randomly chosen from the Survey Metadata
 Period: YYYYMM in a range 202001 to 202512 inclusive, the rules are that the periodicity in the metadata determines the valid
 periods for a comment for a given survey, Monthly can be any month, quarterly can only be 03, 06, 09, 12, annual can only be 12 and other can only be 12. An exception to these rules is survey 141 which must be 04.
 Comment: Using the python library Faker for names and text, the layout should be
 "Spoke to <Faker Name> they said <Faker text>" then have a saved date consistent with the period - e.g. after the period but less than a year later.
 The name of the author of the comment should be random within a list you generate using faker of no more than 100 names.

 output file should be called synthetic_test_comments.csv

 Any questions or fields I have missed, please add below.

An additional request - the text of the comments is fine but to demonstrate the search functionality in a simple way I need seeded hit words that are easy to recall, so leaving the comment text as-is, could you make an addition that every 10th comment
has the name of a chemical element at the end after the lorum ipsum type text.

Additional request 2
I need to see multiple comments for a given ruref, so half the time, create multiple comments for a given ruref, varying the survey and period but 1 time in 10 keep the same survey