from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, ElementNotInteractableException, \
    ElementClickInterceptedException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from model.DataBaseHandler import DataBaseHandler
import re
import time
import pandas as pd
import yaml
import os
import json
# import threading


# Common webscraper functions
class BaseScraper:

    def __init__(self, db_handler: DataBaseHandler, config: dict):
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--start-maximized")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument(" --no-sandbox")

        # Since we are running chrome on multiple threads, we need to have a unique dir for each id
        # thread_id = threading.get_ident()
        # options.add_argument(f"--user-data-dir=chrome-user-data-{thread_id}")

        # Set our binary location from our docker container, temporarily create own
        # options.binary_location = "google-chrome"

        # Get our service (temporarily create own)
        # service = Service("chromedriver/chromedriver")
        service = Service()

        self.driver = webdriver.Chrome(service=service, options=options)
        self.db_handler = db_handler

        self.config = config

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

    def extract_jobs_list(self):
        """Abstract method for extracting job list"""
        return NotImplementedError()

    def extract_job_information(self):
        return NotImplementedError()

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
        Parse all landing pages for a scraper class in the config
        """
        job_set = []

        for landing_page in self.config['LandingPages']:
            job_set.extend(self.extract_all_for_search(landing_page))

            # Insert into our database
            self.db_handler.insert_jobs(job_set)

        df = pd.DataFrame(job_set)
        return df

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
            job_list = self.driver.find_elements(By.CLASS_NAME, "two-pane-serp-page__results-list")

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
                         if "jobs/view" in job
                         and job not in current_job_links['posting_url']
                         ]

            # Also check if any of the job ids are present. If so skip them
            for job_id in current_job_links['posting_id'].dropna():
                for job in job_links:
                    if type(job) is str and job_id in job:
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
        try:
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
        except Exception as e:
            posting_information = {'posting_url': url,
                                   'posting_id': None,
                                   'job_title': None,
                                   'description': None,
                                   'experience': None,
                                   'employment_type': None,
                                   'industries': None
                                   }

        return posting_information


class DiceScraper(BaseScraper):

    def handle_landing_popups(self):
        """
        Method for navigating to the search page and handling popups
        """
        try:
            self.driver.find_element(By.XPATH,
                                     "//button[@data-testid='recommended-jobs-banner-close-btn']"
                                     ).click()

        # This can happen if we have already closed it before
        except NoSuchElementException as e:
            pass

        except ElementClickInterceptedException as e:
            print("Dismissal intercepted: {}.\nContinuing to scrape.".format(e.__class__))

    def extract_jobs_list(self):
        """Method for getting the list of hrefs from the job list"""
        # Loop until we have reached every page
        current_job_links = self.db_handler.fetch_recent_jobs()

        if type(current_job_links) is None or current_job_links.shape[0] == 0:
            current_job_links = pd.DataFrame(data={"posting_url": []})

        new_links = []

        try:
            while True:
                time.sleep(2)
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                job_list = self.driver.find_element(By.XPATH,
                                                    "//div[@data-testid='job-search-results-container']"
                                                    )

                # Extract the inner html
                job_html = job_list.get_attribute("innerHTML")

                # Regex search for the hrefs
                href_pattern = r'href=["\'](.*?)["\']'
                job_links = re.findall(href_pattern, job_html)

                # Add the new links
                new_links.extend([job for job in job_links
                                 if job not in current_job_links['posting_url']
                                 and 'job-detail' in job
                                  ])

                # Check to see if we have more pages
                svg_element = self.driver.find_element(By.XPATH, "//span[@aria-label='Next']")
                if svg_element.get_attribute('aria-disabled'):
                    break
                else:
                    self.handle_landing_popups()
                    self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth'"
                                               ", block: 'center'});", svg_element)
                    svg_element.click()

        except Exception as e:
            print("Could not continue to search for jobs due to error {}".format(e.__class__))

        finally:
            # Get the unique links
            new_links = list(set(new_links))
            return new_links

    def extract_job_information(self, url):
        # Get the url and id
        posting_information = {'posting_url': url,
                               'posting_id': url.split('job-detail/')[1],
                               'job_title': None,
                               'description': None,
                               'experience': 'Dice: not available',
                               'employment_type': 'Dice: not available',
                               'industries': 'Dice: not available'}

        try:
            self.navigate(url)

            # Get the title
            title = self.driver.find_element(By.TAG_NAME, 'h1')
            posting_information['job_title'] = title.text

            # Get the description
            description = self.driver.find_element(By.ID, "jobDescription")
            posting_information['description'] = description.text

        except Exception as e:
            print("Could not properly parse url {} due to error: {}".format(url, e))

        finally:
            return posting_information


if __name__ == '__main__':
    from main import load_config
    config = load_config('../config.yaml')['scraper_config']['classes']['LinkedInScraper']
    scraper = LinkedInScraper(
        DataBaseHandler(json.loads(
            os.environ['DataBaseAuth'])),
        config=config
    )
    scraper.extract_all_for_search(config['LandingPages'][0])
    data = scraper.parse_all_searches()
    scraper.close()
