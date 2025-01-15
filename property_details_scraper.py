import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException

class DataScraper:
    def __init__(self):
        # Set up headless Chromium options for Docker
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920x1080")
        
        # Set the Chromium binary location (as installed in Docker)
        chrome_options.binary_location = "/usr/bin/chromium"

        # Initialize the WebDriver with ChromiumDriver
        self.driver = webdriver.Chrome(service=Service("/usr/bin/chromedriver"), options=chrome_options)

    def close_driver(self):
        self.driver.quit()

    def scrape_central(self):
        # Open the webpage
        central_estates_rental_url = "https://www.central-estates.co.uk/search/2.html?n_override=0&showstc=on&showsold=on&instruction_type=Letting&minprice=&maxprice="
        self.driver.get(central_estates_rental_url)

        # Wait for dynamic content to load
        wait = WebDriverWait(self.driver, 10)
        rental_results = wait.until(EC.visibility_of_element_located((By.ID, "search-results")))

        extraction_fields = ["thumb-description-height", "beds-number", "bath-number"]

        all_results = {}

        for field in extraction_fields:
            results = rental_results.find_elements(By.CLASS_NAME, field)
            text_list = [result.text for result in results]
            all_results[field] = text_list
            
        body = all_results["thumb-description-height"]
        beds = all_results["beds-number"]
        baths = all_results["bath-number"]

        collated_data = list(zip(body, beds, baths))

        # Extract and print the text content of each element
        results = {count: list(result) for count, result in zip(range(len(collated_data)), collated_data)}

        # Initialise a dataframe dictionary to organise results
        df_dict = {"address": [], "cost": [], "description": [], "num_beds": [], "num_baths": []}

        # Add values from results to the DF dict
        for key, value in results.items():
            results[key][0] = results[key][0].split("\n") 

        # Append each value to the respective lists in df_dict
        for value in results.values():
            df_dict["address"].append(value[0][0].split(","))
            df_dict["cost"].append(value[0][1])
            df_dict["description"].append(value[0][2])
            df_dict["num_beds"].append(value[1])
            df_dict["num_baths"].append(value[2])

        return df_dict

    def scrape_stow_bros(self):
        stow_bros_rental_url = "https://www.stowbrothers.com/property-search/?orderby=price-asc&department=residential-lettings"
        self.driver.get(stow_bros_rental_url)

        results_list = []

        while True:
            try:
                # Wait for dynamic content to load
                wait = WebDriverWait(self.driver, 10)

                # Search for main content
                rental_results = wait.until(EC.visibility_of_element_located((By.ID, "content")))

                # Find elements containing data about specific houses
                results = rental_results.find_elements(By.CSS_SELECTOR, ".mt-4.cols-container.f-body")

                # Append data to overall list
                for result in results:
                    results_list.append(result.text.split("\n"))

                next_button = self.driver.find_element(By.CSS_SELECTOR, "a.next.page-numbers")

                # Perform click using JavaScript to avoid potential interception
                self.driver.execute_script("arguments[0].click();", next_button)

                # Wait for the new content to load before proceeding
                wait.until(EC.staleness_of(rental_results))
                wait.until(EC.visibility_of_element_located((By.ID, "content")))

            except (NoSuchElementException, TimeoutException):
                print("No more pages. Exiting pagination loop.")
                break

        df_dict = {"address": [], "price": [], "description": []}

        for item in results_list:
            df_dict["address"].append(item[0])
            df_dict["price"].append(item[1])
            if len(item) > 2:
                df_dict["description"].append(item[2])
            else:
                df_dict["description"].append(None)

        return df_dict

    def scrape_foxtons(self):
        urls = [
            "https://www.foxtons.co.uk/properties-to-rent/forest-gate-e7",
            "https://www.foxtons.co.uk/properties-to-rent/leyton-e10",
            "https://www.foxtons.co.uk/properties-to-rent/walthamstow-e17"
        ]

        property_list = []

        for url in urls:
            self.driver.get(url)
            wait = WebDriverWait(self.driver, 30)
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(3)
            rental_results = wait.until(EC.presence_of_all_elements_located((By.CLASS_NAME, "property_holder")))

            for result in rental_results:
                if result.is_displayed():
                    property_text = result.text.strip()
                    if not property_text:
                        property_text = self.driver.execute_script("return arguments[0].innerText;", result).strip()
                    if property_text:
                        property_list.append(property_text.split("\n"))
                    else:
                        print("Element found but no visible text.")
                else:
                    print("Element is not displayed.")

       # Filter outer list to contain only lists with property data
        filtered_properties_list = [item for item in property_list if not item[0].startswith("New properties") and len(item) == 4]

        # Specify a list of items to remove from zeroth inx of property data lists
        remove_items = ["Zero Deposit Scheme", "Recently let", "Recommended property", "Recently reduced in price"]

        # Remove erroneous elements from list.
        for item in filtered_properties_list:
            if item[0] in remove_items:
                item.pop(0)
            else:
                continue

        # Create a dictionary for loading data into dataframe and append relevant items from inner lists to appropriate keys.
        df_dict = {"address" : [], "cost_pcm" : [], "num_beds" : []}

        print(len([item for item in filtered_properties_list if len(item) > 3]))

        for item in filtered_properties_list:
            df_dict["address"].append(item[0])
            df_dict["cost_pcm"].append(item[1])
            df_dict["num_beds"].append(item[2])

        return df_dict

    def close_driver(self):
        self.driver.quit()

# Example usage:
if __name__ == "__main__":
    scraper = DataScraper()
    central_data = scraper.scrape_central()
    stow_bros_data = scraper.scrape_stow_bros()
    foxtons_data = scraper.scrape_foxtons()
    scraper.close_driver()

    print("Central Estates Data:", central_data)
    print("Stow Brothers Data:", stow_bros_data)
    print("Foxtons Data:", foxtons_data)
