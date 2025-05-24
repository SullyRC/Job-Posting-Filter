from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import time


# Common webscraper functions
class BaseScraper:

    def __init__(self):
        options = Options()
        # options.add_argument("--headless")  # Run without UI
        options.add_argument("--start-maximized")
        self.driver = webdriver.Chrome(service=Service(), options=options)

    def navigate(self, url):
        """Load the webpage."""
        self.driver.get(url)

    def navigate_landing_page(self, url):
        """Navigate and handle popups from our starting page."""
        self.navigate(url)
        time.sleep(2)
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
        try:
            exit_button = scraper.driver.find_element(
                By.XPATH, "//*[@id=\"base-contextual-sign-in-modal\"]/div/section/button")
            exit_button.click()
        except ElementNotInteractableException:
            print("Element was not found! Landing page might already be passd.")

    def extract_jobs(self):
        job_elements = self.driver.find_elements(By.CLASS_NAME, "job-search__results-list")
        return [job.text for job in job_elements]

url = 'https://www.linkedin.com/jobs/search/?currentJobId=4236125446&f_TPR=r86400&geoId=102264677&keywords=data%20scientist&origin=JOB_SEARCH_PAGE_LOCATION_AUTOCOMPLETE&refresh=true'
if __name__ == '__main__':
    scraper = LinkedInScraper()
    scraper.navigate_landing_page(url)

    job_list = scraper.extract_jobs()

    #scraper.close()
