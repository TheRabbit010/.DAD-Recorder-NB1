import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

def render_interactive_charts(df: pd.DataFrame):
    """
    ฟังก์ชันสำหรับสร้างและแสดงผล Interactive Graphs แยกตาม Zone
    รองรับทั้งคอลัมน์แบบมาตรฐาน (CH001_MAX) และแบบมี Tag (CH001 [Z#1 Top]_MAX)
    """
    # 1. จัดสรรแกน เวลา (Datetime)
    if "Datetime" not in df.columns:
        if "Date" in df.columns and "Time" in df.columns:
            df["Datetime"] = pd.to_datetime(df["Date"].astype(str) + " " + df["Time"].astype(str))
        else:
            df["Datetime"] = df.index

    # ชุดสีมาตรฐาน 7 เฉดสีสำหรับ 7 โซน
    colors = ["#8e44ad", "#2980b9", "#27ae60", "#d35400", "#f39c12", "#c0392b", "#16a085"]

    # ฟังก์ชันช่วยค้นหาชื่อคอลัมน์ใน DataFrame
    def find_column(keywords):
        for col in df.columns:
            if all(kw in col for kw in keywords):
                return col
        return None

    # ==========================================
    # Graph 1: Top Zones (CH001 - CH007 MAX)
    # ==========================================
    fig_top = go.Figure()
    for i in range(1, 8):
        ch_str = f"CH{str(i).zfill(3)}"
        col_name = find_column([ch_str, "MAX"]) or find_column([f"Z#{i} Top"])
        if col_name:
            fig_top.add_trace(go.Scatter(
                x=df["Datetime"], 
                y=df[col_name], 
                name=f"Z#{i} Top",
                mode="lines", 
                line=dict(width=1.8, color=colors[(i-1) % len(colors)]),
                hovertemplate=f"Z#{i} Top: %{{y:.1f}} °C<extra></extra>"
            ))

    fig_top.update_layout(
        title="📐 Top Zones Temperature Profile (Z#1 - Z#7)",
        xaxis_title="Date & Time",
        yaxis_title="Temperature [°C]",
        template="plotly_white",
        height=400,
        hovermode="x unified",
        legend=dict(orientation="h", y=1.12, x=1, xanchor="right")
    )
    st.plotly_chart(fig_top, use_container_width=True)

    # ==========================================
    # Graph 2: Bottom Zones (CH008 - CH014 MAX)
    # ==========================================
    fig_bot = go.Figure()
    for i in range(8, 15):
        zone_num = i - 7
        ch_str = f"CH{str(i).zfill(3)}"
        col_name = find_column([ch_str, "MAX"]) or find_column([f"Z#{zone_num} Bottom"])
        if col_name:
            fig_bot.add_trace(go.Scatter(
                x=df["Datetime"], 
                y=df[col_name], 
                name=f"Z#{zone_num} Bottom",
                mode="lines", 
                line=dict(width=1.8, color=colors[(zone_num-1) % len(colors)]),
                hovertemplate=f"Z#{zone_num} Bottom: %{{y:.1f}} °C<extra></extra>"
            ))

    fig_bot.update_layout(
        title="📐 Bottom Zones Temperature Profile (Z#1 - Z#7)",
        xaxis_title="Date & Time",
        yaxis_title="Temperature [°C]",
        template="plotly_white",
        height=400,
        hovermode="x unified",
        legend=dict(orientation="h", y=1.12, x=1, xanchor="right")
    )
    st.plotly_chart(fig_bot, use_container_width=True)

    # ==========================================
    # Graph 3 & 4: Dryers & Dew Point (Side-by-Side)
    # ==========================================
    col_left, col_right = st.columns(2)

    with col_left:
        fig_dryer = go.Figure()
        d1_col = find_column(["CH016", "MAX"]) or find_column(["Dryer #1"])
        d2_col = find_column(["CH017", "MAX"]) or find_column(["Dryer #2"])
        
        if d1_col:
            fig_dryer.add_trace(go.Scatter(x=df["Datetime"], y=df[d1_col], name="Dryer #1", line=dict(color="#2ecc71", width=2)))
        if d2_col:
            fig_dryer.add_trace(go.Scatter(x=df["Datetime"], y=df[d2_col], name="Dryer #2", line=dict(color="#e67e22", width=2)))

        fig_dryer.update_layout(
            title="🔥 Dryer Temperatures",
            xaxis_title="Date & Time",
            yaxis_title="Temperature [°C]",
            template="plotly_white",
            height=380,
            hovermode="x unified"
        )
        st.plotly_chart(fig_dryer, use_container_width=True)

    with col_right:
        fig_dew = go.Figure()
        dew_col = find_column(["CH020", "MAX"]) or find_column(["Dew Point"])
        if dew_col:
            fig_dew.add_trace(go.Scatter(x=df["Datetime"], y=df[dew_col], name="Dew Point", line=dict(color="#9b59b6", width=2)))

        fig_dew.update_layout(
            title="💧 Dew Point Profile",
            xaxis_title="Date & Time",
            yaxis_title="Dew Point [°Cdp]",
            template="plotly_white",
            height=380,
            hovermode="x unified"
        )
        st.plotly_chart(fig_dew, use_container_width=True)

    # ==========================================
    # Graph 5: Gas & Atmosphere Control (Dual Y-Axis)
    # ==========================================
    fig_gas = make_subplots(specs=[[{"secondary_y": True}]])
    o2_exit_col = find_column(["CH015", "MAX"]) or find_column(["O2 Exit"])
    o2_ent_col = find_column(["CH019", "MAX"]) or find_column(["O2 Entrance"])
    n2_col = find_column(["CH018", "MAX"]) or find_column(["N2 Flow"])

    if o2_exit_col:
        fig_gas.add_trace(go.Scatter(x=df["Datetime"], y=df[o2_exit_col], name="O2 Exit", line=dict(color="#e74c3c", width=2)), secondary_y=False)
    if o2_ent_col:
        fig_gas.add_trace(go.Scatter(x=df["Datetime"], y=df[o2_ent_col], name="O2 Entrance", line=dict(color="#3498db", width=2)), secondary_y=False)
    if n2_col:
        fig_gas.add_trace(go.Scatter(x=df["Datetime"], y=df[n2_col], name="N2 Flow Rate", line=dict(color="#2ecc71", width=1.5, dash="dash")), secondary_y=True)

    fig_gas.update_layout(
        title="🧪 Atmosphere & Gas Control",
        xaxis_title="Date & Time",
        template="plotly_white",
        height=400,
        hovermode="x unified"
    )
    fig_gas.update_yaxes(title_text="O2 Level [ppm]", secondary_y=False)
    fig_gas.update_yaxes(title_text="N2 Flow Rate", secondary_y=True, showgrid=False)
    st.plotly_chart(fig_gas, use_container_width=True)


# ==========================================
# เรียกใช้งานฟังก์ชัน (ตัวอย่างการต่อเข้ากับ Streamlit)
# ==========================================
if "converted_df" in st.session_state:
    render_interactive_charts(st.session_state["converted_df"])
