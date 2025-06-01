import streamlit as st
import json
import pandas as pd
import os
import numpy as np
from model.DataBaseHandler import DataBaseHandler

# File for saving queries
QUERY_FILE = "saved_queries.json"


def load_saved_queries():
    """Load existing queries from the file."""
    if os.path.exists(QUERY_FILE):
        with open(QUERY_FILE, "r") as file:
            return json.load(file)
    return {}


def save_query(query_name, active_filters):
    """Save query including filtering conditions and selected values."""
    saved_queries = load_saved_queries()
    saved_queries[query_name] = active_filters
    with open(QUERY_FILE, "w") as file:
        json.dump(saved_queries, file, indent=4)


def load_data(view_type, db_handler):
    """Load job data based on view selection."""
    loaded = db_handler.fetch_all_jobs()

    # Define priority columns and ordering
    ordering = [col for col in ['insert_timestamp', 'job_title', 'applied', 'posting_url', 'job_id']
                if col in loaded.columns]
    other_cols = [col for col in loaded.columns if col not in ordering]
    loaded = loaded[ordering + other_cols]

    # Convert columns to appropriate types
    if 'applied' in loaded.columns:
        loaded['applied'] = loaded['applied'].astype(bool)
    if 'id' in loaded.columns:
        loaded['id'] = loaded['id'].astype(str)

    # Ensure JSON column is parsed correctly
    loaded["agent_response"] = loaded["agent_response"].apply(
        lambda x: json.loads(x) if pd.notna(x) else {})

    if view_type == "View Jobs":
        json_expanded = loaded["agent_response"].apply(
            lambda data: {key: data[key]["response"] for key in data if "response" in data[key]})
    elif view_type == "Response Explanation":
        json_expanded = loaded["agent_response"].apply(
            lambda data: {key: data[key]["explanation"] for key in data if "explanation" in data[key]})
    else:
        return db_handler.fetch_unprocessed_jobs()

    json_expanded = json_expanded.apply(pd.Series)
    loaded = pd.concat([loaded.drop(columns=["agent_response"]), json_expanded], axis=1)

    loaded.columns = [col.replace('?', '').replace(' ', '_') if '?' in col else col
                      for col in loaded.columns]
    loaded.fillna('Missing Value', inplace=True)

    return loaded


def filter_contains(df, column, value=None):
    """Filter a column using 'Contains' logic."""
    if not value:
        value = st.sidebar.text_input(f"Enter keyword for '{column}'")
    if value:
        condition = df[column].str.contains(value, case=False, na=False)
        return condition, {'func': 'filter_contains', 'value': value}
    return None, None


def filter_list_search(df, column, selected_values=None):
    """Filter a column using list selection."""
    if not selected_values:
        column_values = df[column].value_counts()
        selected_values = st.sidebar.multiselect(
            f"Select values for '{column}'", options=column_values.index.tolist())
    if selected_values:
        condition = df[column].isin(selected_values)
        return condition, {'func': 'filter_list_search', 'value': selected_values}
    return None, None


def filter_slider(df, column, selected_values=None):
    """Filter numerical columns using a slider."""
    if selected_values:
        start_value, end_value = selected_values[0], selected_values[1]
    else:
        min_value, max_value = df[column].min(), df[column].max()
        start_value, end_value = st.sidebar.slider(
            f"Select range for '{column}'", min_value=min_value, max_value=max_value,
            value=(min_value, max_value))
    condition = (df[column] >= start_value) & (df[column] <= end_value)
    return condition, {'func': 'filter_slider', 'value': [start_value, end_value]}


def filter_datetime_slider(df, column, selected_values=None):
    """Filter datetime columns using date inputs."""
    df[column] = pd.to_datetime(df[column])
    min_date, max_date = df[column].min(), df[column].max()
    start_date = st.sidebar.date_input(
        "Start Date", min_value=min_date, max_value=max_date, value=min_date)
    end_date = st.sidebar.date_input(
        "End Date", min_value=min_date, max_value=max_date, value=max_date) + pd.Timedelta(1, unit='D')
    condition = (df[column].dt.date >= start_date) & (df[column].dt.date <= end_date)
    return condition, {'func': 'filter_datetime_slider', 'value': None}


def filter_boolean(df, column, bool_choice=None):
    """Filter Boolean columns using radio buttons."""
    if bool_choice is None:
        bool_choice = st.sidebar.radio(f"Filter '{column}'", ["All", True, False])
    if bool_choice != "All":
        condition = df[column] == bool_choice
        return condition, {'func': 'filter_boolean', 'value': bool_choice}
    return None, None


def filter_job_postings(db_handler: DataBaseHandler = None):
    """Streamlit function to filter and view job postings."""
    # If no DB handler is provided, create one using environment authentication
    if db_handler is None:
        db_auth = json.loads(os.environ.get('DataBaseAuth', '{}'))
        db_handler = DataBaseHandler(db_auth)

    st.title("Job Postings Viewer")

    # Sidebar Navigation
    menu = st.sidebar.radio(
        "Navigation", ["View Jobs", "Response Explanation", "View Unprocessed Jobs"])

    # Load job data based on the view
    df = load_data(menu, db_handler)

    # Query Management
    st.sidebar.subheader("Query Management")
    saved_queries = load_saved_queries()
    selected_query = st.sidebar.selectbox("Load Saved Query", ["None"] + list(saved_queries.keys()))

    if selected_query != "None":
        active_filters = saved_queries.get(selected_query, {})
    else:
        active_filters = {}

    # Filtering Options in Sidebar
    st.sidebar.subheader("Filter Job Postings")
    selected_columns = st.sidebar.multiselect("Select columns to filter by", df.columns.tolist())

    # If a saved query is loaded, add its keys to the selected columns list.
    if selected_query != "None":
        selected_columns = list(set(selected_columns + list(active_filters.keys())))

    query_conditions = []
    for column in selected_columns:
        st.sidebar.subheader(f"Filter {column}")
        saved_col = active_filters.get(column)
        condition = None

        if saved_col:
            use_save_data = st.sidebar.radio(f"Use saved filter for {column}?", [
                                             True, False], key=column)
        else:
            use_save_data = False

        if saved_col and use_save_data:
            # Evaluate the stored filtering function: note that eval() is used here,
            # so ensure that your saved metadata is trusted.
            condition, saved_data = eval(saved_col['func'])(df, column, saved_col['value'])
        elif pd.api.types.is_string_dtype(df[column]) or pd.api.types.is_object_dtype(df[column]):
            filter_type = st.sidebar.radio(f"Filter type for '{column}'", [
                                           "List Search", "Contains"], key=column)
            if filter_type == "Contains":
                condition, saved_data = filter_contains(df, column)
            else:
                condition, saved_data = filter_list_search(df, column)
        elif pd.api.types.is_bool_dtype(df[column]):
            condition, saved_data = filter_boolean(df, column)
        elif pd.api.types.is_numeric_dtype(df[column]):
            condition, saved_data = filter_slider(df, column)
        elif pd.api.types.is_datetime64_any_dtype(df[column]):
            condition, saved_data = filter_datetime_slider(df, column)
        else:
            raise TypeError(f"Cannot filter column '{column}' for type {df[column].dtype}")

        if condition is not None:
            query_conditions.append(condition)
            active_filters[column] = saved_data

    # Apply all filters to the DataFrame.
    if query_conditions:
        df_filtered = df[np.logical_and.reduce(query_conditions)]
    else:
        df_filtered = df

    # Allow users to save the current query.
    if st.sidebar.button("Save Query"):
        query_name = st.sidebar.text_input("Query Name")
        if query_name:
            save_query(query_name, active_filters)
            st.sidebar.success(f"Query '{query_name}' saved!")

    # Also provide an extra save button if needed.
    query_name_2 = st.sidebar.text_input("Enter query name to save", key="save_query_2")
    if st.sidebar.button("💾 Save Query", key="save_query_button"):
        if query_name_2:
            save_query(query_name_2, active_filters)
            st.sidebar.success(f"Query '{query_name_2}' saved!")

    # Sort Option
    sort_by = st.sidebar.selectbox("Sort by column", df.columns.tolist())
    if sort_by:
        sort_order = st.sidebar.radio("Sort Order", ["Descending", "Ascending"])
        df_filtered = df_filtered.sort_values(by=sort_by, ascending=(sort_order == "Ascending"))

    # Refresh Data
    if st.button("🔄 Refresh Data"):
        st.rerun()

    # Display DataFrame
    if df.empty:
        st.write("No matching records found.")
    else:
        st.subheader(f"Number of jobs with criteria: {df_filtered.shape[0]}")
        edited_df = st.data_editor(
            df_filtered,
            height=600,
            use_container_width=True,
            num_rows="dynamic",
            column_config={
                'posting_url': st.column_config.LinkColumn(),
                'applied': st.column_config.CheckboxColumn('Applied')
            },
            hide_index=True
        )
        if st.button("✅ Apply Changes"):
            applied_updates = [(row["id"], row["applied"]) for idx, row in edited_df.iterrows()]
            db_handler.update_applied_status(applied_updates)
            df.update(edited_df)
            st.success("Applied status updated successfully!")
        st.download_button(
            label="⬇️ Download Data as CSV",
            data=edited_df.to_csv(index=False),
            file_name="job_postings.csv",
            mime="text/csv"
        )


if __name__ == "__main__":
    # This allows you to run this module directly as a Streamlit app.
    filter_job_postings()
