import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# 1. โหลดข้อมูลจากไฟล์ .DAD (แก้ชื่อไฟล์ให้ตรงกับของคุณ)
file_path = 'data_file.dad'

try:
    # กรณีที่ 1: ข้อมูลคั่นด้วยช่องว่างหรือ Tab (พบบ่อยที่สุดในไฟล์ประเภทนี้)
    df = pd.read_csv(file_path, sep=r'\s+', engine='python')
except Exception as e:
    # กรณีที่ 2: ถ้าเกิดข้อผิดพลาด ลองโหลดแบบคั่นด้วยเครื่องหมายจุลภาค (Comma)
    df = pd.read_csv(file_path)

# แสดงหน้าตาข้อมูล 5 แถวแรกเพื่อตรวจสอบชื่อคอลัมน์ใน Terminal
print("--- ตรวจสอบข้อมูล 5 แถวแรก ---")
print(df.head())
print("-----------------------------\n")

# 2. ตรวจสอบและเลือกชื่อคอลัมน์มาพล็อต
# ตัวอย่าง: สมมติว่ามีคอลัมน์ชื่อ 'Time' และ 'Value' (ให้เปลี่ยนเป็นชื่อคอลัมน์จริงของคุณ)
x_column = df.columns[0] # เลือกคอลัมน์แรกเป็นแกน X
y_column = df.columns[1] # เลือกคอลัมน์ที่สองเป็นแกน Y

print(f"กำลังพล็อตกราฟโดยใช้แกน X: {x_column} และแกน Y: {y_column}")

# 3. สร้าง Interactive Graph ด้วย Plotly
fig = px.line(
    df, 
    x=x_column, 
    y=y_column, 
    title=f"Interactive Graph จากไฟล์ .DAD ({y_column} vs {x_column})",
    template="plotly_dark"  # มีธีมให้เลือก เช่น 'plotly', 'plotly_white', 'plotly_dark'
)

# ปรับแต่งเพิ่มเติมให้กราฟดูง่ายขึ้น (ซูมเฉพาะจุด, แสดงแถบเครื่องมือ)
fig.update_layout(
    hovermode="x unified", # แสดงค่าแกน X และ Y พร้อมกันเมื่อเอาเมาส์ไปชี้
    xaxis_title=x_column,
    yaxis_title=y_column
)

# 4. เปิดแสดงผลกราฟบนเว็บเบราว์เซอร์อัตโนมัติ
fig.show()

# (ตัวเลือกเสริม) บันทึกกราฟเก็บไว้เป็นไฟล์ HTML เพื่อส่งต่อให้คนอื่นเปิดดูแบบ Interactive ได้
# fig.write_html("interactive_chart.html")
