# Fixed Income

The BRAPI Treasury adapter uses V2 `/api/v2/treasury/list`, `/indicators`, and `/indicators/history`. Rates and prices remain Decimal. `rateInfo` is provider metadata that explains rate interpretation; the core does not invent a different semantic. Fixed-income freshness has its own explicit policy because snapshots are daily.
