import pandas as pd

def clean_value(val):
    if isinstance(val, str):
        return val.strip()
    return val

def _normalize_str(s):
    return str(s).strip().upper()

def _truthy_str(s: str):
    s = _normalize_str(s)
    return s in {"1", "TRUE", "T", "YES", "Y", "ON", "PASS", "OK"}

def _falsy_str(s: str):
    s = _normalize_str(s)
    return s in {"0", "FALSE", "F", "NO", "N", "OFF", "FAIL", "NG", "___", "E100000FFF", "?"}

def _get_branch_by_exact_key(rule: dict, value: str):
    if not isinstance(rule, dict):
        return None, None
    val_norm = _normalize_str(value)
    RESERVED = {"FEATURE", "PASS", "FAIL", "DISABLE", "PREDICTION", "ROOT_CAUSE", "OK", "NG"}
    candidates = {}
    for k, v in rule.items():
        if not isinstance(k, str):
            continue
        if k.upper() in RESERVED:
            continue
        candidates[_normalize_str(k)] = (k, v)
    return candidates.get(val_norm, (None, None))

def analyze_row_with_path(row, rule, parent_feature=None, path=None):
    if path is None:
        path = []
    if not isinstance(rule, dict):
        return "Unknown", parent_feature or "No Matching Rule", "->".join(path) if path else ""

    if "Prediction" in rule:
        pred_raw = str(rule["Prediction"]).upper()
        if pred_raw == "NG":
            cause = rule.get("root_cause") or rule.get("feature") or parent_feature or "Unknown"
            leaf_tag = f"[PRED={pred_raw}]"
            return "NG", cause, "->".join(path + [leaf_tag])
        elif pred_raw == "OK":
            leaf_tag = f"[PRED={pred_raw}]"
            return "OK", "Good Condition", "->".join(path + [leaf_tag])
        else:
            return pred_raw, parent_feature or "Unknown", "->".join(path)

    feature = rule.get("feature")
    if feature is None:
        return "Unknown", parent_feature or "No feature in rule", "->".join(path)

    if feature not in row or pd.isna(row[feature]):
        return "Missing", f"Missing feature: {feature}", "->".join(path + [f"{feature}=<MISSING>"])

    val = str(clean_value(row[feature]))

    matched_key, child = _get_branch_by_exact_key(rule, val)
    if matched_key is not None:
        new_path = path + [f"{feature}={matched_key}"]
        return analyze_row_with_path(row, child, parent_feature=feature, path=new_path)

    if "fail" in rule and _falsy_str(val):
        new_path = path + [f"{feature}=FAIL-LIKE({val})"]
        pred, cause, pth = analyze_row_with_path(row, rule["fail"], parent_feature=feature, path=new_path)
        return pred, cause, pth
    if "Disable" in rule and _normalize_str(val) in {"DISABLE", "OFF", "-1"}:
        new_path = path + [f"{feature}=DISABLE({val})"]
        pred, cause, pth = analyze_row_with_path(row, rule["Disable"], parent_feature=feature, path=new_path)
        return pred, cause, pth
    if "pass" in rule:
        new_path = path + [f"{feature}=PASS-LIKE({val})"]
        return analyze_row_with_path(row, rule["pass"], parent_feature=feature, path=new_path)

    return "Unknown", parent_feature or "No Matching Rule", "->".join(path + [f"{feature}=<{val}> (no-branch)"])

def collect_rule_features(rule, out=None):
    if out is None:
        out = set()
    if isinstance(rule, list):
        for r in rule:
            collect_rule_features(r, out)
        return out
    if not isinstance(rule, dict):
        return out
    feat = rule.get("feature")
    if feat:
        out.add(feat)
    for k, v in rule.items():
        if k in ("pass", "fail", "Disable"):
            collect_rule_features(v, out)
        elif isinstance(v, dict) and k not in {"feature", "Prediction", "root_cause", "OK", "NG"}:
            collect_rule_features(v, out)
    return out