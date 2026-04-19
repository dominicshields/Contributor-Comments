Create a new top level menu called Comments to the right of search amd add.
As the first submenu I want a page/view called Comments by Author
This should display all comments with paging once a screen is full - this is vague, we can refine this later.
The comments should be presented sorted by author, then ruref then survey always ordered and grouped
There should be a subtle count of comments by author displayed.
It should be simple to collapse the view grouped by author.
It should be simple to filter by author.

---

Questions / assumptions (to confirm)

1. Menu structure: should `Comments` be a new top-level item replacing `Search and Add`, or should both remain visible?
A. Both visible, we can re-examine the exact menu structure when we have a beta product
2. Pagination: is `50 comments per page` acceptable as an initial default for “once a screen is full”?
A. Yes
3. Group ordering: for `survey`, should ordering follow survey display order with `General` first, then code order?
A. Yes
4. Collapsible groups: should groups default to expanded on first load, with optional “Collapse all” / “Expand all” controls?
A. Yes
5. Author filter: is a case-insensitive “contains” text filter on author full name / username acceptable?
A. Yes
6. Count display: should the subtle count be shown as `Author Name (N)` in each author heading?
A. Yes

New comment page/view
I want a new page/view under the top menu items Comments
Comments by Date
This should show comments in descending date order categorised (initially collapsed) by
Year YYYY
Month (in date order, not alphabetically)
then not collapsed
Ruref
Survey (in survey display order)

---

Questions / assumptions for `Comments by Date` (to confirm)

1. Menu placement: should `Comments by Date` be added as a second submenu item under the existing top-level `Comments` menu, alongside `Comments by Author`?
A. Yes
2. Date basis: should “date order” use the comment `created_at` timestamp, rather than `updated_at` or edit-history timestamps?
A. Date created
3. Pagination: should this page also use standard pagination, and if so is `50 comments per page` still the right initial default?
A. Yes
4. Collapse behavior: when you say “categorised (initially collapsed) by Year, Month, then not collapsed Ruref, Survey”, should both `Year` and `Month` start collapsed, with `RUREF` and `Survey` expanded once a month is opened?
A. Yes
5. Comment ordering within each survey group: should comments be shown newest first by `created_at`?
A. Yes
6. Count display: do you want subtle counts shown on the `Year` and `Month` headings as well, for example `2026 (124)` and `April (37)`?
A. Yes