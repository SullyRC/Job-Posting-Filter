import streamlit as st
import json
import pandas as pd
from model.DataBaseHandler import DataBaseHandler
import os

# Load database authentication
db_auth = json.loads(os.environ.get('DataBaseAuth', '{}'))
db_handler = DataBaseHandler(db_auth)

# Streamlit UI
st.title("Job Postings Viewer")

# Sidebar Navigation
menu = st.sidebar.radio("Navigation", ["View Jobs", "View Unprocessed Jobs"])

# Function to load data


def load_data(view_type):
    if view_type == "View Jobs":
        return db_handler.fetch_all_jobs()
    elif view_type == "View Unprocessed Jobs":
        return db_handler.fetch_unprocessed_jobs()


# Load data
df = load_data(menu)

# 🔹 Multi-Column Filtering Section
st.subheader("Filter Job Postings")

# Allow users to select multiple columns to filter
selected_columns = st.multiselect("Select columns to filter by", df.columns)

# Create input fields for each selected column
query_values = {}
for column in selected_columns:
    query_values[column] = st.text_input(f"Enter keyword for '{column}'")

# Apply multiple filters dynamically
if any(query_values.values()):
    for column, value in query_values.items():
        if value:  # Apply filter only when input exists
            df = df[df[column].astype(str).str.contains(value, case=False, na=False)]

# JSON filitering
if "agent_response" in df.columns:
    json_query = st.text_input("Enter keyword for JSON field ('agent_response')")

    if json_query:
        def json_filter(json_str, query):
            try:
                if pd.isna(json_str) or not json_str.strip():  # Ensure valid JSON
                    return False
                data = json.loads(json_str)
                return any(query.lower() in str(value).lower() for value in data.values())
            except json.JSONDecodeError:
                return False  # Skip malformed JSON entries

        df = df[df["agent_response"].apply(lambda x: json_filter(str(x), json_query))]

# 🔹 Sort Table Option
# 🔹 Sort Table Option
if sort_by := st.selectbox("Sort by column", df.columns):
    sort_order = st.radio("Sort Order", ["Ascending", "Descending"])
    df = df.sort_values(by=sort_by, ascending=(sort_order == "Ascending"))

# 🔹 Refresh Data Button
if st.button("🔄 Refresh Data"):
    st.rerun()

# Display DataFrame
if df.empty:
    st.write("No matching records found.")
else:
    st.dataframe(df)
    st.download_button(
        label="⬇️ Download Data as CSV",
        data=df.to_csv(index=False),
        file_name="job_postings.csv",
        mime="text/csv"
    )
