# main.py
import streamlit as st
import json
import pandas as pd
import os
import numpy as np
from model.DataBaseHandler import DataBaseHandler
from ui_components.config_editor import edit_config_page


def show_evaluation_status():
    if "eval_running" in st.session_state and st.session_state.eval_running is not None:
        if st.session_state.eval_running:
            st.sidebar.info("Evaluation Loop is Running")
        else:
            st.sidebar.warning("Evaluation Loop is Not Running")
    else:
        st.sidebar.warning("No evaluation loop has been started.")


def main():
    st.set_page_config(layout="wide")

    st.sidebar.title("Job Filter AI")
    page = st.sidebar.radio("Select Page", ["Job Filter", "Data Enrichment", "Edit Service Config"])

    # Display evaluation loop status on all pages.
    show_evaluation_status()

    if page == "Job Filter":
        # Call your job_filter module UI
        from ui_components.job_filter import filter_job_postings
        filter_job_postings()

    elif page == "Data Enrichment":
        from ui_components.enrichment import background_controller
        background_controller()

    elif page == "Edit Service Config":
        from ui_components.config_editor import edit_config_page
        edit_config_page()


if __name__ == '__main__':
    main()
