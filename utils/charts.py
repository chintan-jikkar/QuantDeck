# utils/charts.py
import plotly.graph_objects as go
import pandas as pd


def candlestick(df: pd.DataFrame, title: str = "", volume: bool = True) -> go.Figure:
    """OHLCV candlestick with optional volume subplot.

    Args:
        df: DataFrame with Open, High, Low, Close, Volume columns and a DatetimeIndex.
        title: Chart title.
        volume: If True, add a volume bar subplot below the candlestick.
    """
    if volume:
        from plotly.subplots import make_subplots
        fig = make_subplots(
            rows=2, cols=1, shared_xaxes=True,
            vertical_spacing=0.03, row_heights=[0.75, 0.25],
        )
        fig.add_trace(
            go.Candlestick(
                x=df.index, open=df["Open"], high=df["High"],
                low=df["Low"], close=df["Close"], name="Price",
            ),
            row=1, col=1,
        )
        fig.add_trace(
            go.Bar(
                x=df.index, y=df["Volume"], name="Volume",
                marker_color="rgba(100, 100, 200, 0.4)",
            ),
            row=2, col=1,
        )
        fig.update_layout(title=title, xaxis_rangeslider_visible=False, showlegend=False)
    else:
        fig = go.Figure(
            go.Candlestick(
                x=df.index, open=df["Open"], high=df["High"],
                low=df["Low"], close=df["Close"], name="Price",
            )
        )
        fig.update_layout(title=title, xaxis_rangeslider_visible=False)
    return fig


def line(
    series: "pd.Series | pd.DataFrame",
    title: str = "",
    yaxis_label: str = "",
) -> go.Figure:
    """Line chart for one or more series, with unified hover tooltip."""
    fig = go.Figure()
    if isinstance(series, pd.Series):
        fig.add_trace(go.Scatter(x=series.index, y=series.values, mode="lines", name=series.name or ""))
    else:
        for col in series.columns:
            fig.add_trace(go.Scatter(x=series.index, y=series[col], mode="lines", name=col))
    fig.update_layout(title=title, yaxis_title=yaxis_label, hovermode="x unified")
    return fig


def bar(series: pd.Series, title: str = "", color: "str | None" = None) -> go.Figure:
    """Vertical bar chart from a pandas Series."""
    marker = {"color": color} if color else {}
    fig = go.Figure(
        go.Bar(x=series.index, y=series.values, marker=marker, name=series.name or "")
    )
    fig.update_layout(title=title)
    return fig


def heatmap(
    df: pd.DataFrame,
    title: str = "",
    colorscale: str = "RdYlGn",
) -> go.Figure:
    """Heatmap with value annotations in each cell.

    Args:
        df: Rows = y-axis labels, columns = x-axis labels, values = cell colors.
        colorscale: Plotly colorscale name (default: RdYlGn — red=low, green=high).
    """
    fig = go.Figure(
        go.Heatmap(
            z=df.values,
            x=df.columns.tolist(),
            y=df.index.tolist(),
            colorscale=colorscale,
            hoverongaps=False,
            text=df.round(2).values,
            texttemplate="%{text}",
        )
    )
    fig.update_layout(title=title)
    return fig
