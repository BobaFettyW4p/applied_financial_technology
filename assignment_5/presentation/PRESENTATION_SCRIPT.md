# Treasury pricing: five-minute presentation

Five slides for the first two minutes, then a three-minute webpage demo.
Read the quoted text aloud. The actions are cues, not additional narration.
The timing leaves room for clicking and brief pauses. Rehearse once with a timer.

Before presenting, open the deck and run `npm run dev:cloud` from `assignment_5`.
Check that http://127.0.0.1:8787 loads the latest charts. Start with all filters
cleared and the table sorted by maturity. Keep the terminal running. The latest
local changes appear on the permanent URL only after deployment.

## Slides: 0:00–2:00

### Slide 1: Treasury pricing — 0:00–0:25

> Our goal was to show what a Treasury buyer pays at settlement. We started with
> 464 FedInvest records and retained 353 conventional notes and bonds. We use
> November 9 prices and November 10 settlement, with amounts per $100 face
> value.

### Slide 2: Pricing and yield calculations — 0:25–1:00

> We matched CUSIPs to official Treasury terms and coupon dates. We use the end-
> of-day quote, calculate accrued interest through settlement with actual day
> counts, and add it to clean price. YTM uses remaining coupons and principal.
> Month-end and leap-year dates are handled explicitly.

### Slide 3: Checks before publication — 1:00–1:25

> We built 21 tests, including calendar boundaries and a published Treasury
> pricing example. Each calculated yield must reproduce its source dirty price.
> Missing or inconsistent terms stop the export, and the upload checks that the
> source file matches the validation report.

### Slide 4: Data storage and a permanent URL — 1:25–1:50

> R2 stores the original CSV and prepared JSON. A Worker reads the JSON through
> an R2 binding and serves a permanent URL. GitHub runs tests before deployment, Terraform manages
> the bucket, and Wrangler publishes the Worker. The local version lets us
> review changes before publishing them.

### Slide 5: The live page — 1:50–2:00

> Now we can inspect an individual calculation and explore the dataset through
> linked filters, yield comparisons, and pricing charts.

**Action:** Switch to the webpage at the two-minute mark.

## Webpage demo: 2:00–5:00

### Table — 2:00–2:25

**Action:** Show the top of the page with all 353 securities visible in the count.
Point to the price and settlement dates, then the six column headings.

> The table starts in maturity order and includes all 353 securities. The six
> columns are CUSIP, coupon, maturity, clean price, accrued interest, and dirty
> price. Clean price
> is the quoted price. Accrued interest compensates the seller for interest
> already earned, and dirty price adds the two. We can filter by type, coupon,
> or maturity, and sort any column.

### Coupon timeline — 2:25–3:05

**Action:** Click `912828U24`, near the top of the table. The page moves to its
timeline. Keep all filters cleared.

> This 2% note pays one dollar every six months per $100 face value. Its coupon
> period runs from May 15 to November 15. At November 10 settlement, 179 of
> 184 days have elapsed. So the buyer owes the seller about 97 cents of accrued
> interest. Adding that to the clean price gives a dirty price of about $100.94.
> The timeline exposes the exact dates and fraction behind that number.

### Yield to maturity by time remaining — 3:05–3:40

**Action:** Scroll to the YTM chart and hover over a bucket. Avoid clicking a
bucket during the timed demo so the following charts still show the full dataset.

> Here we group every security by time remaining. Each dot is the median yield
> to maturity, the lines cover the middle half of yields, and the labels show
> the counts. Median YTM rises from about 4.29% under one year to 5.35% beyond
> twenty years. These are yields implied by our prices and remaining payments,
> not forecasts or the official Treasury yield curve.

### Coupon rate versus clean price — 3:40–4:15

**Action:** Scroll to the two scatterplots. Point to a dot above the $100 line.
The 6.25% bond `912810FM5` is an example near the upper right.

> Higher coupons generally go with higher prices, but maturity also matters.
> The colors show time remaining. Some securities cost more than $100 because
> buyers pay extra for their larger interest payments. For example, the 6.25%
> bond costs about $105.06 but repays $100 at maturity. Its YTM is about 4.67%,
> below its coupon. Longer-maturity, low-coupon bonds show much deeper discounts.

### Coupon rate versus accrued interest — 4:15–4:40

**Action:** Point to the bands of dots in the neighboring scatterplot.

> Accrued interest depends on both the coupon and payment timing. Larger coupons
> can create larger amounts, but securities with the same coupon can owe very
> different interest. Darker dots are further through their coupon period.
> Those different payment cycles create the bands we see here.

### Maturity distribution — 4:40–4:55

**Action:** Scroll to the maturity chart. If time permits, click 2027 to show
that a chart selection filters all views.

> This chart counts securities by maturity year. There are 54 maturing in 2027
> versus four in 2050. These are counts of securities, not dollars invested.
> Clicking a year filters all views.

### Close — 4:55–5:00

> The result is a reproducible pricing calculation that users can inspect and explore.
