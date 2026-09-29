"""Aggregate ML layer — time-series forecasting, anomaly detection, and topic
modeling over AGGREGATE data (daily counts, corpora of public posts). Never
per-individual. Every function degrades gracefully if the optional lib is missing
or the series is too short, so the API never hard-fails.
"""
import logging

log = logging.getLogger("ml")


def forecast_series(values: list[float], horizon: int = 7) -> dict:
    """Forecast a daily series with Holt exponential smoothing (statsmodels),
    falling back to least-squares. Returns projection + 80% band + trend."""
    n = len(values)
    if n < 4:
        return {"projection": [], "trend": "flat", "confidence": "low", "method": "none"}
    try:
        import numpy as np
        from statsmodels.tsa.holtwinters import ExponentialSmoothing
        y = np.array(values, dtype=float)
        model = ExponentialSmoothing(y, trend="add", seasonal=None,
                                     initialization_method="estimated").fit()
        fc = model.forecast(horizon)
        resid = y - model.fittedvalues
        rmse = float(np.sqrt(np.mean(resid ** 2))) or 1.0
        proj = []
        for i, v in enumerate(fc, 1):
            band = rmse * 1.28 * (1 + i * 0.05)
            proj.append({"step": i, "value": round(max(0, float(v)), 1),
                         "low": round(max(0, float(v) - band), 1),
                         "high": round(float(v) + band, 1)})
        slope = (fc[-1] - y[-1]) / max(horizon, 1)
        mean_y = float(np.mean(y)) or 1
        pct = slope / mean_y * 100
        trend = "rising" if pct > 8 else "falling" if pct < -8 else "flat"
        return {"projection": proj, "trend": trend,
                "confidence": "high" if n >= 14 else "medium", "method": "holt"}
    except Exception as e:  # noqa: BLE001
        log.info("statsmodels forecast unavailable (%s); using linear fallback", e)
        return _linear_forecast(values, horizon)


def _linear_forecast(values: list[float], horizon: int) -> dict:
    n = len(values)
    xs = list(range(n))
    mx, my = sum(xs) / n, sum(values) / n
    denom = sum((x - mx) ** 2 for x in xs) or 1
    slope = sum((xs[i] - mx) * (values[i] - my) for i in range(n)) / denom
    intercept = my - slope * mx
    resid = [values[i] - (intercept + slope * xs[i]) for i in range(n)]
    rmse = (sum(r * r for r in resid) / n) ** 0.5 or 1
    proj = []
    for i in range(1, horizon + 1):
        v = max(0, intercept + slope * (n - 1 + i))
        band = rmse * 1.28 * (1 + i * 0.06)
        proj.append({"step": i, "value": round(v, 1),
                     "low": round(max(0, v - band), 1), "high": round(v + band, 1)})
    pct = (slope * 7 / (my or 1)) * 100
    trend = "rising" if pct > 8 else "falling" if pct < -8 else "flat"
    return {"projection": proj, "trend": trend, "confidence": "low", "method": "linear"}


def detect_anomalies(series: list[dict]) -> list[dict]:
    """Flag anomalous days in [{day, value}] via PyOD ECOD, fallback to robust z-score.
    Returns the input with an added 'anomaly' bool + 'score'."""
    vals = [s["value"] for s in series]
    if len(vals) < 6:
        return [{**s, "anomaly": False, "score": 0.0} for s in series]
    try:
        import numpy as np
        from pyod.models.ecod import ECOD
        X = np.array(vals, dtype=float).reshape(-1, 1)
        clf = ECOD()
        clf.fit(X)
        labels = clf.labels_
        scores = clf.decision_scores_
        smax = float(scores.max()) or 1.0
        return [{**series[i], "anomaly": bool(labels[i]),
                 "score": round(float(scores[i]) / smax, 2)} for i in range(len(series))]
    except Exception as e:  # noqa: BLE001
        log.info("pyod unavailable (%s); using z-score fallback", e)
        import statistics
        med = statistics.median(vals)
        mad = statistics.median([abs(v - med) for v in vals]) or 1
        out = []
        for s in series:
            z = abs(s["value"] - med) / (1.4826 * mad)
            out.append({**s, "anomaly": z >= 3.5, "score": round(min(1.0, z / 6), 2)})
        return out


def topic_model(texts: list[str], k: int = 6) -> list[dict]:
    """Discover latent themes with TF-IDF + NMF (scikit-learn). Returns top terms
    per theme + document share. Falls back to [] if unavailable/insufficient."""
    texts = [t for t in texts if t and len(t) > 20]
    if len(texts) < 12:
        return []
    try:
        import numpy as np
        from sklearn.decomposition import NMF
        from sklearn.feature_extraction.text import TfidfVectorizer
        vec = TfidfVectorizer(max_features=800, stop_words="english",
                              ngram_range=(1, 2), min_df=2)
        X = vec.fit_transform(texts)
        if X.shape[1] < k:
            return []
        terms = vec.get_feature_names_out()
        # random init avoids nndsvda's randomized_svd, which throws a C-contiguity
        # error on some numpy/scipy combos; dense contiguous input for safety
        Xd = np.ascontiguousarray(X.toarray())
        nmf = NMF(n_components=k, init="random", max_iter=400, random_state=42)
        W = nmf.fit_transform(Xd)
        H = nmf.components_
        assign = W.argmax(axis=1)
        out = []
        for i in range(k):
            top = [terms[j] for j in H[i].argsort()[-6:][::-1]]
            share = round(float((assign == i).sum()) / len(texts) * 100, 1)
            if share > 0:
                out.append({"label": ", ".join(top[:3]), "terms": top, "share": share})
        return sorted(out, key=lambda x: -x["share"])
    except Exception as e:  # noqa: BLE001
        log.info("sklearn topic model unavailable (%s)", e)
        return []
