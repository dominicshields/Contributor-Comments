# Contributor Comments Spec Questions

Please answer the questions below so implementation can proceed without rework.

1. Scope for this first implementation:
   - Build only the Flask/Jinja web app and data model now?
   - Or also include initial Terraform and Concourse pipeline files in this same pass?
A. Everything 

2. Database choice now:
   - Implement against PostgreSQL only for this milestone, with code structured so a DynamoDB adapter can be added later?
A. Yes, PostgreSQL only for now, but design code to allow adding DynamoDB later without major refactor.

3. RU reference behavior:
   - Can one `ruref` have many comments over time (across surveys/periods)?
   - Should `ruref` be validated as exactly 11 characters?
   - If yes, alphanumeric only or any characters?
A. Yes to 1 and 2, numeric only

4. Data model for edits (`editor_list`):
   - Use a true edit history table (one row per edit with editor + timestamp)?
   - Or a single field on the comment record that is appended to?
A. True edit history table is better for maintainability and querying, even if more complex to implement initially.

5. Author/editor identity source:
   - How should author/editor be captured right now?
   - From app login user
   - From a request header
   - Simple text input for now (temporary)
A. The logged in user

6. Survey handling:
   - Should users be restricted to `survey_list` values (`221`, `241`, `002`, `023`, `138`)?
   - Or allowed to enter other 3-character codes as well?
A. The metadata list should be amendable by the admins but at present, just the codes I gave.

7. Period input:
   - Should period always be stored as `YYYYMM` with strict validation, even when free-typed?
   - Should invalid values be rejected on submit?
A. Yes to both - store as `YYYYMM` and reject invalid values on submit.

8. Search behavior:
   - Should search include comment text only?
   - Or comment + `ruref` + `survey` + `period`?
   - Is simple contains search acceptable for now, or do you want PostgreSQL full-text search from the start?
A. I want direct input for ruref lookup with options to narrow by survey, or list of surveys and comment full text search.

9. Comment display grouping:
   - On the `ruref` page, should comments be grouped by survey in fixed `survey_list` order?
   - Within each survey, sort by period descending, then created descending?
A. Yes to both

10. ONS design system integration:
    - Pull ONS frontend assets via CDN initially?
    - Or vendor them locally in the project?
A. Whatever AWS/flexi is doing 

11. Timestamp/hover behavior:
    - Store created timestamps in UTC and display in UK time?
    - Is a standard tooltip on author hover acceptable?
A. Yes to both

12. Starter data:
    - Seed `survey_list` on startup automatically for local/dev runs?
A. Yes and a list of test users
