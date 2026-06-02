# L2: Transaction Monitor

This layer uses four Azure Functions running in parallel to perform deterministic checks on the transaction data.

- **T1: Velocity**: 90-day history, structuring detection.
- **T2: Watchlist**: FIU-IND sanctioned entities fuzzy match.
- **T3: Risk score**: Account age, history, flags, risk tier.
- **T4: Geo anomaly**: Location vs historical pattern, moving average of account state.

A weighted scoring formula combines the outputs of these checks into a single suspicion score.
