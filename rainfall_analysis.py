import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import io
from datetime import datetime
from openpyxl import load_workbook
from openpyxl.drawing.image import Image as XLImage
import tempfile

# Constants
MONTH_ORDER = ['January', 'February', 'March', 'April', 'May', 'June',
               'July', 'August', 'September', 'October', 'November', 'December']

def assign_water_year(df):
    df['Month'] = df['Date'].dt.month
    df['Year'] = df['Date'].dt.year
    df['Water_Year'] = df['Date'].apply(lambda x: f"{x.year}-{x.year+1}" if x.month >= 6 else f"{x.year-1}-{x.year}")
    return df

def generate_analysis(df):
    df['Month_Name'] = df['Date'].dt.month_name()

    # Annual Rainfall
    annual_rainfall = df.groupby('Water_Year')['Rainfall_mm'].sum().reset_index()
    annual_rainfall.rename(columns={'Rainfall_mm': 'Annual_Rainfall_mm'}, inplace=True)
    average_rainfall = annual_rainfall['Annual_Rainfall_mm'].mean()
    final_output = pd.concat([annual_rainfall, pd.DataFrame([{
        'Water_Year': 'Average',
        'Annual_Rainfall_mm': average_rainfall
    }])], ignore_index=True)

    # Monthly Average
    monthly_totals = df.groupby(['Water_Year', 'Month_Name'])['Rainfall_mm'].sum().reset_index()
    monthly_avg = monthly_totals.groupby('Month_Name')['Rainfall_mm'].mean().reset_index()
    monthly_avg.rename(columns={'Rainfall_mm': 'Average_Monthly_Rainfall_mm'}, inplace=True)
    monthly_avg['Month_Num'] = monthly_avg['Month_Name'].apply(lambda x: MONTH_ORDER.index(x))
    monthly_avg = monthly_avg.sort_values('Month_Num').drop(columns='Month_Num')

    # Max Daily Rainfall
    max_rainfall = df.loc[df.groupby('Water_Year')['Rainfall_mm'].idxmax()][['Water_Year', 'Rainfall_mm', 'Date']]
    max_rainfall.rename(columns={
        'Rainfall_mm': 'Max_Daily_Rainfall_mm',
        'Date': 'Date_of_Occurrence'
    }, inplace=True)

    return final_output, monthly_avg, max_rainfall

def create_plot(x, y, xlabel, ylabel, title):
    fig, ax = plt.subplots(figsize=(8,4))
    ax.plot(x, y, marker='o', linestyle='-')
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.grid(True)
    plt.xticks(rotation=45)
    plt.tight_layout()
    return fig

def export_to_excel(annual_df, monthly_df, max_df):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        with pd.ExcelWriter(tmp.name, engine='openpyxl') as writer:
            annual_df.to_excel(writer, sheet_name='Annual Rainfall', index=False)
            monthly_df.to_excel(writer, sheet_name='Monthly Averages', index=False)
            max_df.to_excel(writer, sheet_name='Max Daily Rainfall', index=False)

        # Insert plots
        wb = load_workbook(tmp.name)

        plots = [
            ('Annual Rainfall', create_plot(annual_df['Water_Year'], annual_df['Annual_Rainfall_mm'], 'Water Year', 'Annual Rainfall (mm)', 'Annual Rainfall Variations by Water Year')),
            ('Monthly Averages', create_plot(monthly_df['Month_Name'], monthly_df['Average_Monthly_Rainfall_mm'], 'Month', 'Average Monthly Rainfall (mm)', 'Average Monthly Rainfall')),
            ('Max Daily Rainfall', create_plot(max_df['Water_Year'], max_df['Max_Daily_Rainfall_mm'], 'Water Year', 'Max Daily Rainfall (mm)', 'Maximum Daily Rainfall by Water Year')),
        ]

        for sheet, fig in plots:
            image_path = tempfile.NamedTemporaryFile(delete=False, suffix=".png").name
            fig.savefig(image_path)
            img = XLImage(image_path)
            img.anchor = 'E2'
            wb[sheet].add_image(img)

        wb.save(tmp.name)

        tmp.seek(0)
        return tmp.read(), tmp.name

# Streamlit App
st.set_page_config(layout='wide')
st.title("Rainfall Data Analysis (Water Year based)")

uploaded_file = st.file_uploader("Upload CSV File", type=["csv"])

if uploaded_file:
    df = pd.read_csv(uploaded_file)
    df.columns = df.columns.str.strip()
    df['Date'] = pd.to_datetime(df['Date'], format='%d/%m/%y', errors='coerce')
    df = df.dropna(subset=['Date'])
    df = assign_water_year(df)

    st.success("File processed successfully.")

    annual_df, monthly_df, max_df = generate_analysis(df)

    st.subheader("📈 Annual Rainfall Table")
    st.dataframe(annual_df)

    st.subheader("📉 Monthly Average Rainfall Table")
    st.dataframe(monthly_df)

    st.subheader("🌧️ Maximum Daily Rainfall Table")
    st.dataframe(max_df)

    st.subheader("📊 Annual Rainfall Plot")
    st.pyplot(create_plot(annual_df['Water_Year'], annual_df['Annual_Rainfall_mm'], 'Water Year', 'Annual Rainfall (mm)', 'Annual Rainfall Variations by Water Year'))

    st.subheader("📊 Monthly Average Rainfall Plot")
    st.pyplot(create_plot(monthly_df['Month_Name'], monthly_df['Average_Monthly_Rainfall_mm'], 'Month', 'Average Monthly Rainfall (mm)', 'Average Monthly Rainfall'))

    st.subheader("📊 Max Daily Rainfall Plot")
    st.pyplot(create_plot(max_df['Water_Year'], max_df['Max_Daily_Rainfall_mm'], 'Water Year', 'Max Daily Rainfall (mm)', 'Maximum Daily Rainfall by Water Year'))

    st.subheader("⬇️ Download Full Excel Report with Charts")
    excel_bytes, excel_filename = export_to_excel(annual_df, monthly_df, max_df)
    st.download_button("Download Report", data=excel_bytes, file_name="Rainfall_Report.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
