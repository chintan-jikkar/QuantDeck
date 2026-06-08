# api/serialize.py
"""Convert layer outputs (DataFrames, Series, numpy arrays, NaN/Inf) into
strict-JSON-safe Python primitives so FastAPI can return them to the frontend.
NaN/Inf become null (the JS JSON parser rejects literal NaN)."""
import math
import numpy as np
import pandas as pd


def to_jsonable(obj):
    if obj is None:
        return None
    if isinstance(obj, pd.DataFrame):
        df = obj
        # Surface a meaningful (named/non-range) index as a column.
        if df.index.name is not None or not isinstance(df.index, pd.RangeIndex):
            df = df.reset_index()
        return [to_jsonable(rec) for rec in df.to_dict(orient="records")]
    if isinstance(obj, pd.Series):
        return {str(to_jsonable(k)): to_jsonable(v) for k, v in obj.to_dict().items()}
    if isinstance(obj, np.ndarray):
        return [to_jsonable(x) for x in obj.tolist()]
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_jsonable(x) for x in obj]
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        f = float(obj)
        return None if (math.isnan(f) or math.isinf(f)) else f
    if isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    if isinstance(obj, (pd.Timestamp,)):
        return obj.isoformat()
    return obj
