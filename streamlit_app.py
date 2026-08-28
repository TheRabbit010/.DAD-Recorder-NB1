import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime

# 1. ตั้งค่าหน้าจอ
st.set_page_config(layout="wide", page_title="DAD Timeline Visualizer")

st.title("📊 DAD Time-Series Visualizer")

# ==========================================
# แถบตั้งค่าด้านข้าง (Sidebar)
# ==========================================
st.sidebar.header("⏰ การตั้งค่าเวลา (Time Settings)")
start_date = st.sidebar.date_input("วันที่เริ่มต้นไฟล์แรก", pd.to_datetime("today"))
start_time = st.sidebar.time_input("เวลาเริ่มต้นไฟล์แรก", pd.to_datetime("08:00").time())
sample_rate_sec = st.sidebar.number_input("ความถี่ในการบันทึก (วินาที/จุด)", min_value=0.1, value=1.0, step=0.1)
current_start_datetime = datetime.combine(start_date, start_time)

st.sidebar.divider()
st.sidebar.header("🔧 การถอดรหัสไฟล์ (Binary Decoder)")
endian_option = st.sidebar.selectbox("ระบบลำดับไบต์ (Byte Order)", ["Big-Endian (>i2) - Yokogawa", "Little-Endian (<i2)"], index=0)
scale_divider = st.sidebar.number_input("ตัวหารปรับสเกลค่า (Divider)", value=10.0, step=1.0, help="เช่น 6141 / 10.0 = 614.1 °C")
header_offset = st.sidebar.number_input("Header Offset (Bytes)", value=512, step=64)

st.sidebar.divider()
st.sidebar.header("⚙️ แสดงผล (Display Options)")
show_max = st.sidebar.checkbox("🔴 แสดงค่าสูงสุด (Show Max)", value=False)
show_min = st.sidebar.checkbox("🔵 แสดงค่าต่ำสุด (Show Min)", value=False)

dtype_str = ">i2" if "Big-Endian" in endian_option else "<i2"

# ==========================================
# การกำหนด Mapping สัญญาณตาม ch_info (20 Channels)
# ==========================================
ch_info = {
    1: "Z#1 Top",
    2: "Z#2 Top",
    3: "Z#3 Top",
    4: "Z#4 Top",
    5: "Z#5 Top",
    6: "Z#6 Top",
    7: "Z#7 Top",
    8: "Z#1 Bottom",
    9: "Z#2 Bottom",
    10: "Z#3 Bottom",
    11: "Z#4 Bottom",
    12: "Z#5 Bottom",
    13: "Z#6 Bottom",
    14: "Z#7 Bottom",
    15: "O2 Exit",
    16: "Dryer #1",
    17: "Dryer #2",
    18: "N2 Flow",
    19: "O2 Entrance",
    20: "Dew Point"
}

top_names = [ch_info[i] for i in range(1, 8)]
bot_names = [ch_info[i] for i in range(8, 15)]
col_names = [ch_info[i] for i in range(1, 21)]
num_channels = len(col_names)

# ==========================================
# อัปโหลดและประมวลผลไฟล์
# ==========================================
uploaded_files = st.file_uploader("เลือกไฟล์ .DAD / .DAT", type=["dad", "dat"], accept_multiple_files=True)

if uploaded_files:
    sorted_files = sorted(uploaded_files, key=lambda x: x.name)
    all_dfs = []

    for file in sorted_files:
        try:
            binary_data = file.read()
            raw_signals = np.frombuffer(binary_data, dtype=np.dtype(dtype_str), offset=int(header_offset)).astype(float)
            
            if scale_divider != 0:
                raw_signals = raw_signals / scale_divider

            points_per_channel = len(raw_signals) // num_channels
            reshaped_data = raw_signals[:points_per_channel * num_channels].reshape(points_per_channel, num_channels)

            time_freq = f"{int(sample_rate_sec * 1000)}ms"
            time_axis = pd.date_range(start=current_start_datetime, periods=points_per_channel, freq=time_freq)
            
            current_start_datetime = time_axis[-1] + pd.Timedelta(seconds=sample_rate_sec)

            df_single = pd.DataFrame(reshaped_data, columns=col_names)
            df_single.insert(0, "Datetime", time_axis)
            all_dfs.append(df_single)

        except Exception as e:
            st.error(f"เกิดข้อผิดพลาดในการอ่านไฟล์ {file.name}: {e}")

    if all_dfs:
        full_df = pd.concat(all_dfs, ignore_index=True)
        num_files_str = f"({len(sorted_files)} Files)"

        with st.expander("🔍 ดูตารางข้อมูลรวมทุกไฟล์ (Combined Dataset)"):
            st.dataframe(full_df.head(100), use_container_width=True)

        def add_max_min_markers(fig, df, cols, secondary_y_cols=[]):
            for col in cols:
                is_sec = col in secondary_y_cols
                if show_max:
                    max_idx = df[col].idxmax()
                    fig.add_trace(go.Scatter(
                        x=[df.loc[max_idx, "Datetime"]], y=[df.loc[max_idx, col]],
                        mode="markers+text", marker=dict(color="red", size=7, symbol="triangle-up"),
                        text=[f"Max: {df.loc[max_idx, col]:.1f}"], textposition="top center",
                        showlegend=False, hoverinfo="skip"
                    ), secondary_y=is_sec)
                if show_min:
                    min_idx = df[col].idxmin()
                    fig.add_trace(go.Scatter(
                        x=[df.loc[min_idx, "Datetime"]], y=[df.loc[min_idx, col]],
                        mode="markers+text", marker=dict(color="blue", size=7, symbol="triangle-down"),
                        text=[f"Min: {df.loc[min_idx, col]:.1f}"], textposition="bottom center",
                        showlegend=False, hoverinfo="skip"
                    ), secondary_y=is_sec)

        # ==========================================
        # 1. Top Zones Timeline (Scale: 400 - 650 °C)
        # ==========================================
        st.subheader(f"📐 Top Zones Timeline {num_files_str}")
        fig_top = make_subplots(specs=[[{"secondary_y": False}]])
        for col in top_names:
            fig_top.add_trace(go.Scatter(
                x=full_df["Datetime"], y=full_df[col], name=col,
                hovertemplate=f"{col}: %{{y:.1f}} °C<extra></extra>"
            ))
        add_max_min_markers(fig_top, full_df, top_names)
        fig_top.update_layout(
            height=380, template="plotly_white", hovermode="x unified",
            margin=dict(l=40, r=40, t=30, b=30),
            legend=dict(x=1.05, y=1, xanchor="left", yanchor="top")
        )
        fig_top.update_xaxes(title_text="Date & Time", tickformat="%H:%M\n%b %d, %Y")
        fig_top.update_yaxes(title_text="Temperature [°C]", range=[400, 650])
        st.plotly_chart(fig_top, use_container_width=True)

        # ==========================================
        # 2. Bottom Zones Timeline (Scale: 400 - 650 °C)
        # ==========================================
        st.subheader(f"📐 Bottom Zones Timeline {num_files_str}")
        fig_bot = make_subplots(specs=[[{"secondary_y": False}]])
        for col in bot_names:
            fig_bot.add_trace(go.Scatter(
                x=full_df["Datetime"], y=full_df[col], name=col,
                hovertemplate=f"{col}: %{{y:.1f}} °C<extra></extra>"
            ))
        add_max_min_markers(fig_bot, full_df, bot_names)
        fig_bot.update_layout(
            height=380, template="plotly_white", hovermode="x unified",
            margin=dict(l=40, r=40, t=30, b=30),
            legend=dict(x=1.05, y=1, xanchor="left", yanchor="top")
        )
        fig_bot.update_xaxes(title_text="Date & Time", tickformat="%H:%M\n%b %d, %Y")
        fig_bot.update_yaxes(title_text="Temperature [°C]", range=[400, 650])
        st.plotly_chart(fig_bot, use_container_width=True)

        # ==========================================
        # 3. Dryer Temperatures Timeline (Scale: 0 - 400 °C)
        # ==========================================
        st.subheader(f"🔥 Dryer Temperatures Timeline {num_files_str}")
        fig_dryer = make_subplots(specs=[[{"secondary_y": False}]])

        fig_dryer.add_trace(go.Scatter(
            x=full_df["Datetime"], y=full_df["Dryer #1"], name="Dryer #1",
            line=dict(color="#00b894", width=1.5),
            hovertemplate="Dryer #1: %{y:.1f} °C<extra></extra>"
        ))
        fig_dryer.add_trace(go.Scatter(
            x=full_df["Datetime"], y=full_df["Dryer #2"], name="Dryer #2",
            line=dict(color="#ffa500", width=1.5),
            hovertemplate="Dryer #2: %{y:.1f} °C<extra></extra>"
        ))

        add_max_min_markers(fig_dryer, full_df, ["Dryer #1", "Dryer #2"])

        fig_dryer.update_layout(
            height=380, template="plotly_white", hovermode="x unified",
            margin=dict(l=40, r=40, t=30, b=30),
            legend=dict(x=1.05, y=1, xanchor="left", yanchor="top")
        )
        fig_dryer.update_xaxes(title_text="Date & Time", tickformat="%H:%M\n%b %d, %Y")
        fig_dryer.update_yaxes(title_text="Temperature [°C]", range=[0, 400])
        st.plotly_chart(fig_dryer, use_container_width=True)

        # ==========================================
        # 4. Oxygen Concentration & N2 Flow Timeline
        # ==========================================
        st.subheader(f"🧪 Oxygen Concentration & N2 Flow Timeline {num_files_str}")
        fig_o2_n2 = make_subplots(specs=[[{"secondary_y": True}]])

        fig_o2_n2.add_trace(go.Scatter(
            x=full_df["Datetime"], y=full_df["O2 Exit"], name="O2 Exit",
            line=dict(color="red", width=1.5),
            hovertemplate="O2 Exit: %{y:.1f} ppm<extra></extra>"
        ), secondary_y=False)

        fig_o2_n2.add_trace(go.Scatter(
            x=full_df["Datetime"], y=full_df["O2 Entrance"], name="O2 Entrance",
            line=dict(color="#1e90ff", width=1.5),
            hovertemplate="O2 Entrance: %{y:.1f} ppm<extra></extra>"
        ), secondary_y=False)

        fig_o2_n2.add_trace(go.Scatter(
            x=full_df["Datetime"], y=full_df["N2 Flow"], name="N2 Flow",
            line=dict(color="#2ed573", width=1.2, dash="dash"),
            hovertemplate="N2 Flow: %{y:.1f}<extra></extra>"
        ), secondary_y=True)

        add_max_min_markers(fig_o2_n2, full_df, ["O2 Exit", "O2 Entrance", "N2 Flow"], secondary_y_cols=["N2 Flow"])

        fig_o2_n2.update_layout(
            height=380, template="plotly_white", hovermode="x unified",
            margin=dict(l=40, r=40, t=30, b=30),
            legend=dict(x=1.05, y=1, xanchor="left", yanchor="top")
        )
        fig_o2_n2.update_xaxes(title_text="Date & Time", tickformat="%H:%M\n%b %d, %Y")
        fig_o2_n2.update_yaxes(title_text="O2 Level [ppm]", range=[0, 200], secondary_y=False)
        fig_o2_n2.update_yaxes(title_text="N2 Flow", autorange=True, secondary_y=True)
        st.plotly_chart(fig_o2_n2, use_container_width=True)

        # ==========================================
        # 5. Dew Point Timeline (Scale: -100 to +10 °Cdp)
        # ==========================================
        st.subheader(f"💧 Dew Point Timeline {num_files_str}")
        fig_dew = make_subplots(specs=[[{"secondary_y": False}]])

        fig_dew.add_trace(go.Scatter(
            x=full_df["Datetime"], y=full_df["Dew Point"], name="Dew Point",
            line=dict(color="#a55eea", width=1.5),
            hovertemplate="Dew Point: %{y:.1f} °Cdp<extra></extra>"
        ))

        add_max_min_markers(fig_dew, full_df, ["Dew Point"])

        fig_dew.update_layout(
            height=380, template="plotly_white", hovermode="x unified",
            margin=dict(l=40, r=40, t=30, b=30),
            legend=dict(x=1.05, y=1, xanchor="left", yanchor="top")
        )
        fig_dew.update_xaxes(title_text="Date & Time", tickformat="%H:%M\n%b %d, %Y")
        fig_dew.update_yaxes(title_text="Dew Point [°Cdp]", range=[-100, 10])
        st.plotly_chart(fig_dew, use_container_width=True)
