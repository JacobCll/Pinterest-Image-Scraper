from concurrent.futures import ThreadPoolExecutor
from bs4 import BeautifulSoup as soup
from dotmap import DotMap
import numpy as np
import requests
import json
import cv2
import re
import os

class MissingArgumentException(Exception):
    pass

class PinterestScraper:
    def __init__(self):
        self.jsondata_list = []
        self.unique_images = [] # an array of unique dhashes

    def scrape_pinterest(self, search: str):
        pinterest_urls = []
        try:         
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
        img_urls, output_path = tup

        for url in img_urls:
            # get byte data of the image    
            result = requests.get(url, stream=True).content
            # initialize file path for image
            file_name = url.split("/")[-1]
            file_path = os.path.join(output_path, file_name)
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

    def mult_dl(self, url_list, output_path):
        num_of_workers = 10
        idx = len(url_list) // num_of_workers if len(url_list) > 9 else len(url_list)

        param = []
        for i in range(num_of_workers):
            param.append((url_list[((i*idx)):(idx*(i+1))], output_path))

        with ThreadPoolExecutor(max_workers=num_of_workers) as exe:
            exe.map(self.download, param)

    def scrape(self, search: str=None, output_p: str=""):
        if __name__ == "__main__":
            search = input("Search Pinterest for: ")
            output_p = input("Path to Folder: ")
        else:
            if search is None or output_p == "":
                raise MissingArgumentException("Search term and/or output path argument/s missing.")
            
        if not os.path.exists(output_p):
            print(f"(-) Directory: {output_p} does not exist.")
            return False
        
        if not search:
            print("(-) Invalid search.")
            return False
        
        self.jsondata_list = []
        self.unique_images = []
        
        pinterest_urls, folder_name= self.scrape_pinterest(search)

        print(f"(+) Scraping {folder_name} on Pinterest")

        self.get_json(pinterest_urls)

        image_urls = self.get_img()

        print(f"(+) {len(image_urls)} files will be downloaded at {output_p}")
        
        if len(image_urls):
            try:
                self.mult_dl(image_urls, output_p)
            except KeyboardInterrupt:
                return False
            return True
        return False
        
if __name__ in "__main__":
    scraper = PinterestScraper()

    try:
        is_downloaded = scraper.scrape(search=None, output_p="")
    except:
        is_downloaded = False

    if is_downloaded:
        print("(+) Download completed.")
    else:
        print("(-) Nothing to download.")
