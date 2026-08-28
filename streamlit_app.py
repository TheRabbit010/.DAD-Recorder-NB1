import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="DAD Auto Time-Series Plotter", layout="wide", page_icon="📈")

st.title("📈 DAD Time-Series Visualizer (Auto-Detect Time)")
st.write("อัปโหลดไฟล์ `.DAD` ระบบจะค้นหาและแปลงคอลัมน์วัน/เวลาให้อัตโนมัติ พร้อมแสดงกราฟตามลำดับเวลาจริง")

# --- ฟังก์ชันตรวจจับคอลัมน์ วัน/เวลา อัตโนมัติ ---
def detect_time_column(df):
    time_keywords = ['date', 'time', 'datetime', 'timestamp', 'เวลา', 'วันที่', 'dt']
    
    # 1. ตรวจสอบคอลัมน์ที่เป็นประเภท datetime อยู่แล้ว
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            return col
            
    # 2. ค้นหาจากชื่อคอลัมน์ที่มีคำระบุเวลา
    for col in df.columns:
        if any(kw in str(col).lower() for kw in time_keywords):
            parsed = pd.to_datetime(df[col], errors='coerce')
            if parsed.notna().sum() > 0.5 * len(df): # สามารถแปลงเป็นเวลาได้มากกว่า 50%
                return col
                
    # 3. สุ่มสแกนคอลัมน์ที่เป็นข้อความเพื่อทดลองแปลงเป็นเวลา
    for col in df.columns:
        if df[col].dtype == 'object':
            parsed = pd.to_datetime(df[col], errors='coerce')
            if parsed.notna().sum() > 0.7 * len(df):
                return col
                
    return df.columns[0]  # Fallback เลือกคอลัมน์แรกหากไม่พบ

# --- Sidebar ตั้งค่าการอ่านไฟล์ ---
st.sidebar.header("⚙️ ตั้งค่าการอ่านไฟล์")
delimiter_choice = st.sidebar.selectbox(
    "ตัวแบ่งข้อมูล (Delimiter)",
    options=["Space/Tab (อัตโนมัติ)", "Comma (,)", "Tab (\\t)", "Semicolon (;)"],
    index=0
)
sep_map = {
    "Space/Tab (อัตโนมัติ)": r'\s+',
    "Comma (,)": ',',
    "Tab (\\t)": '\t',
    "Semicolon (;)": ';'
}

# --- 1. ส่วนอัปโหลดไฟล์ ---
uploaded_files = st.file_uploader(
    "เลือกไฟล์ .DAD / .TXT / .CSV (เลือกหลายไฟล์พร้อมกันได้)",
    type=["dad", "txt", "dat", "csv"],
    accept_multiple_files=True
)

if uploaded_files:
    df_list = []
    
    for file in uploaded_files:
        try:
            temp_df = pd.read_csv(file, sep=sep_map[delimiter_choice], engine='python')
            temp_df['Source_File'] = file.name
            df_list.append(temp_df)
        except Exception as e:
            st.error(f"ไม่สามารถอ่านไฟล์ **{file.name}**: {e}")

    if df_list:
        combined_df = pd.concat(df_list, ignore_index=True)
        all_cols = [c for c in combined_df.columns if c != 'Source_File']

        # --- 2. ค้นหาและกำหนดคอลัมน์เวลาอัตโนมัติ ---
        detected_col = detect_time_column(combined_df)
        default_idx = all_cols.index(detected_col) if detected_col in all_cols else 0

        st.subheader("🛠️ การเลือกคอลัมน์ (ระบุอัตโนมัติ)")
        col1, col2 = st.columns(2)

        with col1:
            time_col = st.selectbox(
                "คอลัมน์วัน-เวลา (ระบบเลือกให้อัตโนมัติ):",
                options=all_cols,
                index=default_idx
            )

        # แปลงคอลัมน์ที่เลือกให้เป็น DateTime จริง และเรียงลำดับเวลา
        combined_df[time_col] = pd.to_datetime(combined_df[time_col], errors='coerce')
        
        # ตัดข้อมูลที่ไม่สามารถแปลงเป็นเวลาได้ออก และเรียงลำดับตามเวลาจริง
        valid_time_df = combined_df.dropna(subset=[time_col]).sort_values(by=time_col).reset_index(drop=True)

        with col2:
            signal_cols = st.multiselect(
                "เลือกคอลัมน์ค่าสัญญาณ (Y-Axis):",
                options=[c for c in all_cols if c != time_col],
                default=[c for c in all_cols if c != time_col][:1]
            )

        if not valid_time_df.empty:
            start_time = valid_time_df[time_col].min().strftime('%Y-%m-%d %H:%M:%S')
            end_time = valid_time_df[time_col].max().strftime('%Y-%m-%d %H:%M:%S')
            st.success(f"📌 ตรวจพบช่วงเวลาจริง: **{start_time}** ถึง **{end_time}** (รวม {len(valid_time_df)} จุดข้อมูล)")
        else:
            st.error("ไม่สามารถแปลงข้อมูลในคอลัมน์ที่เลือกให้เป็นวัน/เวลาได้ โปรดเลือกคอลัมน์อื่น")

        # --- 3. แสดง Interactive Graph ---
        if signal_cols and not valid_time_df.empty:
            st.subheader("📊 Interactive Time-Series Graph")

            fig = px.line(
                valid_time_df,
                x=time_col,
                y=signal_cols,
                color='Source_File' if len(signal_cols) == 1 else None,
                title="กราฟแสดงค่าสัญญาณตามลำดับเวลาจริง",
                labels={time_col: "วัน-เวลา", "value": "ค่าสัญญาณ"}
            )

            fig.update_layout(
                hovermode="x unified",
                height=600,
                xaxis=dict(
                    type="date",
                    rangeslider=dict(visible=True)
                )
            )

            st.plotly_chart(fig, use_container_width=True)

        # --- 4. ปุ่มดาวน์โหลดข้อมูล ---
        with st.expander("📄 ตารางข้อมูลที่รวมและเรียงตามเวลาแล้ว"):
            st.dataframe(valid_time_df)
            csv_data = valid_time_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="ดาวน์โหลด Combined CSV",
                data=csv_data,
                file_name="combined_time_data.csv",
                mime="text/csv"
            )
