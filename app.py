
# -*- coding: utf-8 -*-
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="Transport & Sales Dashboard", layout="wide")

# ---------- Helper: Map column names ----------
COLUMN_MAP = {
    "MX02:วันที่มอบหมายงาน": "assign_date",
    "job_id": "job_id",
    "MX12:จำนวนใบนำส่ง (ใบ)": "num_deliveries",
    "MX12:จำนวนสินค้า (รายการ)": "num_items",
    "MX12:ค่าเที่ยวขนส่ง (บาท)": "total_cost",
    "MX12:ค่าเที่ยวเพิ่มเติม (บาท)": "additional_cost",
    "MX12:เส้นทางขนส่ง": "route_name",
    "MX12:nan ส่งสำเร็จ": "success_count",
    "MX12:nan ไม่สำเร็จ": "fail_count"
}

# ---------- Sidebar: Upload File ----------
st.sidebar.header("📂 Upload Excel File")
uploaded_file = st.sidebar.file_uploader("Upload master_dataset.xlsx", type=["xlsx"])

if uploaded_file is None:
    st.info("กรุณาอัปโหลดไฟล์ master_dataset.xlsx ก่อน")
    st.stop()

# ---------- Load Data ----------
df_raw = pd.read_excel(uploaded_file, sheet_name=0)
df = df_raw.rename(columns={old: new for old, new in COLUMN_MAP.items() if old in df_raw.columns})

# Convert date
if "assign_date" in df.columns:
    df["assign_date"] = pd.to_datetime(df["assign_date"], errors="coerce", dayfirst=True)

# Fill missing cost columns if absent
df["total_cost"] = pd.to_numeric(df.get("total_cost", 0), errors="coerce").fillna(0)
df["additional_cost"] = pd.to_numeric(df.get("additional_cost", 0), errors="coerce").fillna(0)

# Create total cost combined
df["cost_sum"] = df["total_cost"] + df["additional_cost"]

# ---------- Filters ----------
st.sidebar.subheader("🔍 Filters")
if "assign_date" in df.columns:
    min_date, max_date = df["assign_date"].min(), df["assign_date"].max()
    date_range = st.sidebar.date_input("ช่วงวันที่", (min_date, max_date))
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
        df = df[(df["assign_date"] >= start_date) & (df["assign_date"] <= end_date)]

if "route_name" in df.columns:
    route_filter = st.sidebar.multiselect("เลือกเส้นทาง", options=df["route_name"].dropna().unique())
    if route_filter:
        df = df[df["route_name"].isin(route_filter)]

# ---------- Section 1: Operational Summary ----------
st.title("📊 Transport & Sales Dashboard")

col1, col2, col3 = st.columns(3)
col1.metric("Total Jobs", f"{df['job_id'].nunique():,}")
col2.metric("Total Deliveries", f"{df['num_deliveries'].sum():,}")
col3.metric("Total Items", f"{df['num_items'].sum():,}")

if "assign_date" in df.columns:
    trend_df = df.groupby("assign_date").agg(
        jobs=("job_id", "nunique"),
        deliveries=("num_deliveries", "sum"),
        items=("num_items", "sum")
    ).reset_index()

    fig = go.Figure()
    fig.add_trace(go.Bar(x=trend_df["assign_date"], y=trend_df["deliveries"], name="Deliveries"))
    fig.add_trace(go.Scatter(x=trend_df["assign_date"], y=trend_df["items"], name="Items", yaxis="y2"))

    fig.update_layout(
        title="Trend: Deliveries & Items",
        yaxis=dict(title="Deliveries"),
        yaxis2=dict(title="Items", overlaying="y", side="right")
    )
    st.plotly_chart(fig, use_container_width=True)

# ---------- Section 2: Cost Analysis ----------
st.header("💰 Cost Analysis")
total_cost_sum = df["cost_sum"].sum()
avg_cost_job = df["cost_sum"].mean()
st.metric("Total Cost", f"{total_cost_sum:,.0f} ฿")
st.metric("Average Cost / Job", f"{avg_cost_job:,.0f} ฿")

cost_breakdown = pd.DataFrame({
    "Cost Type": ["Base Cost", "Additional Cost"],
    "Value": [df["total_cost"].sum(), df["additional_cost"].sum()]
})
fig2 = px.pie(cost_breakdown, names="Cost Type", values="Value", title="Cost Breakdown")
st.plotly_chart(fig2, use_container_width=True)

if "route_name" in df.columns:
    top_routes_cost = df.groupby("route_name")["cost_sum"].sum().reset_index().sort_values("cost_sum", ascending=False).head(10)
    fig3 = px.bar(top_routes_cost, x="route_name", y="cost_sum", title="Top 10 Routes by Total Cost")
    fig3.update_layout(xaxis_tickangle=-45)
    st.plotly_chart(fig3, use_container_width=True)

# ---------- Section 3: Route Performance (Complete) ----------
st.header("🛣 Route Performance")

if "route_name" in df.columns:
    # รวมข้อมูลตามเส้นทาง
    route_perf = df.groupby("route_name").agg(
        total_jobs=("job_id", "nunique"),
        total_cost=("cost_sum", "sum"),
        avg_cost=("cost_sum", "mean")
    ).reset_index()

    # Top Routes by total jobs (ตาราง)
    st.subheader("Top Routes by Total Jobs")
    st.dataframe(route_perf.sort_values("total_jobs", ascending=False), use_container_width=True)

    # Top 10 Routes by total cost (กราฟแนวตั้ง)
    st.subheader("Top 10 Routes by Total Cost")
    top_routes_cost = route_perf.sort_values("total_cost", ascending=False).head(10)
    fig3 = px.bar(
        top_routes_cost,
        x="route_name",
        y="total_cost",
        title="Top 10 Routes by Total Cost",
        orientation="v"
    )
    fig3.update_layout(xaxis_tickangle=-45)
    st.plotly_chart(fig3, use_container_width=True)

    # หาว่าเส้นทางไหนประหยัดที่สุด (avg_cost ต่ำสุด)
    cheapest_route = route_perf.sort_values("avg_cost", ascending=True).head(1)
    cheapest_name = cheapest_route.iloc[0]["route_name"]
    cheapest_value = cheapest_route.iloc[0]["avg_cost"]
    st.markdown(f"**💡 เส้นทางที่ประหยัดที่สุด:** `{cheapest_name}` เฉลี่ย {cheapest_value:,.2f} บาท/งาน")

    # Top 10 cheapest และ Top 10 most expensive (avg cost)
    cheapest_routes = route_perf.sort_values("avg_cost", ascending=True).head(10)
    expensive_routes = route_perf.sort_values("avg_cost", ascending=False).head(10)

    fig4 = px.bar(
        cheapest_routes,
        x="route_name",
        y="avg_cost",
        title="Top 10 Cheapest Routes (Avg Cost/Job)",
        orientation="v"
    )
    fig4.update_layout(xaxis_tickangle=-45)
    st.plotly_chart(fig4, use_container_width=True)

    fig5 = px.bar(
        expensive_routes,
        x="route_name",
        y="avg_cost",
        title="Top 10 Most Expensive Routes (Avg Cost/Job)",
        orientation="v"
    )
    fig5.update_layout(xaxis_tickangle=-45)
    st.plotly_chart(fig5, use_container_width=True)

else:
    st.info("ไม่มีคอลัมน์ route_name สำหรับวิเคราะห์เส้นทาง")

# ---------- Section 4: Delivery Performance ----------
st.header("🚚 Delivery Performance")
if "success_count" in df.columns and "fail_count" in df.columns:
    total_success = df["success_count"].sum()
    total_fail = df["fail_count"].sum()
    total_deliveries = total_success + total_fail
    success_pct = (total_success / total_deliveries * 100) if total_deliveries else 0
    fail_pct = (total_fail / total_deliveries * 100) if total_deliveries else 0

    col1, col2 = st.columns(2)
    col1.metric("Success %", f"{success_pct:.2f}%")
    col2.metric("Fail %", f"{fail_pct:.2f}%")

    perf_df = pd.DataFrame({
        "Status": ["Success", "Fail"],
        "Count": [total_success, total_fail]
    })
    fig4 = px.pie(perf_df, names="Status", values="Count", title="Delivery Success vs Fail")
    st.plotly_chart(fig4, use_container_width=True)

# ---------- Data Table & Export ----------
st.subheader("📄 Filtered Data")
st.dataframe(df, use_container_width=True)

csv_data = df.to_csv(index=False).encode("utf-8-sig")
st.download_button("⬇️ Download CSV", data=csv_data, file_name="filtered_data.csv", mime="text/csv")


# ---------- Summary Insight ----------
st.header("📝 Summary Insight: ทำไมการนำเสนอแต่ละส่วนถึงสำคัญ")

st.markdown("""
**✅ 1. ภาพรวมการขนส่ง (Operational Summary)**  
- แสดงปริมาณงาน, จำนวนการส่งมอบ และจำนวนสินค้ารวมในแต่ละช่วงเวลา  
- **ประโยชน์:** ทำให้เห็นแนวโน้มการทำงาน ช่วงไหนงานหนาแน่น ต้องเพิ่มทรัพยากร หรือช่วงไหนเบาเพื่อลดต้นทุน

**💰 2. การวิเคราะห์ต้นทุน (Cost Analysis)**  
- แสดงต้นทุนรวม, ต้นทุนเฉลี่ยต่อเที่ยว และสัดส่วนค่าใช้จ่ายหลัก-เพิ่มเติม  
- **ประโยชน์:** ใช้ระบุจุดที่ต้นทุนสูงผิดปกติ และช่วยตัดสินใจเจรจาราคาหรือปรับแผนการจัดส่ง

**🗺️ 3. การวิเคราะห์เส้นทาง (Route Performance)**  
- แสดงเส้นทางที่มีงานมากที่สุด, ต้นทุนรวมสูงสุด, และเส้นทางที่ประหยัดที่สุด  
- **ประโยชน์:** ช่วยเลือกเส้นทางที่คุ้มค่าที่สุด ลดการใช้เส้นทางที่สิ้นเปลือง และวางแผนเพิ่มประสิทธิภาพ

**🚚 4. คุณภาพการส่งมอบ (Delivery Performance)**  
- แสดง % ส่งสำเร็จและไม่สำเร็จ พร้อมภาพรวมคุณภาพการบริการ  
- **ประโยชน์:** ใช้ติดตามคุณภาพการให้บริการและแก้ไขปัญหา เพื่อรักษาความพึงพอใจของลูกค้า
""")
