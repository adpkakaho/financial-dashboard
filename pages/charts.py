"""
pages/charts.py
===============
공통 Plotly 차트 생성 헬퍼
"""

import plotly.graph_objects as go
import pandas as pd

_GRID  = "#F1F5F9"
_WHITE = "#fff"
_LAYOUT_BASE = dict(
    plot_bgcolor=_WHITE,
    paper_bgcolor=_WHITE,
    margin=dict(l=0, r=0, t=20, b=0),
)


def make_line(df: pd.DataFrame, x: str, y: str,
              color: str = "#2563EB", height: int = 200,
              y_suffix: str = "", title: str = "") -> go.Figure:
    """날짜 x축 라인차트"""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df[x], y=df[y],
        mode="lines+markers",
        line=dict(color=color, width=2),
        marker=dict(size=4, color=color),
        name=y,
    ))
    fig.update_layout(
        height=height,
        title=dict(text=title, font=dict(size=12, color="#475569")),
        xaxis=dict(showgrid=True, gridcolor=_GRID, tickformat="%m/%d", tickangle=0),
        yaxis=dict(showgrid=True, gridcolor=_GRID, ticksuffix=y_suffix),
        **_LAYOUT_BASE,
    )
    return fig


def make_bar(df: pd.DataFrame, x: str, y: str,
             color: str = "#2563EB", height: int = 200,
             neg_color: str = "#EF4444", y_suffix: str = "") -> go.Figure:
    """날짜 x축 바차트 (양/음 색상 자동 분리)"""
    colors = [color if float(v) >= 0 else neg_color for v in df[y]]
    fig = go.Figure(go.Bar(x=df[x], y=df[y], marker_color=colors))
    fig.update_layout(
        height=height,
        xaxis=dict(showgrid=False, tickformat="%m/%d", tickangle=0),
        yaxis=dict(showgrid=True, gridcolor=_GRID, ticksuffix=y_suffix),
        **{**_LAYOUT_BASE, "margin": dict(l=0, r=0, t=10, b=0)},
    )
    return fig


def make_dual_axis(df: pd.DataFrame,
                   bar_x: str, bar_y: str, bar_colors: list,
                   line_x: str, line_y: str,
                   bar_name: str = "", line_name: str = "",
                   line_color: str = "#D97706",
                   height: int = 220) -> go.Figure:
    """이중 Y축 (바 + 라인) 차트"""
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df[bar_x], y=df[bar_y],
        name=bar_name, yaxis="y2",
        marker_color=bar_colors,
    ))
    fig.add_trace(go.Scatter(
        x=df[line_x], y=df[line_y],
        name=line_name,
        line=dict(color=line_color, width=2.5),
        marker=dict(size=5),
    ))
    fig.update_layout(
        height=height,
        xaxis=dict(tickformat="%y/%m", tickangle=0),
        yaxis=dict(title=line_y, gridcolor=_GRID),
        yaxis2=dict(title=bar_y, overlaying="y", side="right"),
        legend=dict(orientation="h", y=1.1),
        **{**_LAYOUT_BASE, "margin": dict(l=0, r=0, t=10, b=0)},
    )
    return fig


def kpi_card(label: str, value: str, sub: str, color: str, src: str,
             top_border: bool = True) -> str:
    border_top = f"border-top: 3px solid {color};" if top_border else ""
    return f"""
    <div class="kpi-card" style="{border_top}">
      <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
        <span class="kpi-label">{label}</span>
        <span class="src-badge">{src}</span>
      </div>
      <div class="kpi-value" style="color:{color};">{value}</div>
      <div class="kpi-sub">{sub}</div>
    </div>
    """
