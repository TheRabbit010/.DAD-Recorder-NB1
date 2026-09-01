import streamlit as st
import pandas as pd
import numpy as np
import re
from datetime import datetime

# ==========================================
# 1. ตั้งค่าหน้าจอ
# ==========================================
st.set_page_config(layout="wide", page_title="DAD Full Raw Data Extractor")
st.title("📄 DAD Full Raw Data Extractor")
st.markdown("ดึงข้อมูลดิบทั้งหมด 90 ช่องสัญญาณ (CH_00 ถึง CH_89) โดยไม่มีการฟิลเตอร์ใดๆ")

def clear_data_state():
    if "converted_df" in st.session_state:
        del st.session_state["converted_df"]

# ==========================================
# 2. โครงสร้างไฟล์ .DAD
# ==========================================
HEADER_OFFSET = 512
TOTAL_CHANNELS = 90  # จำนวนช่องสัญญาณทั้งหมดต่อ 1 บรรทัด
SCALE_DIVIDER = 10.0
DTYPE_STR = ">i2"

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
    
    with st.spinner("กำลังสกัดข้อมูลทั้ง 90 ช่องสัญญาณ..."):
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

                # 💡 ดึงข้อมูลทุกช่อง (0 ถึง 89) โดยตั้งชื่อคอลัมน์เป็น CH_00 ถึง CH_89
                data_dict = {}
                for i in range(TOTAL_CHANNELS):
                    col_name = f"CH_{str(i).zfill(2)}"
                    data_dict[col_name] = reshaped_data[:, i]

                df_single = pd.DataFrame(data_dict)
                
                # สร้างเวลา
                time_axis = pd.date_range(start=start_dt, periods=points_per_channel, freq="10s")
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
    
    st.success("✅ โหลดข้อมูลครบทั้ง 90 ช่องสัญญาณสำเร็จ!")
    
    st.divider()
    st.subheader("📊 พรีวิวตารางข้อมูลดิบทั้งหมด (CH_00 ถึง CH_89)")
    st.dataframe(df_ready.head(100), use_container_width=True)

    csv_data = df_ready.to_csv(index=False).encode('utf-8-sig')
    
    st.download_button(
        label="📥 ดาวน์โหลดไฟล์ CSV (90 Channels)",
        data=csv_data,
        file_name=f"DAD_All_Channels_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv",
        type="primary",
        use_container_width=True
    )
