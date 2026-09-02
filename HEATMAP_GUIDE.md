# How to Read the Spike Heatmap (Store × Day)

**What it shows:** for each store (rows) and each day-of-week (columns: Mon
through Sun), the total wastage across your ENTIRE selected date range for
that store, on that weekday.

**Why every number is positive:** it shows the *size* of wastage (magnitude),
not direction. This is intentional — the point of the heatmap is to spot
which store/weekday combination wastes the most, so mixing positive and
negative would make the colors meaningless for comparison.

**Why it's not tied to one specific date:** "Wed" isn't one Wednesday — it's
the sum of every Wednesday in your selected date range for that store. This
answers "does BTM consistently waste more on Saturdays?" rather than "what
happened on one specific day." Use the sidebar Date Range filter to narrow
the window if you want a tighter comparison (e.g. just last month).

**Reading the colors:** darker/brighter red = higher wastage for that
store+weekday combination, relative to the highest value currently shown.
Hover over any cell to see the exact store, day, and ₹ amount as a tooltip.

**Example:** if BTM's "Sun" cell is the brightest on the whole grid, that
means across your selected date range, BTM's Sunday wastage total is the
single highest store+weekday combination in the data — worth investigating
what happens operationally on Sundays at that store.
