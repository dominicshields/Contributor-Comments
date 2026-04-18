Contact Functionality.
For any given reporting unit there can be a contact or contacts as they can be distinct to each survey.
The attributes of contact are name, telephone number and email address.
I do not want contact information to be intrusive so it should only display in read mode if there are values and be as compact as possible.
What I do not want is someone to input a new comment and add a contact for the reporting unit and survey when one already exists, in this instance they should be directed to edit the existiong contact.

At the same time I want to add to the comment the ability to add a general comment that does not ap;ly to only one survey and this should appear before the survey comments in search results.

Questions to confirm:
1. Should a general comment have its own independent contact (RUREF + General), or should general comments always reuse one of the survey-level contacts?
A. Independent
2. When a user filters search by specific surveys, should general comments always still be shown, or hidden unless no survey filter is applied?
A. Always display general comment
3. Should contact edit access be available to all authenticated users (current implementation), or admin-only?
A. Available to all authenticated users
