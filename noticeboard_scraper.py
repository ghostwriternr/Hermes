"""
Scraper for the UG Notice board
"""
from os import environ as env
from urllib.parse import urljoin
import hashlib
from bs4 import BeautifulSoup
import requests
from pymongo import MongoClient

import settings

MC = MongoClient(env['MONGODB_URI'])
REQUESTS_SESSION = requests.Session()

BASE_URL = 'http://noticeboard.iitkgp.ernet.in/'
SUB_URLS = [
    'acad_ug/',
    'acad_pg/',
    'bcrth/'
]

def scrape_notice(notice_url, section, notice_has_attachment):
    """
    Scrape method for each notice
    """
    requests_response = REQUESTS_SESSION.get(notice_url)
    soup = BeautifulSoup(requests_response.text, "html.parser")
    notice = soup.find_all('tr')
    notice_details = notice[0].find_all('td')
    notice_title = notice_details[0].get_text()
    notice_time = notice_details[1].get_text()
    notice_text = notice[1].find('div').get_text()
    notice_json = {}
    notice_json['title'] = notice_title
    notice_json['time'] = notice_time.strip()
    notice_json['text'] = notice_text
    hash_md5 = hashlib.md5()
    if notice_has_attachment:
        notice_attachment = notice[1].find('a').get('href')
        notice_json['attachment'] = BASE_URL + section + notice_attachment
        attachment_response = REQUESTS_SESSION.get(notice_json['attachment'], stream=True)
        attachment_response.raw.decode_content = True
        for chunk in iter(lambda: attachment_response.raw.read(4096), b""):
            hash_md5.update(chunk)
        notice_json['attachment_md5'] = hash_md5.hexdigest()
    return notice_json

def handle_notices_diff(section, notices):
    """
    Method to check for new/updated notices
    """
    new_notices = []
    section_coll = MC.get_database()[section.split('/')[0]]
    for notice in notices:
        db_notice = section_coll.find_one(notice)
        if db_notice is None:
            new_notices.append(notice)
            section_coll.insert_one(notice)
    return new_notices

def scrape_noticeboard(section):
    """
    Scrape method for selected noticeboard section
    """
    requests_response = REQUESTS_SESSION.get(BASE_URL + section)
    soup = BeautifulSoup(requests_response.text, "html.parser")
    notices = []
    while True:
        noticeboard = soup.find('td', {'valign': 'top'}).find('table')
        all_notices = noticeboard.find_all('tr')
        for notice in all_notices:
            notice_columns = notice.find_all('td')
            if len(notice_columns) == 3:
                notice_has_attachment = not notice_columns[1].find('a', {'class': 'notice'}) is None
                notice_url = notice_columns[2].find('a').get('href')
                notice_url = BASE_URL + section + notice_url
                notice_json = scrape_notice(notice_url, section, notice_has_attachment)
                notices.append(notice_json)
        try:
            next_page = all_notices[-1].find(
                'font', {'class': 'text'}).find('a', {'class': 'notice'})
            next_page_url = next_page.get('href')
            soup = BeautifulSoup(REQUESTS_SESSION.get(
                urljoin(BASE_URL, next_page_url)).text, "html.parser")
        except AttributeError:
            break
    new_notices = handle_notices_diff(section, notices)
    return new_notices

def scrape():
    """
    Scrape method for all noticeboard sections
    """
    new_notices = {}
    for section in SUB_URLS:
        section_notices = scrape_noticeboard(section)
        new_notices[section.split('/')[0]] = section_notices
    return new_notices

if __name__ == "__main__":
    scrape()
