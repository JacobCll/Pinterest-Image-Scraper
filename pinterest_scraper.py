from concurrent.futures import ThreadPoolExecutor
from bs4 import BeautifulSoup as soup
from dotmap import DotMap
from tqdm import tqdm
import numpy as np
import requests
import json
import cv2
import re
import os

class PinterestImgScraper:
    def __init__(self):
        self.jsondata_list = []
        # an array of unique dhashes
        self.unique_images = []

    def scrape_pinterest(self, search=None):
        pinterest_urls = []

        try: 
            search = input("Search Pinterest for: ") if search == None else search
            url = f'http://www.google.co.in/search?hl=en&q={search} pinterest'
            url = url.replace("+", "%2B").replace(" ", "%20")

            res = requests.get(url)
            html = soup(res.content, 'html.parser')

            links = html.select('#main > div > div > div > a')

            for link in links:
                link = link.get('href');
                link = re.sub(r'/url\?q=', '', link)
                if link[0] != "/" and "pinterest" in link:
                    pinterest_urls.append(link)
        except Exception:
            return []

        folder_name = search.replace(" ", "_")
        return pinterest_urls, folder_name

    # this function updates the array self.jsondata_list[]
    def get_json(self, pint_urls):
        try:    
            for url in pint_urls:
                # unicode 
                response = requests.get(url).text
                html = soup(response, 'html.parser')
                json_data = html.find("script", attrs={"id": "__PWS_DATA__"})
                self.jsondata_list.append(json_data.string)

        except Exception:
            return

    # get image urls from json file
    def get_img(self):
        image_urls = []
        if not len([i for i in self.jsondata_list if i.strip()]):
            return []
        
        for js in self.jsondata_list:
            try:
                data = DotMap(json.loads(js))
                # navigate through the dotmap to get original url links
                for pin in data.props.initialReduxState.pins:
                    # if orig is a list of urls 
                    if isinstance(data.props.initialReduxState.pins[pin].images.get("orig"), list):
                        for i in data.props.initialReduxState.pins[pin].images.get("orig"):
                            image_urls.append(i.get("url"))
                    else:
                        image_urls.append(data.props.initialReduxState.pins[pin].images.get("orig").get("url"))
            except Exception:
                continue

        # set for no duplicates
        return list(set(image_urls))
    
    # dhash image hash algorithm to remove duplicates in self.unique_images[]
    def dhash(self, image, hashSize=8):
        resized = cv2.resize(image, (hashSize + 1, hashSize))
        diff = resized[:, 1:] > resized[:, :-1]
        return sum([2 ** i for (i, v) in enumerate(diff.flatten()) if v])
    

    def download(self, tup):
        img_urls, folder_name = tup
        if not os.path.exists(os.path.join(os.getcwd(), folder_name)):
            os.mkdir(os.path.join(os.getcwd(), folder_name))

        for url in tqdm(img_urls):
            # get byte data of the image
            result = requests.get(url, stream=True).content
            # initialize file path for image
            file_name = url.split("/")[-1]
            file_path = os.path.join(os.getcwd(), folder_name, file_name)
            # convert the bytearray to an np array 
            # dtype represents unsigned 8-bit integers (0-255)
            # imgarr contains the binary image data 
            imgarr = np.asarray(bytearray(result), dtype="uint8")
            # load full image and store in the created file path
            image  = cv2.imdecode(imgarr, cv2.IMREAD_COLOR)

            # check if the image hash is unique
            if not self.dhash(image) in self.unique_images:
                # download image
                cv2.imwrite(file_path, image)

            self.unique_images.append(self.dhash(image))

    def mult_dl(self, url_list, keyword):
        folder_name = keyword
        num_of_workers = 10
        idx = len(url_list) // num_of_workers if len(url_list) > 9 else len(url_list)

        param = []
        for i in range(num_of_workers):
            param.append((url_list[((i*idx)):(idx*(i+1))], folder_name))

        with ThreadPoolExecutor(max_workers=num_of_workers) as exe:
            exe.map(self.download, param)

    def scrape(self, search=None):
        self.jsondata_list = []
        self.unique_images = []

        pinterest_urls, folder_name = self.scrape_pinterest(search)
        print(f"==Scraping {folder_name} on Pinterest==")

        self.get_json(pinterest_urls)

        image_urls = self.get_img()
        
        print()
        print(f"=={len(image_urls)} files will be downloaded==")
        
        if len(image_urls):
            try:
                self.mult_dl(image_urls, folder_name)
            except KeyboardInterrupt:
                return False
            return True
        return False
        
if __name__ in "__main__":
    scraper = PinterestImgScraper()
    is_downloaded = scraper.scrape()

    if is_downloaded:
        print("\n==Downloading completed==")
    else:
        print("\n==Nothing to download==")
