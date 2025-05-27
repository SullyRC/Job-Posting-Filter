# JobMatch AI – Automated Job Scraper & Evaluator
## Overview
JobMatch AI is an end-to-end job application tracking system powered by LLM-driven job evaluations, web scraping, and an interactive Streamlit dashboard.
This tool scrapes job postings, analyzes their relevance using AI, and provides an intuitive UI for job tracking.
## Features
🔹 Automated Job Scraper – Continuously scrapes job postings from various sources
🔹 AI-Powered Job Evaluation – Uses a custom LLM agent to assess job relevance
🔹 Streamlit Interactive Dashboard – View, filter, and track applications
🔹 Database Integration – Stores job postings and applied status in MySQL
🔹 Advanced Filtering – Supports list search, keyword matching, sliders, datetime selectors, and Boolean filters
🔹 Job Application Tracker – Mark jobs as applied and update statuses dynamically
🔹 Click-to-Apply Functionality – Open job postings directly from the UI

Repository Structure
📂 main – Orchestrates scraping and job evaluation logic
📂 config – Defines runtime behavior (which functions to run and their parameters)
📂 streamlit-dash – Streamlit dashboard for tracking job postings
Model Directory
📂 model/AgentInference – LLM inference functions for evaluating job descriptions
📂 model/Agent – Processes job data, populating agent_response in the database
📂 model/agent_config – Defines questions for the AI agent’s ask_questions() function
📂 model/DataBaseHandler – Database interaction module (MySQL data management)
📂 model/prompts – Contains structured prompts used by the AI agent
