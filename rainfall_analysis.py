import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import io
from datetime import datetime
from openpyxl import load_workbook
from openpyxl.drawing.image import Image as XLImage
import tempfile
import openai

# Constants
MONTH_ORDER = ['January', 'February', 'March', 'April', 'May', 'June',
               'July', 'August', 'September', 'October', 'November', 'December']
DEKAD_ORDER = ['I', 'II', 'III']
WATER_YEAR_MONTH_ORDER = [
    'June', 'July', 'August', 'September', 'October', 'November', 'December',
    'January', 'February', 'March', 'April', 'May']
DEKAD_MONTH_INDEX = {month: i for i, month in enumerate(WATER_YEAR_MONTH_ORDER)}
DEKAD_INDEX = {d: i for i, d in enumerate(DEKAD_ORDER)}

openai.api_key = st.secrets["OPENAI_API_KEY"]

def assign_water_year(df):
    df['Month'] = df['Date'].dt.month
    df['Year'] = df['Date'].dt.year
    df['Water_Year'] = df['Date'].apply(lambda x: f"{x.year}-{x.year+1}" if x.month >= 6 else f"{x.year-1}-{x.year}")
    return df

def assign_dekad(day):
    if day <= 10:
        return "I"
    elif day <= 20:
        return "II"
    else:
        return "III"

def calculate_monsoon_rainfall(df):
    monsoon_df = df[df['Date'].dt.month.isin([6, 7, 8, 9])]
    non_monsoon_df = df[~df['Date'].dt.month.isin([6, 7, 8, 9])]
    monsoon = monsoon_df.groupby('Water_Year')['Rainfall_mm'].sum().reset_index()
    monsoon.rename(columns={'Rainfall_mm': 'Monsoon_Rainfall_mm'}, inplace=True)
    non_monsoon = non_monsoon_df.groupby('Water_Year')['Rainfall_mm'].sum().reset_index()
    non_monsoon.rename(columns={'Rainfall_mm': 'Non_Monsoon_Rainfall_mm'}, inplace=True)
    merged = pd.merge(monsoon, non_monsoon, on='Water_Year', how='outer').fillna(0)
    return merged

def generate_analysis(df):
    df['Month_Name'] = df['Date'].dt.month_name()
    annual_rainfall = df.groupby('Water_Year')['Rainfall_mm'].sum().reset_index()
    annual_rainfall.rename(columns={'Rainfall_mm': 'Annual_Rainfall_mm'}, inplace=True)
    average_rainfall = annual_rainfall['Annual_Rainfall_mm'].mean()
    final_output = pd.concat([annual_rainfall, pd.DataFrame([{
        'Water_Year': 'Average',
        'Annual_Rainfall_mm': average_rainfall
    }])], ignore_index=True)

    monthly_totals = df.groupby(['Water_Year', 'Month_Name'])['Rainfall_mm'].sum().reset_index()
    monthly_avg = monthly_totals.groupby('Month_Name')['Rainfall_mm'].mean().reset_index()
    monthly_avg.rename(columns={'Rainfall_mm': 'Average_Monthly_Rainfall_mm'}, inplace=True)
    monthly_avg['Month_Num'] = monthly_avg['Month_Name'].apply(lambda x: MONTH_ORDER.index(x))
    monthly_avg = monthly_avg.sort_values('Month_Num').drop(columns='Month_Num')

    max_rainfall = df.loc[df.groupby('Water_Year')['Rainfall_mm'].idxmax()][['Water_Year', 'Rainfall_mm', 'Date']]
    max_rainfall.rename(columns={'Rainfall_mm': 'Max_Daily_Rainfall_mm', 'Date': 'Date_of_Occurrence'}, inplace=True)

    df['Day'] = df['Date'].dt.day
    df['Dekad'] = df['Day'].apply(assign_dekad)
    dekad_rainfall = df.groupby(['Water_Year', 'Month_Name', 'Dekad'])['Rainfall_mm'].sum().reset_index()
    dekad_rainfall.rename(columns={'Rainfall_mm': 'Ten_Daily_Rainfall_mm'}, inplace=True)
    dekad_rainfall['Month_Num'] = dekad_rainfall['Month_Name'].map(DEKAD_MONTH_INDEX)
    dekad_rainfall['Dekad_Num'] = dekad_rainfall['Dekad'].map(DEKAD_INDEX)
    dekad_rainfall = dekad_rainfall.sort_values(by=['Water_Year', 'Month_Num', 'Dekad_Num']).drop(columns=['Month_Num', 'Dekad_Num'])

    dekad_rainfall['Period'] = dekad_rainfall['Month_Name'] + ' ' + dekad_rainfall['Dekad']
    dekad_avg = dekad_rainfall.groupby('Period')['Ten_Daily_Rainfall_mm'].mean().reset_index()
    dekad_avg.rename(columns={'Ten_Daily_Rainfall_mm': 'Avg_Ten_Daily_Rainfall_mm'}, inplace=True)

    return final_output, monthly_avg, max_rainfall, dekad_avg, calculate_monsoon_rainfall(df), dekad_rainfall

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

def export_to_excel(annual_df, monthly_df, max_df, dekad_df, monsoon_df):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        with pd.ExcelWriter(tmp.name, engine='openpyxl') as writer:
            annual_df.to_excel(writer, sheet_name='Annual Rainfall', index=False)
            monthly_df.to_excel(writer, sheet_name='Monthly Averages', index=False)
            max_df.to_excel(writer, sheet_name='Max Daily Rainfall', index=False)
            dekad_df.to_excel(writer, sheet_name='10-Daily Averages', index=False)
            monsoon_df.to_excel(writer, sheet_name='Monsoon Rainfall', index=False)

        wb = load_workbook(tmp.name)

        plots = [
            ('Annual Rainfall', create_plot(annual_df['Water_Year'], annual_df['Annual_Rainfall_mm'], 'Water Year', 'Annual Rainfall (mm)', 'Annual Rainfall Variations by Water Year')),
            ('Monthly Averages', create_plot(monthly_df['Month_Name'], monthly_df['Average_Monthly_Rainfall_mm'], 'Month', 'Average Monthly Rainfall (mm)', 'Average Monthly Rainfall')),
            ('Max Daily Rainfall', create_plot(max_df['Water_Year'], max_df['Max_Daily_Rainfall_mm'], 'Water Year', 'Max Daily Rainfall (mm)', 'Maximum Daily Rainfall by Water Year')),
            ('10-Daily Averages', create_plot(dekad_df['Period'], dekad_df['Avg_Ten_Daily_Rainfall_mm'], 'Dekadal Period', 'Average Rainfall (mm)', 'Average Ten-Daily Rainfall')),
            ('Monsoon Rainfall', create_plot(monsoon_df['Water_Year'], monsoon_df['Monsoon_Rainfall_mm'], 'Water Year', 'Monsoon Rainfall (mm)', 'Monsoon Rainfall (June–September)'))
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

def generate_ai_insights(annual_df, monthly_df, max_df):
    annual_summary = annual_df.to_csv(index=False)
    monthly_summary = monthly_df.to_csv(index=False)
    max_rainfall_summary = max_df.to_csv(index=False)
    prompt = f"""
    Provide a concise analysis of rainfall trends based on the following datasets:

    Annual Rainfall Data:
    {annual_summary}

    Monthly Average Rainfall Data:
    {monthly_summary}

    Maximum Daily Rainfall Events:
    {max_rainfall_summary}

    Highlight anomalies, trends, and any insights useful for water resource planning.
    """
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "system", "content": "You are a hydrologist and climate analyst."},
                  {"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

# Streamlit UI
st.set_page_config(layout='wide')
st.title("Rainfall Data Analysis (Water Year based)")
uploaded_file = st.file_uploader("Upload CSV File", type=["csv"])

if uploaded_file:
    df = pd.read_csv(uploaded_file)
    df.columns = df.columns.str.strip()
    if 'Date' not in df.columns or 'Rainfall_mm' not in df.columns:
        st.error("CSV must contain 'Date' and 'Rainfall_mm' columns.")
        st.stop()

    df['Date'] = pd.to_datetime(df['Date'], format='%d/%m/%y', errors='coerce')
    df = df.dropna(subset=['Date'])
    df = assign_water_year(df)

    st.success("File processed successfully.")

    annual_df, monthly_df, max_df, dekad_df, monsoon_df, dekad_full = generate_analysis(df)

    st.subheader("📈 Annual Rainfall Table")
    st.dataframe(annual_df)

    st.subheader("📉 Monthly Average Rainfall Table")
    st.dataframe(monthly_df)

    st.subheader("🌧️ Maximum Daily Rainfall Table")
    st.dataframe(max_df)

    st.subheader("📅 10-Daily Rainfall Averages (Average across Years)")
    st.dataframe(dekad_df)

    st.subheader("📅 10-Daily Rainfall Values (All Years)")
    st.dataframe(dekad_full)

    st.subheader("🌦️ Monsoon Rainfall Summary (June–September)")
    st.markdown("*Note: Monsoon is considered from June to September.*")
    st.dataframe(monsoon_df)

    st.subheader("📊 Annual Rainfall Plot")
    st.pyplot(create_plot(annual_df['Water_Year'], annual_df['Annual_Rainfall_mm'], 'Water Year', 'Annual Rainfall (mm)', 'Annual Rainfall Variations by Water Year'))

    st.subheader("📊 Monthly Average Rainfall Plot")
    st.pyplot(create_plot(monthly_df['Month_Name'], monthly_df['Average_Monthly_Rainfall_mm'], 'Month', 'Average Monthly Rainfall (mm)', 'Average Monthly Rainfall'))

    st.subheader("📊 Max Daily Rainfall Plot")
    st.pyplot(create_plot(max_df['Water_Year'], max_df['Max_Daily_Rainfall_mm'], 'Water Year', 'Max Daily Rainfall (mm)', 'Maximum Daily Rainfall by Water Year'))

    st.subheader("📊 10-Daily Rainfall Plot")
    st.pyplot(create_plot(dekad_df['Period'], dekad_df['Avg_Ten_Daily_Rainfall_mm'], 'Dekadal Period', 'Average Rainfall (mm)', 'Average Ten-Daily Rainfall'))

    st.subheader("📊 Monsoon Rainfall Plot")
    st.pyplot(create_plot(monsoon_df['Water_Year'], monsoon_df['Monsoon_Rainfall_mm'], 'Water Year', 'Monsoon Rainfall (mm)', 'Monsoon Rainfall (June–September)'))

    st.subheader("🤖 AI-Assisted Rainfall Insights")
    if st.button("Generate AI Insights"):
        with st.spinner("Generating insights using ChatGPT..."):
            try:
                insights = generate_ai_insights(annual_df, monthly_df, max_df)
                st.success("AI insights generated successfully.")
                st.markdown(insights)
            except Exception as e:
                st.error("Failed to generate insights.")
                st.exception(e)

    st.subheader("⬇️ Download Full Excel Report with Charts")
    excel_bytes, excel_filename = export_to_excel(annual_df, monthly_df, max_df, dekad_df, monsoon_df)
    st.download_button("Download Report", data=excel_bytes, file_name="Rainfall_Report.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
