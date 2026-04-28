Add Annual Survey of Hourly Earnings (ASHE) functionality

The application as set up expects the main reference (key) to be reporting unit reference (ruref) which is 11 digit numeric.

We have a survey code (141) which as you can see in the metadata is an annual inquiry, it starts in April each year and hence
the period is of the form YYYY04

The main reference (key) for the ASHE survey is different that for all the other surveys, its reference is
National Insurance (NI) number as the survey is asking about individuals.

A UK NI number is of the format
Two prefix letters, six digits and one suffix letter. For example: AB123456C

So can this application be changed so that the reference that is currently set up for ruref (11 digit) also 
allow the reference to be NI Number?

There are a few cross-checks that can be done, a NI number can only be used for the survey 141
and everyone selected for this survey has the last two digits of their NI number "14"

The NI number can be validated using the following rules:
1. The first two characters must be letters (A-Z).
2. The next six characters must be digits (0-9).
3. The last character must be a letter (A-Z).
4. The NI number must be exactly 9 characters long.
5. The NI number digits must end with "14" for survey 141.

## Questions

1. Is NI number support strictly for survey `141` only, or do you want the design to support other future surveys with non-RUREF identifiers as well?
A. Possibly, let's not worry about that now.
2. For survey `141`, should NI number fully replace the current RUREF input, or should the data model move to a more generic reference field that can represent either a RUREF or an NI number?
A. Generic
3. For survey `141`, should the application accept only NI numbers, or should it temporarily accept either an 11-digit RUREF or an NI number during any transition period?
A. For now only allow NI numbers but this may change.
4. In the UI, should labels change from `RUREF` / `Reporting Unit Reference` to `NI Number` whenever the selected survey is `141`?
A. Yes, the label should change to NI Number when survey 141 is selected.
5. Should ASHE records appear in all the same places as current comment records, including search, RUREF detail pages, comments-by-author, comments-by-date, contact management, bulk upload, and admin reporting?
A. Yes, ASHE records should be integrated into all existing comment functionalities, with the reference field adapting to show either RUREF or NI number as appropriate based on the survey code.
6. If survey `141` uses NI numbers, should general comments also be allowed against an NI number, or should NI-number references be valid only for survey-specific `141` comments?
A. No, the exclusivity of 141 means that General would have no relevance
7. Should contact records also be keyed by NI number for survey `141`, or are contacts not needed for ASHE comments?
A. Yes
8. For CSV bulk upload, should the existing `ruref` column accept NI numbers when `survey_code=141`, or do you want a separate column name such as `reference` or `ni_number`?
A. A. Yes - the first option
9. Should NI numbers be normalized before saving, for example uppercasing letters and stripping spaces, or should the application store the exact user input?
A. Yes uppercase
10. Do you want to enforce only the rules listed above, or also the fuller UK NI-number restrictions such as disallowed prefix/suffix letters and other official validation rules?
A. Just our rules
11. For survey `141`, should the allowed period always be exactly `YYYY04`, or is April simply the valid collection month while historical or exceptional non-April periods may still need to be stored?
A. For now only allow 04 for month
