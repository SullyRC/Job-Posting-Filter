import streamlit as st
import yaml
import importlib
import inspect

from model import scraper  # Assumes scraper classes are defined in model/scraper.py

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
    """Update LandingPages for a given scraper, with a limit of MAX_LANDING_PAGES."""
    config = load_config()
    if scraper_name in config["scraper_config"]["classes"]:
        # Limit the number of landing pages to MAX_LANDING_PAGES
        config["scraper_config"]["classes"][scraper_name]["LandingPages"] = new_pages[:MAX_LANDING_PAGES]
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


def remove_scraper_class(scraper_name):
    """Remove a scraper class from the configuration."""
    config = load_config()
    if scraper_name in config["scraper_config"]["classes"]:
        del config["scraper_config"]["classes"][scraper_name]
        save_config(config)
        return True
    return False


def get_available_scraper_classes():
    """
    Dynamically fetch scraper classes from model/scraper.py.
    This function returns the names of classes defined in the scraper module.
    """
    scraper_classes = []
    for name, obj in inspect.getmembers(scraper, inspect.isclass):
        if obj.__module__ == scraper.__name__:
            scraper_classes.append(name)
    return scraper_classes


# 🔹 Streamlit UI for Editing Configuration

def edit_config_page():
    """Streamlit UI for modifying scraper configuration."""
    st.title("Scraper Configuration Editor")

    # Load config into session state
    if "config" not in st.session_state:
        st.session_state.config = load_config()

    st.sidebar.header("Manage Scraper Types")

    # Section to add new scraper types
    available_scrapers = get_available_scraper_classes()
    current_scrapers = list(st.session_state.config["scraper_config"]["classes"].keys())
    # Filter out currently added scraper types
    new_scrapers = [
        scraper_class for scraper_class in available_scrapers if scraper_class not in current_scrapers]

    st.sidebar.subheader("Add New Scraper")
    if new_scrapers:
        new_scraper_choice = st.sidebar.selectbox(
            "Select Scraper to Add", ["Select Scraper"] + new_scrapers, key="add_scraper")
        if new_scraper_choice != "Select Scraper":
            if st.sidebar.button("Add Scraper"):
                if add_scraper_class(new_scraper_choice):
                    st.sidebar.success(f"Added {new_scraper_choice} to configuration!")
                    # Update session state config after adding
                    st.session_state.config = load_config()
                else:
                    st.sidebar.error("Failed to add scraper.")
    else:
        st.sidebar.info("No new scraper types available.")

    # Section to remove existing scraper types
    st.sidebar.subheader("Remove Scraper")
    if current_scrapers:
        remove_scraper_choice = st.sidebar.selectbox(
            "Select Scraper to Remove", ["Select Scraper"] + current_scrapers, key="remove_scraper")
        if remove_scraper_choice != "Select Scraper":
            if st.sidebar.button("Remove Scraper"):
                if remove_scraper_class(remove_scraper_choice):
                    st.sidebar.success(f"Removed {remove_scraper_choice} from configuration!")
                    # Update session state config after removal
                    st.session_state.config = load_config()
                else:
                    st.sidebar.error("Failed to remove scraper.")
    else:
        st.sidebar.info("No scraper types to remove.")

    # Main section: Select an existing scraper to edit its landing pages.
    st.subheader("Edit Existing Scraper Landing Pages")
    scraper_classes = list(st.session_state.config["scraper_config"]["classes"].keys())
    if scraper_classes:
        selected_scraper = st.sidebar.selectbox(
            "Select Scraper to Edit", scraper_classes, key="edit_scraper")

        # Get current landing pages
        landing_pages = st.session_state.config["scraper_config"]["classes"][selected_scraper]["LandingPages"]

        st.subheader(f"Modify Landing Pages for {selected_scraper}")
        new_pages = []
        # Show up to MAX_LANDING_PAGES text input fields with existing values pre-filled
        for i in range(MAX_LANDING_PAGES):
            default_text = landing_pages[i] if i < len(landing_pages) else ""
            url_input = st.text_input(
                f"Landing Page {i+1}", default_text, key=f"{selected_scraper}_page_{i}")
            if url_input.strip():
                new_pages.append(url_input.strip())

        # Button to update landing pages in the config file
        if st.button("Update Landing Pages", key="update_pages"):
            if update_landing_pages(selected_scraper, new_pages):
                st.success(f"✅ Updated Landing Pages for {selected_scraper}!")
                # Update session state with new configuration
                st.session_state.config = load_config()
            else:
                st.error("⚠️ Failed to update configuration.")

        # Button to save the full session state config to file (optional)
        if st.button("Save Config to File", key="save_config"):
            save_config(st.session_state.config)
            st.success("✅ Configuration saved successfully!")
    else:
        st.info("No scraper types available in configuration.")


# Run the Streamlit app page
if __name__ == "__main__":
    edit_config_page()
