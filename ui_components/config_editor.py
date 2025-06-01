import streamlit as st
import yaml

CONFIG_FILE = "config.yaml"
MAX_LANDING_PAGES = 10
# 🔹 Load and Save Functions


def load_config():
    """Load the YAML configuration from file."""
    with open(CONFIG_FILE, "r") as f:
        return yaml.safe_load(f)


def save_config(config):
    """Save the modified configuration back to file."""
    with open(CONFIG_FILE, "w") as f:
        yaml.dump(config, f, default_flow_style=False)


def update_landing_pages(scraper_name, new_pages):
    """Update LandingPages for a given scraper."""
    config = load_config()
    if scraper_name in config["scraper_config"]["classes"]:
        config["scraper_config"]["classes"][scraper_name]["LandingPages"] = new_pages
        save_config(config)
        return True
    return False


def add_scraper_class(scraper_name):
    """Add a new scraper class to the configuration."""
    config = load_config()
    if scraper_name not in config["scraper_config"]["classes"]:
        config["scraper_config"]["classes"][scraper_name] = {"LandingPages": []}
        save_config(config)
        return True
    return False

# 🔹 Streamlit UI for Editing Configuration


def edit_config_page():
    """Streamlit UI for modifying scraper configuration."""
    st.title("Scraper Configuration Editor")

    # Load config into session state
    if "config" not in st.session_state:
        st.session_state.config = load_config()

    # Select scraper
    scraper_classes = list(st.session_state.config["scraper_config"]["classes"].keys())
    selected_scraper = st.sidebar.selectbox("Select Scraper to Edit", scraper_classes)

    # Get current landing pages
    landing_pages = st.session_state.config["scraper_config"]["classes"][selected_scraper]["LandingPages"]

    st.subheader(f"Modify Landing Pages for {selected_scraper}")

    # Generate text inputs for existing landing pages + 1 extra field
    new_pages = []
    for i in range(len(landing_pages) + 1):  # One extra field
        url_input = st.text_input(
            f"Landing Page {i+1}", landing_pages[i] if i < len(landing_pages) else "")
        if url_input.strip():
            new_pages.append(url_input.strip())

    # Update landing pages
    if st.button("Update Landing Pages"):
        if update_landing_pages(selected_scraper, new_pages):
            st.success(f"✅ Updated Landing Pages for {selected_scraper}!")
        else:
            st.error("⚠️ Failed to update configuration.")

    # Save config to file
    if st.button("Save Config to File"):
        save_config(st.session_state.config)
        st.success("✅ Configuration saved successfully!")
