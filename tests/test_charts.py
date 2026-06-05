# tests/test_charts.py
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import pytest


def test_candlestick_returns_figure(sample_prices):
    from utils.charts import candlestick
    fig = candlestick(sample_prices)
    assert isinstance(fig, go.Figure)


def test_candlestick_with_volume_has_two_traces(sample_prices):
    from utils.charts import candlestick
    fig = candlestick(sample_prices, volume=True)
    assert len(fig.data) == 2  # Candlestick + Bar (volume)


def test_candlestick_without_volume_has_one_trace(sample_prices):
    from utils.charts import candlestick
    fig = candlestick(sample_prices, volume=False)
    assert len(fig.data) == 1


def test_line_single_series_returns_one_trace(sample_prices):
    from utils.charts import line
    fig = line(sample_prices["Close"])
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 1


def test_line_dataframe_returns_one_trace_per_column(sample_prices):
    from utils.charts import line
    fig = line(sample_prices[["Close", "Open"]])
    assert len(fig.data) == 2


def test_line_uses_x_unified_hover(sample_prices):
    from utils.charts import line
    fig = line(sample_prices["Close"])
    assert fig.layout.hovermode == "x unified"


def test_bar_returns_figure(sample_prices):
    from utils.charts import bar
    fig = bar(sample_prices["Volume"])
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 1


def test_heatmap_returns_figure():
    from utils.charts import heatmap
    df = pd.DataFrame([[1.0, 2.0], [3.0, 4.0]], index=["A", "B"], columns=["X", "Y"])
    fig = heatmap(df)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 1


def test_heatmap_z_shape():
    from utils.charts import heatmap
    df = pd.DataFrame([[1.0, 2.0], [3.0, 4.0]], index=["A", "B"], columns=["X", "Y"])
    fig = heatmap(df)
    z = fig.data[0].z
    assert len(z) == 2 and len(z[0]) == 2
