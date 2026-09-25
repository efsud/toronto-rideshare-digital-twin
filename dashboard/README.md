# Interactive marketplace control room

The dashboard advances one shared, session-scoped simulation engine. Configure
P0–P7, matching strategy, seed, fleet and synthetic demand, behavior/offer
assumptions, cancellation wait, fairness and fiscal bounds, and routing; then
step once or run a bounded number of decision epochs.

```bash
pip install -e ".[visualization]"
.venv/bin/streamlit run dashboard/app.py
```

What the display means:

- H3 resolution-8 cells are center-contained in a local boundary derived by
  dissolving the official City of Toronto Open Data 25-ward polygons. The asset
  contains source URL, retrieval date, and derivation metadata.
- Requests and fleet are synthetic. Driver acceptance is a seeded logistic
  model using offer earnings and pickup minutes; its coefficients are
  configurable assumptions, not measured Uber/Lyft behavior.
- Movement is explicit but discrete: drivers remain at their prior endpoint
  while en route, then update at pickup, drop-off, or reposition completion.
- If configured GraphML is absent, a visible warning identifies the straight-line
  haversine travel-time proxy. With GraphML present, routing uses the network and
  uses a traffic profile by departure bucket when available and enabled.
- Saved-result exploration and full P0–P7 comparisons remain available in the
  lower panel and only compute when explicitly requested.
