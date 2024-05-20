import json
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import quote, urljoin
from uuid import uuid4
import gzip

import jsonpickle
import requests

import globals

from .models import main_index as main
from .models import metadata as meta


@dataclass(init=False)
class CacheEntry:
    timestamp = datetime
    filename: str

    @staticmethod
    def create() -> 'CacheEntry':
        ce = CacheEntry()
        ce.timestamp = datetime.now()
        ce.filename = f'{uuid4()}.cache'
        return ce

    @staticmethod
    def loadjson(data: dict[str, str]) -> 'CacheEntry':
        ce = CacheEntry()
        ce.timestamp = datetime.fromisoformat(data['timestamp'])
        ce.filename = data['filename']
        return ce

    def dump(self) -> dict[str, str]:
        d = {}
        d['timestamp'] = self.timestamp.isoformat()
        d['filename'] = self.filename[:]
        return d

    def refresh(self) -> None:
        self.timestamp = datetime.now()


class Cache:
    INDEX_FILENAME = 'index.json'

    def __init__(self, cache_dirpath: str) -> None:
        self.cache_dirpath = cache_dirpath
        self.index: dict[str, CacheEntry] = {}
        self.index_filepath = os.path.join(cache_dirpath, Cache.INDEX_FILENAME)

    @staticmethod
    def init(cache_dirpath: str) -> 'Cache':
        def load_index(cache: Cache) -> None:
            if os.path.exists(cache.index_filepath) and os.path.isfile(cache.index_filepath):
                with open(cache.index_filepath, mode='rt') as file:
                    data: dict = json.load(file)
                    for key in data.keys():
                        cache.index[key] = CacheEntry.loadjson(data[key])

        if not os.path.exists(cache_dirpath):
            os.mkdir(cache_dirpath)

        cache = Cache(cache_dirpath)
        load_index(cache)
        return cache

    def save(self) -> None:
        with globals.lock:
            index_dict: dict[str, dict[str, str]] = {}
            for key in self.index.keys():
                index_dict[key] = self.index[key].dump()

            with open(self.index_filepath, mode='wt') as file:
                json.dump(index_dict, file)

    def add(self, key: str, value: Any) -> None:
        with globals.lock:
            cache_entry: CacheEntry = None
            if ce := self.index.get(key):
                ce.refresh()
                cache_entry = ce
            if not cache_entry:
                cache_entry = CacheEntry.create()
                self.index[key] = cache_entry

            filepath = os.path.join(self.cache_dirpath, cache_entry.filename)
            with gzip.open(filepath, mode='wb') as file:
                json: str = jsonpickle.encode(value)
                file.write(json.encode())

            self.save()

    def get(self, key: str) -> Any | None:
        with globals.lock:
            if key not in self.index:
                return None
            filepath = os.path.join(
                self.cache_dirpath, self.index[key].filename)
            with gzip.open(filepath, mode='rb') as file:
                json = file.read().decode()
                value = jsonpickle.decode(json)
                return value


class CachedHttpClient:
    def __init__(self, cache_dirpath: str) -> None:
        self.cache = Cache.init(cache_dirpath)
        self.session = requests.Session()

    def get(self, url: str) -> requests.Response:
        if response := self.cache.get(url):
            return response
        response = self.session.get(url)
        response.raise_for_status()
        self.cache.add(url, response)
        return response


class NugetClient:
    NUGETORG_API_BASEURL = 'https://api.nuget.org/'

    def __init__(self, baseurl: str = None, cache_dirpath='./cache') -> None:
        self.httpclient = CachedHttpClient(cache_dirpath)
        self.baseurl = baseurl if baseurl else NugetClient.NUGETORG_API_BASEURL
        self.__index: main.Index = self.__get_index()

    def __get_index(self, version='v3') -> main.Index:
        url = urljoin(self.baseurl, f'/{version}/index.json')
        url = quote(url, safe="/:")
        resp = self.httpclient.get(url)
        index_json = resp.json()
        index = main.Index.create(index_json)
        return index

    def get_metadata(self, package_name: str, package_version: str) -> meta.CatalogItem | None:
        def find_metadata(index: meta.Index, version: meta.Version) -> meta.IndexItem | None:
            for item in index.items:
                if item.version_range.inrange(version):
                    return item
            return None

        def find_catalogitem(catalog_pages: list[meta.CatalogPage], version: meta.Version) -> meta.CatalogItem | None:
            for page in catalog_pages:
                for item in page.items:
                    if item.entry.version.text == version.text:
                        return item
            return None

        def get_catalogpages(metadata: meta.IndexItem) -> list[meta.CatalogPage]:
            pages: list[meta.CatalogPage] = []

            response = self.httpclient.get(metadata.url)
            json = response.json()
            type = json['@type']

            if type == 'catalog:CatalogPage':
                page = meta.CatalogPage.create(json)
                pages.append(page)
                return pages

            if 'catalog:CatalogRoot' in type:
                for item in (it for it in json['items'] if it['@type'] == 'catalog:CatalogPage'):
                    page = meta.CatalogPage.create(item)
                    pages.append(page)

            return pages

        def get_index(package_name: str) -> meta.Index:
            id = self.__index.resources['RegistrationsBaseUrl/3.6.0'][0].id
            url = urljoin(id, f'{package_name.lower()}/index.json')
            url = quote(url, safe='/:')
            resp = self.httpclient.get(url)
            json = resp.json()
            index = meta.Index.create(json)
            return index

        index = get_index(package_name)
        version = meta.Version.create(package_version)
        metadata = find_metadata(index, version)
        catalogpages = get_catalogpages(metadata)
        return find_catalogitem(catalogpages, version)
