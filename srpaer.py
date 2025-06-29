from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import time
import undetected_chromedriver as uc
import random
from urllib.parse import quote
import json
import datetime

def scrape_indeed_jobs(role="data scientist", location="India", max_jobs=10):
    """
    Scrape job descriptions from Indeed India with pagination
    """
    driver = None
    job_descriptions = []
    scraped = 0
    start = 0

    try:
        options = uc.ChromeOptions()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-plugins")
        options.add_argument("--disable-images")
        options.add_argument("--disable-javascript")
        options.add_argument("user-agent=Mozilla/5.0")

        print("🔧 Initializing Chrome driver...")
        driver = uc.Chrome(options=options, headless=False)
        driver.implicitly_wait(5)
        wait = WebDriverWait(driver, 15)

        encoded_role = quote(role)
        encoded_location = quote(location)

        while scraped < max_jobs:
            paginated_url = f"https://in.indeed.com/jobs?q={encoded_role}&l={encoded_location}&start={start}"
            print(f"\n🌐 Loading page: {paginated_url}")
            driver.get(paginated_url)
            time.sleep(random.uniform(3, 6))

            page_source = driver.page_source.lower()
            if "captcha" in page_source or "access denied" in page_source:
                print("⚠️ Captcha or access block detected. Stopping.")
                break

            job_card_selectors = [
                "a[data-jk]",
                "[data-jk]",
                ".job_seen_beacon",
                ".slider_container .slider_item",
                "[data-testid='job-title']",
                ".jobsearch-SerpJobCard"
            ]

            job_cards = []
            for selector in job_card_selectors:
                try:
                    print(f"🔍 Trying selector: {selector}")
                    job_cards = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, selector)))
                    if job_cards:
                        print(f"✅ Found {len(job_cards)} job cards.")
                        break
                except TimeoutException:
                    print(f"❌ No elements found with selector: {selector}")
                    continue

            if not job_cards:
                print("❌ No job cards found on this page. Ending.")
                break

            for job_card in job_cards:
                if scraped >= max_jobs:
                    break
                try:
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", job_card)
                    time.sleep(random.uniform(1, 2))
                    try:
                        job_card.click()
                    except:
                        driver.execute_script("arguments[0].click();", job_card)
                    time.sleep(random.uniform(2, 4))

                    description_selectors = [
                        "#vjs-desc",
                        "[data-testid='jobsearch-JobComponent-description']",
                        ".jobsearch-jobDescriptionText",
                        ".jobDescriptionText",
                        "#jobDescriptionText"
                    ]

                    job_desc = None
                    for desc_selector in description_selectors:
                        try:
                            job_desc_elem = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, desc_selector)))
                            job_desc = job_desc_elem.text.strip()
                            if job_desc:
                                break
                        except TimeoutException:
                            continue

                    if job_desc:
                        print(f"✅ Job {scraped+1}: {len(job_desc)} characters scraped")
                        job_descriptions.append(job_desc)
                        scraped += 1
                    else:
                        print(f"❌ Could not find job description for job {scraped+1}")
                except Exception as e:
                    print(f"⚠️ Error processing job {scraped+1}: {e}")
                    continue

            start += 10  # Move to next page

    except Exception as e:
        print(f"❌ Critical error: {e}")
    finally:
        if driver:
            try:
                print("🔄 Closing browser...")
                driver.quit()
                time.sleep(1)
            except Exception as e:
                print(f"⚠️ Error while closing browser: {e}")

    print(f"\n✅ Total jobs scraped: {len(job_descriptions)}")
    return job_descriptions


def save_descriptions_to_file(descriptions, filename="job_descriptions.txt"):
    try:
        with open(filename, "w", encoding="utf-8") as f:
            for i, desc in enumerate(descriptions, 1):
                f.write(f"{'='*50}\nJOB DESCRIPTION {i}\n{'='*50}\n")
                f.write(desc)
                f.write("\n\n")
        print(f"💾 Saved to text file: {filename}")
    except Exception as e:
        print(f"❌ Error saving text file: {e}")


def save_descriptions_to_json(descriptions, role, filename_prefix="job_descriptions"):
    filename = f"{filename_prefix}_{role.replace(' ', '_')}.json"
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump({"role": role, "descriptions": descriptions}, f, indent=2, ensure_ascii=False)
        print(f"💾 Saved to JSON file: {filename}")
    except Exception as e:
        print(f"❌ Error saving JSON file: {e}")


if __name__ == "__main__":
    print("🚀 Starting Indeed job scraper...")

    # Config
    role = "machine learning engineer"
    location = "India"
    max_jobs = 10  # You can increase this

    # Filter roles
    target_keywords = ["ml", "machine learning", "ai", "artificial intelligence", "deep learning"]
    if not any(keyword.lower() in role.lower() for keyword in target_keywords):
        print(f"❌ Role '{role}' is not in target keywords. Skipping.")
    else:
        descriptions = scrape_indeed_jobs(role, location, max_jobs)
        if descriptions:
            save_descriptions_to_file(descriptions)
            save_descriptions_to_json(descriptions, role)
            print(f"\n📊 Done! Scraped {len(descriptions)} jobs for role: {role}")
        else:
            print("⚠️ No descriptions scraped.")
