from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, ElementNotInteractableException
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from model.DataBaseHandler import DataBaseHandler
import re
import time
import pandas as pd
import yaml
import os
import json


# Common webscraper functions
class BaseScraper:

    def __init__(self, db_handler: DataBaseHandler, config: dict):
        options = Options()
        # options.add_argument("--headless")  # Run without UI
        options.add_argument("--start-maximized")
        self.driver = webdriver.Chrome(service=Service(), options=options)
        self.db_handler = db_handler

        self.config = config['scraper_config']

    def navigate(self, url):
        """Load the webpage."""
        self.driver.get(url)
        self.url = url
        time.sleep(3)

    def navigate_landing_page(self, url):
        """Navigate and handle popups from our starting page."""
        self.navigate(url)
        self.handle_landing_popups()

    def handle_landing_popups(self):
        """Abstract method for handling landing popups."""
        return NotImplementedError()

    def close(self):
        """Close the browser."""
        self.driver.quit()


class LinkedInScraper(BaseScraper):

    def handle_landing_popups(self):
        """
        Method for navigating to the search page and handling popups
        """

        # Add extra time to sleep until objects are loaded
        time.sleep(3)

        try:
            # Get our sign in and check if we need to return
            sign_in = self.driver.find_element(By.ID, "base-contextual-sign-in-modal")

        except NoSuchElementException:
            # If we have not found this element, then we the sign in is not present
            return

        if len(sign_in.text) == 0:
            # We have passed the sign-in
            return

        # Find our button to exit out of here
        button = sign_in.find_element(By.XPATH,
                                      "//*[@data-tracking-control-name="
                                      "'public_jobs_contextual-sign-in-modal_modal_dismiss']")

        try:
            button.click()
        except ElementNotInteractableException:
            print("Could not close popup. Continuing either way.")

        return

    def extract_jobs_list(self):
        """
        Method for getting the list of hrefs from the job list
        """
        try:
            # Scroll to the bottom of the page
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

            # Sleep until we have the load more jobs load
            time.sleep(5)

            # Get the list
            job_list = self.driver.find_elements(By.CLASS_NAME, "jobs-search__results-list")

            # Extract the inner html
            job_html = job_list[0].get_attribute("innerHTML")

            # Regex search for the hrefs
            href_pattern = r'href=["\'](.*?)["\']'
            job_links = re.findall(href_pattern, job_html)

            # Don't insert jobs that are in database
            current_job_links = self.db_handler.fetch_recent_jobs()

            if type(current_job_links) is None or current_job_links.shape[0] == 0:
                current_job_links = pd.DataFrame(data={"posting_url": [],
                                                       "posting_id": []})

            # We need to remove any job links with https://www.linkedin.com/company/
            job_links = [job for job in job_links
                         if "linkedin.com/company/" not in job
                         and job not in current_job_links['posting_url']
                         ]

            # Also check if any of the job ids are present. If so skip them
            for job_id in current_job_links['posting_id']:
                for job in job_links:
                    if job_id in job:
                        job_links.remove(job)

            return job_links

        except Exception as e:
            print("Unable to properly fetch job list due to error {}.".format(e),
                  "\nReturning empty list.")
            return []

    def extract_job_information(self, url):
        """
        Navigate and extract relevant information out of the job posting
        """
        self.navigate(url)

        posting_information = {'posting_url': url}

        # Get the job id
        pattern = r"-([\d]+)\?"
        posting_information['posting_id'] = re.search(pattern, url).group(1)

        # Get the title
        title = self.driver.find_element(By.TAG_NAME, 'h1')

        # This will occur if we've hit an auth issue
        if title.text == 'Join LinkedIn':
            posting_information.update(
                {'job_title': None,
                 'description': None,
                 'experience': None,
                 'employment_type': None,
                 'industries': None
                 })
            return posting_information
        posting_information['job_title'] = title.text

        # Get the description of the posting
        posting_description = self.driver.find_element(By.CLASS_NAME,
                                                       "decorated-job-posting__details")
        posting_information['description'] = posting_description.text

        # Get the job tags
        tags = self.driver.find_element(By.CLASS_NAME,
                                        "description__job-criteria-list")

        # Need to do some handling on these tags to extract information
        tags = tags.text
        experience = re.search("Seniority level\n(.*?)\nEmployment",
                               tags, re.DOTALL)
        posting_information['experience'] = experience.group(1) if experience else None
        employment_type = re.search("Employment type\n(.*?)\nJob function",
                                    tags, re.DOTALL)
        posting_information['employment_type'] = employment_type.group(1) if employment_type \
            else None
        industries = re.search("Industries\n(.*?)",
                               tags, re.DOTALL)
        posting_information['industries'] = industries.group(1) if industries else None
        return posting_information

    def extract_all_for_search(self, landing_url):
        """
        Load and parse information from all jobs listed
        """
        self.navigate_landing_page(landing_url)

        # Get our job links
        links = self.extract_jobs_list()

        # Get our information
        job_set = [self.extract_job_information(job) for job in links]

        return job_set

    def parse_all_searches(self):
        """
        Parse all landing pages for linkedin in the config
        """
        job_set = []

        for landing_page in self.config['LinkedInScraper']['LandingPages']:
            job_set.extend(self.extract_all_for_search(landing_page))

            # Insert into our database
            self.db_handler.insert_jobs(job_set)

        df = pd.DataFrame(job_set)
        return df


if __name__ == '__main__':
    scraper = LinkedInScraper(
        DataBaseHandler(json.loads(
            os.environ['DataBaseAuth']))
    )

    df = scraper.parse_all_searches()
    scraper.close()
