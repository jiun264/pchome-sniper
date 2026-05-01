import sys
import traceback

print("Testing undetected_chromedriver...")
try:
    import undetected_chromedriver as uc
    options = uc.ChromeOptions()
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    print("Initializing uc.Chrome...")
    driver = uc.Chrome(options=options)
    print("UC OK! Closing...")
    driver.quit()
except Exception as e:
    print(f"UC Failed: {e}")
    traceback.print_exc()
