from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
import time, random
def start_whatsapp():
    options = Options()

    options.add_argument("--remote-allow-origins=*")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--start-maximized")

    options.add_argument(r"user-data-dir=C:\whatsapp_selenium_profile")

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )

    driver.get("https://web.whatsapp.com")
    return driver

def get_unread_contacts(driver):
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    import time
    import re

    wait = WebDriverWait(driver, 60)

    try:
        wait.until(
            EC.presence_of_element_located((By.XPATH, "//div[@role='grid']"))
        )

        time.sleep(7)

        unread_results = []

        unread_badges = driver.find_elements(
            By.XPATH,
            "//span[contains(@aria-label,'unread')]"
        )

        print("Detected unread badges:", len(unread_badges))

        for badge in unread_badges:
            try:
                label = badge.get_attribute("aria-label")
                match = re.search(r"(\d+)", label)
                unread_count = match.group(1) if match else "1"

                chat_container = badge.find_element(
                    By.XPATH,
                    "./ancestor::div[@role='row']"
                )

                try:
                    contact_element = chat_container.find_element(
                        By.XPATH,
                        ".//span[@dir='auto']"
                    )
                    contact_name = contact_element.text.strip()
                    if not contact_name:
                        contact_name = "Unknown Contact"
                except:
                    contact_name = "Unknown Contact"

                unread_results.append({
                    "contact": contact_name,
                    "count": unread_count
                })

            except:
                continue

        driver.quit()
        return unread_results

    except Exception as e:
        print("Error:", e)
        driver.quit()
        return []