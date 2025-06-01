# main.py
import streamlit as st
import json
import pandas as pd
import os
import numpy as np
from model.DataBaseHandler import DataBaseHandler
from ui_components.job_filter import filter_job_postings


def show_evaluation_status():
    if "eval_process" in st.session_state and st.session_state.eval_process is not None:
        if st.session_state.eval_process.is_alive():
            st.sidebar.info("Evaluation Loop is Running")
        else:
            st.sidebar.warning("Evaluation Loop is Not Running")
    else:
        st.sidebar.warning("No evaluation loop has been started.")


def main():
    st.set_page_config(layout="wide")

    st.sidebar.title("Job Filter AI")
    page = st.sidebar.radio("Select Page", ["Job Filter", "Data Enrichment"])

    # Display evaluation loop status on all pages.
    show_evaluation_status()

    if page == "Job Filter":
        # Call your job_filter module UI
        from ui_components.job_filter import filter_job_postings
        filter_job_postings()

    elif page == "Data Enrichment":
        st.title("Loading Agent")
        st.subheader("This can take up to 5 minutes")
        from ui_components.enrichment import background_controller
        background_controller()


if __name__ == '__main__':
    main()
