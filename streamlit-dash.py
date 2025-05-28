import streamlit as st
import json
import pandas as pd
from model.DataBaseHandler import DataBaseHandler
import os
import datetime
import numpy as np

# Load database authentication
db_auth = json.loads(os.environ.get('DataBaseAuth', '{}'))
db_handler = DataBaseHandler(db_auth)

# Set streamlit config
st.set_page_config(layout="wide")

# Streamlit UI
st.title("Job Postings Viewer")

# Sidebar Navigation
menu = st.sidebar.radio(
    "Navigation", ["View Jobs", "Response Explanation", "View Unprocessed Jobs"])

# Function to load data


def load_data(view_type):
    if view_type == "View Jobs":
        # Load the data
        loaded = db_handler.fetch_all_jobs()

        # Priority columns
        ordering = [col for col in ['insert_timestamp', 'job_title', 'applied', 'posting_url']
                    if col in loaded.columns]

        # shift ordering of columns in the dataframe
        other_cols = [col for col in loaded.columns if col not in ordering]

        loaded = loaded[ordering + other_cols]

        if 'applied' in loaded.columns:
            loaded['applied'] = loaded['applied'].astype(bool)

        if 'id' in loaded.columns:
            loaded['id'] = loaded['id'].astype(str)

        # Ensure JSON column is parsed correctly
        loaded["agent_response"] = loaded["agent_response"].apply(lambda x: json.loads(x)
                                                                  if pd.notna(x) else {})

        # Extract only "response" values from each question
        json_expanded = loaded["agent_response"].apply(lambda data:
                                                       {key: data[key]["response"] for key in data
                                                        if "response" in data[key]})

        # Convert extracted responses into DataFrame columns
        json_expanded = json_expanded.apply(pd.Series)

        # Merge expanded JSON columns back into the main DataFrame
        loaded = pd.concat([loaded.drop(columns=["agent_response"]), json_expanded], axis=1)

        loaded.drop(columns=['posting_id', 'description'], inplace=True)

        return loaded

    if view_type == "Response Explanation":
        # Load the data
        loaded = db_handler.fetch_all_jobs()

        # Priority columns
        ordering = [col for col in ['insert_timestamp', 'job_title', 'applied', 'posting_url',
                                    'job_id'] if col in loaded.columns]

        # shift ordering of columns in the dataframe
        other_cols = [col for col in loaded.columns if col not in ordering]

        loaded = loaded[ordering + other_cols]

        if 'applied' in loaded.columns:
            loaded['applied'] = loaded['applied'].astype(bool)

        if 'id' in loaded.columns:
            loaded['id'] = loaded['id'].astype(str)

        # Ensure JSON column is parsed correctly
        loaded["agent_response"] = loaded["agent_response"].apply(lambda x: json.loads(x)
                                                                  if pd.notna(x) else {})

        json_expanded = loaded["agent_response"].apply(lambda data:
                                                       {key: data[key]["explanation"] for key in data
                                                        if "explanation" in data[key]})

        # Convert extracted responses into DataFrame columns
        json_expanded = json_expanded.apply(pd.Series)

        # Merge expanded JSON columns back into the main DataFrame
        loaded = pd.concat([loaded.drop(columns=["agent_response"]), json_expanded], axis=1)

        return loaded

    elif view_type == "View Unprocessed Jobs":
        return db_handler.fetch_unprocessed_jobs()


def filter_contains(df, column):
    """Filters column based on user input using 'Contains' logic."""
    value = st.sidebar.text_input(f"Enter keyword for '{column}'")
    if value:
        return f"`{column}`.str.contains('{value}', case=False, na=False)"
    return None


def filter_list_search(df, column):
    """Filters column using a selectable list of values sorted by frequency."""
    column_values = df[column].dropna().value_counts()

    formatted_options = [f"{value} ({count})" for value, count in column_values.items()]
    selected_values = st.sidebar.multiselect(f"Select values for '{column}' (Occurrences)",
                                             options=formatted_options)
    clean_selected_values = [item.split(" (")[0] for item in selected_values]

    if clean_selected_values:
        return f"`{column}` in {clean_selected_values}"
    return None


def filter_slider(df, column):
    """Filters numerical columns using a range slider."""
    min_value, max_value = df[column].min(), df[column].max()
    start_value, end_value = st.sidebar.slider(f"Select range for '{column}'", min_value=min_value,
                                               max_value=max_value, value=(min_value, max_value))

    return f"`{column}` >= @start_value & `{column}` <= @end_value"


def filter_datetime_slider(df, column):
    """Filters datetime columns using a date range slider."""
    df[column] = pd.to_datetime(df[column])  # Ensure datetime format

    min_date, max_date = df[column].min(), df[column].max()

    start_date = st.sidebar.date_input(
        "Start Date", min_value=min_date, max_value=max_date, value=min_date)
    end_date = st.sidebar.date_input("End Date", min_value=min_date,
                                     max_value=max_date, value=max_date) + pd.Timedelta(1, unit='D')

    return start_date, end_date, f"`{column}` >= @start_date & `{column}` <= @end_date"


def filter_boolean(df, column):
    """Filters Boolean columns using a radio button."""
    bool_choice = st.sidebar.radio(f"Filter '{column}'", ["All", "True", "False"])
    if bool_choice == "True":
        return f"`{column}` == True"
    elif bool_choice == "False":
        return f"`{column}` == False"
    return None


# Load data
df = load_data(menu)

# 🔹 Multi-Column Filtering Section
st.sidebar.subheader("Filter Job Postings")

# Allow users to select multiple columns to filter
squery_conditions = []
selected_columns = st.sidebar.multiselect("Select columns to filter by", df.columns)
query_conditions = []
for column in selected_columns:
    col_dtype = df[column].dtype

    st.sidebar.subheader(f"Filter {column}")

    if col_dtype == "object" or pd.api.types.is_string_dtype(df[column]):
        filter_type = st.sidebar.radio(f"Filter type for '{column}'", [
                                       "List Search", "Contains"], key=column)
        query = filter_contains(
            df, column) if filter_type == "Contains" else filter_list_search(df, column)

    elif pd.api.types.is_bool_dtype(df[column]) or col_dtype == np.bool:
        query = filter_boolean(df, column)

    elif pd.api.types.is_numeric_dtype(df[column]):
        query = filter_slider(df, column)

    elif pd.api.types.is_datetime64_any_dtype(df[column]):
        start_date, end_date, query = filter_datetime_slider(df, column)
        # locals()["start_date"] = start_date
        # locals()["end_date"] = end_date

    else:
        raise TypeError(f"Cannot filter column '{column}' for type {col_dtype}")

    if query:
        query_conditions.append(query)

# 🔹 Apply filtering using df.query()
if query_conditions:
    query_string = " & ".join(query_conditions)
    df = df.query(query_string)


# Apply filtering using df.query()
if query_conditions:
    query_string = " & ".join(query_conditions)
    df = df.query(query_string)

# 🔹 Sort Table Option
if sort_by := st.sidebar.selectbox("Sort by column", df.columns):
    sort_order = st.sidebar.radio("Sort Order", ["Descending", "Ascending"])
    df = df.sort_values(by=sort_by, ascending=(sort_order == "Ascending"))

# 🔹 Refresh Data Button
if st.button("🔄 Refresh Data"):
    st.rerun()

# Display DataFrame
if df.empty:
    st.write("No matching records found.")
else:
    edited_df = st.data_editor(df, height=600, use_container_width=True, num_rows='dynamic',
                               column_config={
                                   'posting_url': st.column_config.LinkColumn(),
                                   'applied': st.column_config.CheckboxColumn('Applied')},
                               hide_index=True)

    if st.button("✅ Apply Changes"):
        applied_updates = [(row["id"], row["applied"]) for idx, row in edited_df.iterrows()]

        # 🔹 Update database with applied status
        db_handler.update_applied_status(applied_updates)

        # 🔹 Sync changes to dataframe in memory
        df.update(edited_df)

        st.success("Applied status updated successfully!")

    st.download_button(
        label="⬇️ Download Data as CSV",
        data=edited_df.to_csv(index=False),
        file_name="job_postings.csv",
        mime="text/csv"
    )
