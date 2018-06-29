# -*- coding: utf-8 -*-

import requests
import time
import os
import sys
import pathlib
import random
import datetime
import re
import logging

import progressbar

from requests.exceptions import ReadTimeout

from bs4 import BeautifulSoup
from fpdf import FPDF
from termcolor import colored
from torrequest import TorRequest


print(colored("""
oooooooooooo   .oooooo.   oooo    oooo          ooooo        ooooooooooooo ooooooooo.    .oooooo..o
`888'     `8  d8P'  `Y8b  `888   .8P'           `888'        8'   888   `8 `888   `Y88. d8P'    `Y8
 888         888           888  d8'              888              888       888   .d88' Y88bo.     
 888oooo8    888           88888[                888              888       888ooo88P'   `"Y8888o. 
 888    "    888           888`88b.              888              888       888`88b.         `"Y88b
 888         `88b    ooo   888  `88b.            888       o      888       888  `88b.  oo     .d8P
o888o         `Y8bood8P'  o888o  o888o           o888ooooood8     o888o     o888o  o888o 8""88888P' """, 'yellow'))


# Urls and account credentials
URL_CSRF = 'https://www.litres.ru/pages/login'
URL_AUTH = 'https://www.litres.ru/'
URL_PAGE = ''

LOGIN = ''
PASSWORD = ''

DEFAULT_USER_AGENT = 'Mozilla/5.0 (X11; Fedora; Linux x86_64; rv:60.0) Gecko/20100101 Firefox/60.0'
TOR_PROXIES = {
    'http': "socks5://127.0.0.1:9050",
    'https': "socks5://127.0.0.1:9050"
}

MAX_RETRIES = 0
GET_PAGE_RETRIES = 0
CHANGE_FILE_EXTENSION = 0

PAGE_NUMBER = 0
FILE_EXTENSION = 'gif'
FILE_EXTENSION_DICT = {'gif': 'gif', 'jpg': 'jpg'}


# Create session.
client = requests.Session()

# Set logger
logger = logging.getLogger("Main")
logger.setLevel(logging.INFO)

fh = logging.FileHandler('fck_ltrs.log')
logger.addHandler(fh)


# Need for check time of script execution.
class Profiler(object):
    def __enter__(self):
        self._startTime = time.time()

    def __exit__(self, type, value, traceback):
        elapsed_time_min = (time.time() - self._startTime) / 60
        print(colored("Elapsed time: {:.3f} sec or ({}) min".format((time.time() - self._startTime), elapsed_time_min),
                      'yellow'))


def progressbar_widget(text, range_=3, sleep=1):
    widgets = [
        text + '\t', progressbar.Percentage()
    ]

    for i in progressbar.progressbar(range(range_), widgets=widgets):
        time.sleep(sleep)


def get_random_user_agent():
    # Get path to ua file.
    path = sys.argv[0]
    path = os.path.join(os.path.dirname(path), 'ua')

    file_name = path + '/Firefox.txt'

    # Read lines from ua file.
    with open(file_name) as file:
        lines = file.readlines()

    # Get random ua.
    random.seed(datetime.datetime.now())

    try:
        user_agent = lines[random.randint(0, len(lines) - 1)]
    except IndexError:
        user_agent = DEFAULT_USER_AGENT

    clear_ua = re.sub("^\s+|\n|\r|\s+$", '', user_agent)

    return clear_ua


def get_csrf_token(auth_url, user_agent=DEFAULT_USER_AGENT, proxies=None):
    client.cookies.clear()

    headers = {'User-Agent': user_agent}

    try:
        html = client.get(auth_url, headers=headers, proxies=proxies, timeout=(3.05, 27), stream=True)
    except Exception as e:
        print(e)
        html = client.get(auth_url, headers=headers, proxies=proxies, timeout=(3.05, 27), stream=True)

    if html.status_code == 200:
        soup = BeautifulSoup(html.text, 'lxml')

        try:
            csrf = soup.find(id='frm_login').find('input').get('value')

        except AttributeError:
            global MAX_RETRIES
            csrf = None

            while MAX_RETRIES != 5:
                MAX_RETRIES += 1

                # Set text and log.
                text = '[ERROR] Perhaps server was banned your ip. Tor is activated. Changing ip...'
                progressbar_widget(colored(text, 'red'), range_=2, sleep=1)

                dt = datetime.datetime.now().strftime("%A, %d. %B %Y %I:%M%p")
                logger.info(dt + text)

                # Activate tor , change ip , call func which getting csrf token again.
                with TorRequest(proxy_port=9050, ctrl_port=9051, password=None) as tr:
                    tr.reset_identity()

                csrf = get_csrf_token(auth_url, user_agent=get_random_user_agent(), proxies=TOR_PROXIES)
                break

        return csrf

    else:
        return False


def auth(csrf_token, auth_url, user_agent=DEFAULT_USER_AGENT):
    headers = {'User-Agent': user_agent}
    data = {
        'csrf': csrf_token,
        'login': LOGIN,
        'pre_action': 'login',
        'pwd': PASSWORD,
        'ref_url': '/',
    }

    try:
        client.post(url=auth_url, stream=True, headers=headers, data=data, timeout=(3.05, 27))

        return True

    except Exception as e:
        print(e)
        return False


def get_page_bin(page_url, user_agent=DEFAULT_USER_AGENT):
    headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'User-Agent': user_agent
    }

    try:
        binary_page = client.get(page_url, stream=True, headers=headers, proxies=TOR_PROXIES, timeout=(3.05, 27))
    except ReadTimeout:
        pass

    except Exception as e:
        print(e)
        binary_page = client.get(page_url, stream=True, headers=headers, proxies=TOR_PROXIES, timeout=(3.05, 27))

    # Check on real page. If the requested page is out range - return None.
    if binary_page.status_code == 200:
        return binary_page.content

    else:
        # Где то здесь ошибка , связанная с тормозом скрипта. Уже не факт , что из за этого)))

        global GET_PAGE_RETRIES
        global CHANGE_FILE_EXTENSION

        while GET_PAGE_RETRIES == 0:
            GET_PAGE_RETRIES += 1
            CHANGE_FILE_EXTENSION += 1

            # Get new session and getting csrf token.
            csrf_token = get_csrf_token(URL_CSRF, user_agent=get_random_user_agent())

            # Authentication.
            auth(csrf_token, URL_AUTH, user_agent=get_random_user_agent())

            # Get binary page.
            formatted_url_page = URL_PAGE.format(PAGE_NUMBER, FILE_EXTENSION_DICT['gif'])
            binary_page = get_page_bin(formatted_url_page, user_agent=get_random_user_agent())

            break

        while GET_PAGE_RETRIES == 1 and CHANGE_FILE_EXTENSION == 1:
            text = colored('[ERROR] Perhaps script find not gif format in URL request. Changing format from gif to '
                           'jpeg...', 'red')
            progressbar_widget(text)

            # Set text in log.
            dt = datetime.datetime.now().strftime("%A, %d. %B %Y %I:%M%p")
            logger.info(dt + text)

            # Changing file format in url request.
            global FILE_EXTENSION
            FILE_EXTENSION = FILE_EXTENSION_DICT['jpg']

            CHANGE_FILE_EXTENSION += 1

            # Get binary page with other file format.
            formatted_url_page = URL_PAGE.format(PAGE_NUMBER, FILE_EXTENSION_DICT['jpg'])
            binary_page = get_page_bin(formatted_url_page, user_agent=get_random_user_agent())

            break

    return binary_page


def write_file(bin_page, page_number_):
    path = sys.argv[0]
    path = os.path.join(os.path.dirname(path), 'downloaded')
    pathlib.Path(path).mkdir(parents=True, exist_ok=True)

    # Check global file format.
    global FILE_EXTENSION

    file_name = path + '/{}.{}'.format(str(page_number_), FILE_EXTENSION)
    FILE_EXTENSION = FILE_EXTENSION_DICT['gif']

    with open(file_name, 'wb') as target:
        try:
            target.write(bin_page)
        except TypeError:
            os.remove(file_name)

            dt = datetime.datetime.now().strftime("%A, %d. %B %Y %I:%M%p")
            text = colored('[' + dt + '] ', 'yellow')
            print(text + 'Last page was downloaded. Waiting for next step.')

            return False


def sort_files():
    # Get all downloaded files.
    images_dir_path = sys.argv[0]
    images_dir_path = os.path.join(os.path.dirname(images_dir_path), 'downloaded')

    pages_list = os.listdir(images_dir_path)

    # Eject page numbers from files names
    new_pages_list = []
    not_gif_file_extensions_list = []

    [new_pages_list.append(int(page.split('.')[0])) for page in pages_list]

    # Create list of non gif files.
    [not_gif_file_extensions_list.append(page.split('.')) for page in pages_list if page.split('.')[1] != 'gif']

    # Sort gif files list.
    new_pages_list.sort()

    # Add full path to all files of sorted list and change extension of non gif files.
    sorted_files_list = []

    for page in new_pages_list:
        file_name = images_dir_path + '/' + str(page) + '.gif'

        for non_gif_file in not_gif_file_extensions_list:
            if page == int(non_gif_file[0]):
                file_name = images_dir_path + '/' + str(page) + '.' + str(non_gif_file[1])

        sorted_files_list.append(file_name)

    return sorted_files_list


def create_pdf(sorted_files_list):
    pdf = FPDF()

    for image in sorted_files_list:
        pdf.add_page()
        pdf.image(image, 0, 0, 200, 300)

    path = sys.argv[0]
    path = os.path.join(os.path.dirname(path), 'result')

    pathlib.Path(path).mkdir(parents=True, exist_ok=True)

    file_name = path + '/book.pdf'

    pdf.output(file_name, "F")


def main():
    # Get current date.
    dt = datetime.datetime.now().strftime("%A, %d. %B %Y %I:%M%p")

    # Get random Firefox user agent.
    user_agent = get_random_user_agent()

    # Get CSRF token.
    csrf_token = get_csrf_token(URL_CSRF, user_agent)

    if csrf_token is False or csrf_token is None:
        text = '[ERROR] While getting csrf token.'.format(dt)
        progressbar_widget(colored(text, 'red'))

        logger.info(dt + text)
        sys.exit(0)

    else:
        text = colored('Getting CSRF token...', 'green')
        progressbar_widget(text)
        print(colored('Done!', 'blue'))

    # Authentication in site.
    result = auth(csrf_token, URL_AUTH, user_agent)

    text = colored('Authentication...', 'green')
    progressbar_widget(text)
    print(colored('Done!', 'blue'))

    if result is False:
        logger.info('[{}] Error while authentication in the site.'.format(dt))
        sys.exit(0)

    # Get binary page and write it into file.
    global PAGE_NUMBER
    global MAX_RETRIES
    global GET_PAGE_RETRIES
    global CHANGE_FILE_EXTENSION

    while True:
        MAX_RETRIES = 0
        GET_PAGE_RETRIES = 0
        CHANGE_FILE_EXTENSION = 0

        formatted_url_page = URL_PAGE.format(PAGE_NUMBER, FILE_EXTENSION_DICT['gif'])

        # Get date and time.
        dt2 = datetime.datetime.now().strftime("%A, %d. %B %Y %I:%M:%S%p")

        # Get binary page.
        bin_page = get_page_bin(formatted_url_page, user_agent)

        # Check on real page.
        result = write_file(bin_page, PAGE_NUMBER)

        if result is False:
            break

        PAGE_NUMBER += 1

        # Set current page into log.
        logger.info('[{}] Page #{} has been written into file.'.format(dt2, PAGE_NUMBER))

        # Set widget.
        texts_list = ['[{}] Writing binary page #{} into file...'.format(colored(dt2, 'yellow'),
                                                                         colored(PAGE_NUMBER, 'yellow',
                                                                                 attrs=['bold'])),
                      '[{}] Page #{} has been written into file.'.format(colored(dt2, 'yellow'),
                                                                         colored(PAGE_NUMBER, 'yellow',
                                                                                 attrs=['bold']))]

        for text in texts_list:
            progressbar_widget(text)

        print(colored('Done!', 'blue'))

    # Sort downloaded files.
    sorted_files_list = sort_files()

    # Create PDF file.
    creating_pdf_text = '[{}] All pages was successfully downloaded. PFD file creating...'.format(colored(dt2, 'blue'))
    progressbar_widget(creating_pdf_text)

    create_pdf(sorted_files_list)

    done_pdf_text = '[{}] PDF file was created'.format(colored(dt2, 'blue'))
    progressbar_widget(done_pdf_text)

    # Set info into log.
    logger.info(creating_pdf_text)
    print(colored('Done!', 'blue'))


if __name__ == '__main__':
    with Profiler() as p:
        print(colored('Start time: {}'.format(datetime.datetime.now().strftime("%A, %d. %B %Y %I:%M%p")), 'green'))
        main()
        print(colored('End time: {}'.format(datetime.datetime.now().strftime("%A, %d. %B %Y %I:%M%p")), 'green'))
