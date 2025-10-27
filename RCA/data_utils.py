import pandas as pd

def safe_to_datetime(series):
    try:
        return pd.to_datetime(series, errors="coerce", utc=False)
    except Exception:
        return pd.to_datetime(series.astype(str), errors='coerce', utc=False)

def strip_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if df is None:
        return df
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    for col in df.columns:
        if pd.api.types.is_string_dtype(df[col]) or df[col].dtype == object:
            df[col] = df[col].apply(lambda x: x.strip() if isinstance(x, str) else x)
    return df

def safe_upper_map(s):
    try:
        return str(s).strip().upper()
    except Exception:
        return str(s)

'''def compute_classification_metrics(y_true, y_pred, positive_label="NG"):
    yt = [safe_upper_map(x) for x in y_true]
    yp = [safe_upper_map(x) for x in y_pred]
    labels = set(yt) | set(yp)
    total = len(yt)
    correct = sum(1 for a,b in zip(yt,yp) if a==b)
    accuracy = correct / total if total else 0.0

    pos = positive_label.upper()
    tp = sum(1 for a,b in zip(yt,yp) if a==pos and b==pos)
    fp = sum(1 for a,b in zip(yt,yp) if a!=pos and b==pos)
    fn = sum(1 for a,b in zip(yt,yp) if a==pos and b!=pos)
    tn = sum(1 for a,b in zip(yt,yp) if a!=pos and b!=pos)
    precision = tp / (tp+fp) if (tp+fp)>0 else 0.0
    recall = tp / (tp+fn) if (tp+fn)>0 else 0.0
    f1 = 2*precision*recall/(precision+recall) if (precision+recall)>0 else 0.0
    mismatch = sum(1 for a,b in zip(yt,yp) if a!=b)
    return {
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "mismatch": mismatch,
        "total": total
    }'''