import re
import io
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

# 1. ตั้งค่าหน้าจอ
st.set_page_config(layout="wide", page_title="DAD Timeline Visualizer")

st.title("📊 DAD Time-Series Visualizer")

# ==========================================
# แถบตั้งค่าด้านข้าง (Sidebar)
# ==========================================
st.sidebar.header("⚙️ การแสดงผล (Display Options)")
show_max = st.sidebar.checkbox("🔴 แสดงค่าสูงสุด (Show Max)", value=False)
show_min = st.sidebar.checkbox("🔵 แสดงค่าต่ำสุด (Show Min)", value=False)

# ==========================================
# โครงสร้าง Mapping สัญญาณตามสเปคไฟล์ (Yokogawa DX/MV)
# ==========================================
col_mapping = {
    1: 4,   # CH01 -> Z#1 Top
    2: 6,   # CH02 -> Z#2 Top
    3: 8,   # CH03 -> Z#3 Top
    4: 10,  # CH04 -> Z#4 Top
    5: 12,  # CH05 -> Z#5 Top
    6: 14,  # CH06 -> Z#6 Top
    7: 16,  # CH07 -> Z#7 Top
    8: 18,  # CH08 -> Z#1 Bottom
    9: 20,  # CH09 -> Z#2 Bottom
    10: 22, # CH10 -> Z#3 Bottom
    11: 24, # CH11 -> Z#4 Bottom
    12: 26, # CH12 -> Z#5 Bottom
    13: 28, # CH13 -> Z#6 Bottom
    14: 30, # CH14 -> Z#7 Bottom
    15: 32, # CH15 -> O2 Exit
    16: 36, # CH16 -> Dryer #1
    17: 38, # CH17 -> Dryer #2
    18: 84, # CH18 -> N2 Flow
    19: 88, # CH19 -> O2 Entrance
    20: 86, # CH20 -> Dew Point
}

ch_info = {
    1: "Z#1 Top", 2: "Z#2 Top", 3: "Z#3 Top", 4: "Z#4 Top",
    5: "Z#5 Top", 6: "Z#6 Top", 7: "Z#7 Top",
    8: "Z#1 Bottom", 9: "Z#2 Bottom", 10: "Z#3 Bottom", 11: "Z#4 Bottom",
    12: "Z#5 Bottom", 13: "Z#6 Bottom", 14: "Z#7 Bottom",
    15: "O2 Exit", 16: "Dryer #1", 17: "Dryer #2", 18: "N2 Flow",
    19: "O2 Entrance", 20: "Dew Point"
}

POSSIBLE_HEADER_OFFSETS = [512, 1024, 256, 0]
POSSIBLE_RECORD_SIZES = [178, 180, 176, 184, 90, 88]
SCALE_DIVIDER = 10.0

top_names = [ch_info[i] for i in range(1, 8)]
bot_names = [ch_info[i] for i in range(8, 15)]

COLOR_PALETTE = [
    "#8e44ad", "#2980b9", "#27ae60", "#d35400", 
    "#f39c12", "#c0392b", "#16a085", "#8e44ad", 
    "#2980b9", "#27ae60", "#d35400", "#f39c12", 
    "#c0392b", "#16a085", "#e74c3c", "#2ecc71"
]

# 💡 ถอดรหัสเวลาฝัง BCD Timestamp จากแต่ละ Record ในไฟล์ไบนารี
def decode_bcd_timestamp(byte_arr):
    try:
        y = ((byte_arr[0] >> 4) * 10) + (byte_arr[0] & 0x0F)
        m = ((byte_arr[1] >> 4) * 10) + (byte_arr[1] & 0x0F)
        d = ((byte_arr[2] >> 4) * 10) + (byte_arr[2] & 0x0F)
        hh = ((byte_arr[3] >> 4) * 10) + (byte_arr[3] & 0x0F)
        mm = ((byte_arr[4] >> 4) * 10) + (byte_arr[4] & 0x0F)
        ss = ((byte_arr[5] >> 4) * 10) + (byte_arr[5] & 0x0F)
        
        if 20 <= y <= 35 and 1 <= m <= 12 and 1 <= d <= 31 and 0 <= hh <= 23 and 0 <= mm <= 59 and 0 <= ss <= 59:
            return datetime(2000 + y, m, d, hh, mm, ss)
    except Exception:
        pass
    return None

def extract_start_time_from_filename(filename):
    matches = re.findall(r'\d{6}', filename)
    if len(matches) >= 2:
        d_str = matches[-2]
        t_str = matches[-1]
        
        p1, p2, p3 = int(d_str[:2]), int(d_str[2:4]), int(d_str[4:6])
        hh, mm, ss = int(t_str[:2]), int(t_str[2:4]), int(t_str[4:6])
            
        if 20 <= p1 <= 30:  
            year, month, day = 2000 + p1, p2, p3
        elif 20 <= p3 <= 30: 
            day, month, year = p1, p2, 2000 + p3
        else:
            year, month, day = 2000 + p1, p2, p3

        try:
            return datetime(year, month, day, hh, mm, ss)
        except ValueError:
            pass
            
    return pd.to_datetime("today").replace(hour=8, minute=0, second=0, microsecond=0)

# ฟังก์ชันถอดรหัสแบบสแกน Record-by-Record
def parse_dad_binary_file(file_bytes, filename):
    best_offset = 512
    best_rsize = 178
    best_valid_cnt = -1
    
    # 1. ค้นหา Offset และขนาด Record ที่ถูกต้องที่สุด
    for offset in POSSIBLE_HEADER_OFFSETS:
        buf = file_bytes[offset:]
        if len(buf) < 178:
            continue
        for rsize in POSSIBLE_RECORD_SIZES:
            total_recs = len(buf) // rsize
            if total_recs == 0:
                continue
            
            valid_cnt = 0
            for r in range(min(total_recs, 40)):
                rec_bytes = buf[r*rsize : r*rsize + 6]
                if decode_bcd_timestamp(rec_bytes) is not None:
                    valid_cnt += 1
            
            if valid_cnt > best_valid_cnt:
                best_valid_cnt = valid_cnt
                best_offset = offset
                best_rsize = rsize

    # 2. ถอดรหัสวันที่ เวลา และสัญญาณตามโครงสร้าง Record จริง
    buf = file_bytes[best_offset:]
    total_records = len(buf) // best_rsize
    
    timestamps = []
    data_dict = {ch_info[ch]: np.zeros(total_records) for ch in range(1, 21)}
    fallback_dt = extract_start_time_from_filename(filename)
    last_valid_ts = fallback_dt
    
    for r in range(total_records):
        rec_raw = buf[r*best_rsize : (r+1)*best_rsize]
        
        # ถอดรหัส BCD Timestamp ประจำบรรทัด
        ts = decode_bcd_timestamp(rec_raw[:6])
        if ts is not None:
            timestamps.append(ts)
            last_valid_ts = ts
        else:
            if len(timestamps) > 0:
                last_valid_ts = last_valid_ts + timedelta(seconds=1)
                timestamps.append(last_valid_ts)
            else:
                timestamps.append(fallback_dt)
                
        # ถอดรหัสค่าช่องสัญญาณ (Int16 Big-Endian)
        words_in_rec = best_rsize // 2
        rec_words = np.frombuffer(rec_raw[:words_in_rec*2], dtype='>i2').astype(float) / SCALE_DIVIDER
        
        for ch_num, col_idx in col_mapping.items():
            ch_name = ch_info[ch_num]
            if col_idx < len(rec_words):
                val = rec_words[col_idx]
                # กรองค่ารหัสสถานะความผิดปกติ (Error Flags / Status Overrange) ออก
                if val < -500.0 or val > 3500.0:
                    data_dict[ch_name][r] = np.nan
                else:
                    data_dict[ch_name][r] = val
            else:
                data_dict[ch_name][r] = np.nan

    df = pd.DataFrame(data_dict)
    
    # เติมค่าเชื่อมจุดที่หายไปจากการกรอง Error Flag
    for col in df.columns:
        df[col] = df[col].interpolate(method='linear').ffill().bfill()
        
    df.insert(0, "Datetime", timestamps)
    return df

# ==========================================
# อัปโหลดไฟล์ .DAD
# ==========================================
uploaded_files = st.file_uploader("เลือกไฟล์ .DAD", type=["dad", "DAD"], accept_multiple_files=True)

if uploaded_files:
    sorted_files = sorted(uploaded_files, key=lambda x: x.name)
    all_dfs = []

    for file in sorted_files:
        try:
            binary_data = file.read()
            df_parsed = parse_dad_binary_file(binary_data, file.name)
            if df_parsed is not None and not df_parsed.empty:
                all_dfs.append(df_parsed)
        except Exception as e:
            st.error(f"เกิดข้อผิดพลาดในการอ่านไฟล์ {file.name}: {e}")

    if all_dfs:
        full_df = pd.concat(all_dfs, ignore_index=True)
        full_df = full_df.sort_values(by="Datetime").reset_index(drop=True)
        full_df = full_df.drop_duplicates(subset=["Datetime"], keep="first").reset_index(drop=True)

        num_files_str = f"({len(sorted_files)} Files)"

        # ==========================================
        # 📥 ปุ่ม Export Excel / CSV
        # ==========================================
        st.sidebar.divider()
        st.sidebar.header("📥 ดาวน์โหลดข้อมูล (Export)")

        try:
            import openpyxl
            excel_buffer = io.BytesIO()
            with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                full_df.to_excel(writer, sheet_name='All Data', index=False)
                full_df[['Datetime'] + top_names].to_excel(writer, sheet_name='Top Zones', index=False)
                full_df[['Datetime'] + bot_names].to_excel(writer, sheet_name='Bottom Zones', index=False)
                full_df[['Datetime', 'Dryer #1', 'Dryer #2']].to_excel(writer, sheet_name='Dryer', index=False)
                full_df[['Datetime', 'O2 Exit', 'O2 Entrance', 'N2 Flow']].to_excel(writer, sheet_name='O2 & N2 Flow', index=False)
                full_df[['Datetime', 'Dew Point']].to_excel(writer, sheet_name='Dew Point', index=False)

            st.sidebar.download_button(
                label="📥 ดาวน์โหลดไฟล์ Excel (.xlsx)",
                data=excel_buffer.getvalue(),
                file_name=f"DAD_Export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        except Exception:
            csv_data = full_df.to_csv(index=False).encode('utf-8-sig')
            st.sidebar.download_button(
                label="📥 ดาวน์โหลดข้อมูล (.csv)",
                data=csv_data,
                file_name=f"DAD_Export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True
            )

        with st.expander("🔍 ดูตารางข้อมูลดิบ (ตรวจเช็คความถูกต้องของตัวเลขและเวลา)"):
            st.dataframe(full_df.head(100), use_container_width=True)

        def apply_white_theme_style(fig, y_title, y_range=None, is_secondary=False):
            fig.update_layout(
                height=380,
                template="plotly_white",
                margin=dict(l=40, r=40, t=30, b=30),
                hovermode="x unified",
                legend=dict(x=1.01, y=1, xanchor="left", yanchor="top", font=dict(size=11))
            )
            fig.update_xaxes(
                title_text="Date & Time",
                tickformat="%d/%m\n%H:%M:%S",
                showgrid=True, gridcolor="#E5E5E5"
            )
            fig.update_yaxes(
                title_text=y_title,
                showgrid=True, gridcolor="#E5E5E5",
                range=y_range if y_range else None,
                autorange=True if not y_range else False,
                secondary_y=is_secondary
            )

        def add_max_min_markers(fig, df, cols, secondary_y_cols=[]):
            for col in cols:
                is_sec = col in secondary_y_cols
                if show_max:
                    max_idx = df[col].idxmax()
                    fig.add_trace(go.Scatter(
                        x=[df.loc[max_idx, "Datetime"]], y=[df.loc[max_idx, col]],
                        mode="markers+text", marker=dict(color="red", size=8, symbol="triangle-up"),
                        text=[f"Max: {df.loc[max_idx, col]:.1f}"], textposition="top center",
                        showlegend=False, hoverinfo="skip"
                    ), secondary_y=is_sec)
                if show_min:
                    min_idx = df[col].idxmin()
                    fig.add_trace(go.Scatter(
                        x=[df.loc[min_idx, "Datetime"]], y=[df.loc[min_idx, col]],
                        mode="markers+text", marker=dict(color="blue", size=8, symbol="triangle-down"),
                        text=[f"Min: {df.loc[min_idx, col]:.1f}"], textposition="bottom center",
                        showlegend=False, hoverinfo="skip"
                    ), secondary_y=is_sec)

        # 1. Top Zones
        st.subheader(f"📐 Top Zones Timeline {num_files_str}")
        fig_top = make_subplots(specs=[[{"secondary_y": False}]])
        for idx, col in enumerate(top_names):
            fig_top.add_trace(go.Scatter(
                x=full_df["Datetime"], y=full_df[col], name=col,
                line=dict(width=1.8, color=COLOR_PALETTE[idx % len(COLOR_PALETTE)]),
                hovertemplate=f"{col}: %{{y:.1f}} °C<extra></extra>"
            ))
        add_max_min_markers(fig_top, full_df, top_names)
        apply_white_theme_style(fig_top, "Temperature [°C]", y_range=None)
        st.plotly_chart(fig_top, use_container_width=True)

        # 2. Bottom Zones
        st.subheader(f"📐 Bottom Zones Timeline {num_files_str}")
        fig_bot = make_subplots(specs=[[{"secondary_y": False}]])
        for idx, col in enumerate(bot_names):
            fig_bot.add_trace(go.Scatter(
                x=full_df["Datetime"], y=full_df[col], name=col,
                line=dict(width=1.8, color=COLOR_PALETTE[idx % len(COLOR_PALETTE)]),
                hovertemplate=f"{col}: %{{y:.1f}} °C<extra></extra>"
            ))
        add_max_min_markers(fig_bot, full_df, bot_names)
        apply_white_theme_style(fig_bot, "Temperature [°C]", y_range=None)
        st.plotly_chart(fig_bot, use_container_width=True)

        # 3. Dryer
        st.subheader(f"🔥 Dryer Temperatures Timeline {num_files_str}")
        fig_dryer = make_subplots(specs=[[{"secondary_y": False}]])
        fig_dryer.add_trace(go.Scatter(
            x=full_df["Datetime"], y=full_df["Dryer #1"], name="Dryer #1", line=dict(color="#2ecc71", width=2.0)
        ))
        fig_dryer.add_trace(go.Scatter(
            x=full_df["Datetime"], y=full_df["Dryer #2"], name="Dryer #2", line=dict(color="#e67e22", width=2.0)
        ))
        add_max_min_markers(fig_dryer, full_df, ["Dryer #1", "Dryer #2"])
        apply_white_theme_style(fig_dryer, "Temperature [°C]", y_range=None)
        st.plotly_chart(fig_dryer, use_container_width=True)

        # 4. Oxygen & N2
        st.subheader(f"🧪 Oxygen Concentration & N2 Flow Timeline {num_files_str}")
        fig_o2_n2 = make_subplots(specs=[[{"secondary_y": True}]])
        fig_o2_n2.add_trace(go.Scatter(
            x=full_df["Datetime"], y=full_df["O2 Exit"], name="O2 Exit", line=dict(color="#e74c3c", width=2.0)
        ), secondary_y=False)
        fig_o2_n2.add_trace(go.Scatter(
            x=full_df["Datetime"], y=full_df["O2 Entrance"], name="O2 Entrance", line=dict(color="#3498db", width=2.0)
        ), secondary_y=False)
        fig_o2_n2.add_trace(go.Scatter(
            x=full_df["Datetime"], y=full_df["N2 Flow"], name="N2 Flow", line=dict(color="#2ecc71", width=1.5, dash="dash")
        ), secondary_y=True)
        add_max_min_markers(fig_o2_n2, full_df, ["O2 Exit", "O2 Entrance", "N2 Flow"], secondary_y_cols=["N2 Flow"])
        apply_white_theme_style(fig_o2_n2, "O2 Level [ppm]", y_range=None)
        fig_o2_n2.update_yaxes(title_text="N2 Flow", autorange=True, secondary_y=True, showgrid=False)
        st.plotly_chart(fig_o2_n2, use_container_width=True)

        # 5. Dew Point
        st.subheader(f"💧 Dew Point Timeline {num_files_str}")
        fig_dew = make_subplots(specs=[[{"secondary_y": False}]])
        fig_dew.add_trace(go.Scatter(
            x=full_df["Datetime"], y=full_df["Dew Point"], name="Dew Point", line=dict(color="#9b59b6", width=2.0)
        ))
        add_max_min_markers(fig_dew, full_df, ["Dew Point"])
        apply_white_theme_style(fig_dew, "Dew Point [°Cdp]", y_range=None)
        st.plotly_chart(fig_dew, use_container_width=True)
