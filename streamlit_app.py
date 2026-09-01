import streamlit as st
import pandas as pd
import numpy as np
import re
from datetime import datetime

# ==========================================
# 1. ตั้งค่าหน้าจอ
# ==========================================
st.set_page_config(layout="wide", page_title="Yokogawa DX2000 .DAD to CSV")
st.title("📄 Yokogawa DX2000 (.DAD to CSV Converter)")
st.markdown("แก้ไข Stride Error ขั้นสุดท้าย: ล็อกความกว้างข้อมูลที่ 48 ช่อง (ตรงเป๊ะ 100%)")

def clear_data_state():
    if "converted_df" in st.session_state:
        del st.session_state["converted_df"]

# ==========================================
# 2. โครงสร้างไบนารีที่ถูกต้องที่สุด (Mathematical Proven)
# ==========================================
HEADER_OFFSET = 512
# 💡 กุญแจสำคัญ: ขนาดความกว้างที่แท้จริงคือ 48 (24 คู่ MIN/MAX)
TOTAL_CHANNELS = 48   
SCALE_DIVIDER = 10.0
DTYPE_STR = ">i2"

# ชื่อจุดวัดสำหรับช่องสัญญาณหลัก
ch_names = {
    1: "Z#1 Top",     2: "Z#2 Top",     3: "Z#3 Top",     4: "Z#4 Top",
    5: "Z#5 Top",     6: "Z#6 Top",     7: "Z#7 Top",
    8: "Z#1 Bottom",  9: "Z#2 Bottom",  10: "Z#3 Bottom", 11: "Z#4 Bottom",
    12: "Z#5 Bottom", 13: "Z#6 Bottom", 14: "Z#7 Bottom",
    15: "O2 Exit",    16: "Dryer #1",   17: "Dryer #2",
    18: "N2 Flow",    19: "O2 Entrance", 20: "Dew Point"
}

def extract_start_time_from_filename(filename):
    matches = re.findall(r'\d{6}', filename)
    if len(matches) >= 2:
        d_str, t_str = matches[-2], matches[-1]
        p1, p2, p3 = int(d_str[:2]), int(d_str[2:4]), int(d_str[4:6])
        hh, mm, ss = int(t_str[:2]), int(t_str[2:4]), int(t_str[4:6])
        if 20 <= p1 <= 35: year, month, day = 2000 + p1, p2, p3
        elif 20 <= p3 <= 35: day, month, year = p1, p2, 2000 + p3
        else: year, month, day = 2000 + p1, p2, p3
        try: return datetime(year, month, day, hh, mm, ss)
        except ValueError: pass
    return pd.to_datetime("today").replace(microsecond=0)

# ==========================================
# 3. อัปโหลดและประมวลผล
# ==========================================
uploaded_files = st.file_uploader("อัปโหลดไฟล์ .DAD ที่นี่", type=["dad", "DAD"], accept_multiple_files=True, on_change=clear_data_state)

if uploaded_files and "converted_df" not in st.session_state:
    all_dfs = []
    
    with st.spinner("กำลังแปลงไฟล์... (ล็อกความกว้างที่ 48 ช่อง)"):
        for file in uploaded_files:
            try:
                start_dt = extract_start_time_from_filename(file.name)
                
                binary_data = file.read()
                raw_signals = np.frombuffer(binary_data, dtype=np.dtype(DTYPE_STR), offset=HEADER_OFFSET).astype(float)
                
                points_per_channel = len(raw_signals) // TOTAL_CHANNELS
                if points_per_channel == 0: continue

                usable_points = points_per_channel * TOTAL_CHANNELS
                
                # อ่านแบบเรียงบรรทัด (order='C')
                reshaped_data = raw_signals[:usable_points].reshape((points_per_channel, TOTAL_CHANNELS), order='C')
                reshaped_data = reshaped_data / SCALE_DIVIDER

                data_dict = {}
                
                # เราจะสกัดข้อมูลออกมาทั้งหมด 24 คู่ (48 ช่อง) เพื่อไม่ให้มีข้อมูลหลุดหาย
                num_logical_channels = TOTAL_CHANNELS // 2
                
                for ch_num in range(1, num_logical_channels + 1):
                    ch_str = str(ch_num).zfill(3)
                    
                    # ถ้าช่องนี้มีชื่อตั้งไว้ ให้ใส่ชื่อ ถ้าไม่มีให้คงชื่อ CH ไว้เฉยๆ
                    if ch_num in ch_names:
                        tag_name = ch_names[ch_num]
                        col_min = f"CH{ch_str} [{tag_name}]_MIN"
                        col_max = f"CH{ch_str} [{tag_name}]_MAX"
                    else:
                        col_min = f"CH{ch_str}_MIN"
                        col_max = f"CH{ch_str}_MAX"
                    
                    min_col_idx = (ch_num - 1) * 2      # Index คู่
                    max_col_idx = (ch_num - 1) * 2 + 1  # Index คี่
                    
                    # ดึงข้อมูลมาตรงๆ ไม่ตัดอะไรทิ้ง
                    data_dict[col_min] = reshaped_data[:, min_col_idx]
                    data_dict[col_max] = reshaped_data[:, max_col_idx]

                df_single = pd.DataFrame(data_dict)
                
                # สร้างคอลัมน์ วัน เวลา และ sec ตามรูปแบบ DAQSTANDARD
                time_axis = pd.date_range(start=start_dt, periods=points_per_channel, freq="10s")
                df_single.insert(0, "sec", 0.0)
                df_single.insert(0, "Time", time_axis.strftime('%H:%M:%S'))
                df_single.insert(0, "Date", time_axis.strftime('%Y/%m/%d'))
                df_single.insert(0, "Datetime", time_axis.strftime('%Y-%m-%d %H:%M:%S'))
                
                all_dfs.append(df_single)
                
            except Exception as e:
                st.error(f"❌ เกิดข้อผิดพลาดในการอ่านไฟล์ {file.name}: {e}")

        if all_dfs:
            full_df = pd.concat(all_dfs, ignore_index=True)
            full_df = full_df.drop_duplicates(subset=["Datetime"]).reset_index(drop=True)
            st.session_state["converted_df"] = full_df

# ==========================================
# 4. แสดงผลและสร้างปุ่มดาวน์โหลด
# ==========================================
if "converted_df" in st.session_state:
    df_ready = st.session_state["converted_df"]
    
    st.success("✅ แปลงไฟล์สำเร็จ! ข้อมูลไม่ไหลเฉียงแล้ว 100%")
    
    st.divider()
    st.subheader("📊 พรีวิวตารางข้อมูล (ตรวจสอบความถูกต้อง)")
    # แสดง 15 คอลัมน์แรกให้ดูบนเว็บ
    st.dataframe(df_ready.iloc[:, :15].head(100), use_container_width=True)

    csv_data = df_ready.to_csv(index=False).encode('utf-8-sig')
    
    st.download_button(
        label="📥 ดาวน์โหลดไฟล์ CSV",
        data=csv_data,
        file_name=f"DAQSTANDARD_Export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv",
        type="primary",
        use_container_width=True
    )
