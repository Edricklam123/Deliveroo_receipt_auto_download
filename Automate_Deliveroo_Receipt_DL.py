# Author: Edrick Lam
# Create: 7/21/2021

# Import libraries
import os
import re
import sys
import datetime
import time
import urllib.request
import pandas as pd
from dateutil import parser
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from login_config import *        # A dictionary holding your account credentials

def login_deliveroo(driver, account_dict):
    driver.get('https://deliveroo.co.uk/login?redirect=%2F')
    try:
        driver.find_element_by_id('onetrust-accept-btn-handler').click()
    except Exception as err:
        print(f'[SYS] Encoutnered exceptions requires manual resovle: {err}')
        input('[SYS] Press ENTER when resolved...')

    # main_page -> find login button -> click
    main_window = driver.current_window_handle
    # driver.find_element_by_xpath('//*[.="Menu"]').click()
    # time.sleep(5)
    # driver.find_elements_by_xpath('//span[.="Sign up or log in"]')[0].click()
    # time.sleep(2)
    driver.find_element_by_xpath('//button[@class="orderweb__839c60e3 metro"]').click()
    time.sleep(2)
    driver.switch_to.window(driver.window_handles[1])

    # login_page -> fill details -> login
    driver.find_element_by_id('email').send_keys(account_dict['facebook'][0])
    driver.find_element_by_id('pass').send_keys(account_dict['facebook'][1])
    driver.find_element_by_name('login').click()

    # return to main_page -> travel to order_history_page
    driver.switch_to.window(main_window)
    time.sleep(2)


if __name__ == '__main__':
    # environment setup
    OUTPUT_MASTER_FOLDER = r'C:\PATH\TO\OUTPUT\DIR'
    TODAY = datetime.datetime.today().date()
    OUTPUT_FOLDER = f'{TODAY.strftime("%B")} {TODAY.strftime("%Y")}'
    if not os.path.isdir(f'{OUTPUT_MASTER_FOLDER}\\{OUTPUT_FOLDER}'):
        print(f'[SYS] Creating directory for {OUTPUT_FOLDER}' )
        os.makedirs(f'{OUTPUT_MASTER_FOLDER}\\{OUTPUT_FOLDER}')
    # Set default download director and change the setting
    options = webdriver.ChromeOptions()
    prefs = {"profile.default_content_settings.popups": 0,
             "download.default_directory": rf'{OUTPUT_MASTER_FOLDER}\{OUTPUT_FOLDER}\\',  # IMPORTANT - ENDING SLASH V IMPORTANT
             "directory_upgrade": True}
    options.add_experimental_option("prefs", prefs)
    # options.add_argument('--log-level 3') # -> do not print logging info to console

    driver = webdriver.Chrome(executable_path=r'C:\path_to_chromedriver\chromedriver.exe',
                              chrome_options=options)
    time.sleep(3)
    # use function to login Deliveroo
    login_deliveroo(driver, account_dict)

    # Goto Order History page

    # driver.find_element_by_xpath('//*[.="Menu"]').click()
    try:
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.XPATH, '//*[.="Menu"]'))
        )
    finally:
        time.sleep(5)
        driver.find_element_by_xpath('//*[.="Menu"]').click()

    # time.sleep(1)
    driver.find_element_by_xpath('//*[.="Order History"]').click()
    # driver.get('https://deliveroo.co.uk/orders')


    # procedure to get the updated class name
    tag_to_find = r'<a href="/orders/'
    starting_position = driver.page_source.find(tag_to_find)
    clause = driver.page_source[starting_position: starting_position+100] # more space to play safe
    ending_position = clause.find('>') + 1
    processing_clause = clause[:ending_position]
    orders_class_name = BeautifulSoup(processing_clause, 'lxml').find('a').attrs['class'][0]

    soup = BeautifulSoup(driver.page_source, 'lxml')
    order_list = soup.find_all('a', class_=orders_class_name)
    table_list = []
    for dinner in order_list:
        row = []
        row.append(dinner['href'])
        for x in dinner.find_all('p'):
            row.append(x.text)
        table_list.append(row)

    order_history_tb = pd.DataFrame(table_list)
    order_history_tb.columns = ['link', 'name', 'amount', 'details']
    order_history_tb['link'] = order_history_tb['link'].str.replace(u'/orders/','')
    order_history_tb[['amount', 'date']] = order_history_tb['details'].str.split(' • ', expand=True)
    order_history_tb['month'] = pd.to_datetime(order_history_tb['date']).dt.month
    order_history_tb['date'] = pd.to_datetime(order_history_tb['date']).dt.date
    order_history_tb.drop_duplicates(subset='date', keep='first', inplace=True)

    order_history_tb.drop('details', axis=1, inplace=True)

    # Check the latest receipt
    existing_files = os.listdir(rf'{OUTPUT_MASTER_FOLDER}\{OUTPUT_FOLDER}')
    # there is no files in the folder - either new month or new download
    # Gather all the dates in the existing receipts
    downloaded_dates = []
    for file in existing_files:
        if file != 'Taxi':
            try:
                downloaded_dates.append(parser.parse(file, fuzzy=True).date())
            except:
                print(f'[ERR] Cannot recognize dates in file "{file}"')
                pass
    today_date = datetime.datetime.today().date()
    order_history_tb = order_history_tb.query('month == @today_date.month & date not in @downloaded_dates')
    num_receipt_dl = len(order_history_tb)

    if num_receipt_dl == 0:
        print('[SYS] There is no new receipt for this month. Quit program now...')
        driver.quit()
        quit()

    # Downloading files
    # We assume we will download from the latest order
    for i in range(len(order_history_tb)):
        print(f'[INFO] Downloading receipts as of {order_history_tb.iloc[i]["date"]}')
        url = 'receipt/'.join(['https://deliveroo.co.uk/order/', order_history_tb.iloc[i]["link"]])
        driver.get(url)       # downloaded to folder
        time.sleep(1)         # I am lazy not writing the check function
        amount = float(order_history_tb.iloc[i]["amount"].lstrip('$'))
        DATE = order_history_tb.iloc[i]["date"].strftime("%d %B %Y")
        for filename in os.listdir(f'{OUTPUT_MASTER_FOLDER}\{OUTPUT_FOLDER}'):
            filepath = rf'{OUTPUT_MASTER_FOLDER}\{OUTPUT_FOLDER}\{filename}'
            if time.time() - os.stat(filepath).st_mtime < 30 and filename.endswith('.pdf') and 'Dinner' not in filename:
                # TODO: rename the file according to table
                # If price > $280 -> name it with Peter
                if amount > 280:
                    new_filepath = rf'{OUTPUT_MASTER_FOLDER}\{OUTPUT_FOLDER}\{DATE} Dinner with .pdf'
                else:
                    new_filepath = rf'{OUTPUT_MASTER_FOLDER}\{OUTPUT_FOLDER}\{DATE} Dinner.pdf'
                os.rename(filepath, new_filepath)

    print('[SYS] Finished downloading...')
    driver.quit()

