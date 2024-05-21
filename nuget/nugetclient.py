import base64
import gzip
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from hashlib import sha256
from typing import Any
from urllib.parse import quote, urljoin

import jsonpickle
import requests

import globals

from .models import main_index as main
from .models import metadata as meta


@dataclass()
class CacheEntry:
    keyhash: str
    expiry_date: datetime = field(
        default_factory=lambda: datetime.now() + timedelta(days=10))

    @staticmethod
    def from_filename(filename: str) -> 'CacheEntry':
        keyhash, expiry_base64, _ = filename.split('.')
        expiry_str = base64.b64decode(expiry_base64).decode()
        expiry_date = datetime.fromisoformat(expiry_str)
        return CacheEntry(keyhash, expiry_date)

    @property
    def filename(self) -> str:
        expiry_bytes = self.expiry_date.isoformat().encode()
        expiry_base64 = base64.b64encode(expiry_bytes).decode()
        return f'{self.keyhash}.{expiry_base64}.cache'


class Cache:
    def __init__(self, cache_dirpath: str) -> None:
        self.cache_dirpath = cache_dirpath
        self.index: dict[str, CacheEntry] = {}

    @staticmethod
    def hashkey(key: str) -> str:
        return sha256(key.encode()).hexdigest()

    @staticmethod
    def init(cache_dirpath: str) -> 'Cache':
        def load_index(_cache: Cache) -> None:
            for filename in os.listdir(cache_dirpath):
                ce = CacheEntry.from_filename(filename)
                _cache.index[ce.keyhash] = ce

        if not os.path.exists(cache_dirpath):
            os.mkdir(cache_dirpath)

        cache = Cache(cache_dirpath)
        load_index(cache)
        return cache

    def add(self, key: str, value: Any) -> None:
        keyhash = Cache.hashkey(key)

        with globals.lock:
            if ce := self.index.get(keyhash):
                del self.index[keyhash]
                filepath = os.path.join(self.cache_dirpath, ce.filename)
                os.remove(filepath)

            cache_entry = CacheEntry(keyhash)
            self.index[cache_entry.keyhash] = cache_entry

            filepath = os.path.join(self.cache_dirpath, cache_entry.filename)
            with gzip.open(filepath, mode='wb') as file:
                json: str = jsonpickle.encode(value)
                file.write(json.encode())

    def get(self, key: str) -> Any | None:
        keyhash = Cache.hashkey(key)

        with globals.lock:
            if keyhash not in self.index:
                return None
            filepath = os.path.join(
                self.cache_dirpath, self.index[keyhash].filename)
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
        def find_metadata(_index: meta.Index, _version: meta.Version) -> meta.IndexItem | None:
            for item in _index.items:
                if item.version_range.inrange(_version):
                    return item
            return None

        def find_catalogitem(catalog_pages: list[meta.CatalogPage], _version: meta.Version) -> meta.CatalogItem | None:
            for page in catalog_pages:
                for item in page.items:
                    if item.entry.version.text == _version.text:
                        return item
            return None

        def get_catalogpages(index_item: meta.IndexItem) -> list[meta.CatalogPage]:
            pages: list[meta.CatalogPage] = []

            response = self.httpclient.get(index_item.metadata.url)
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

        def get_index(_package_name: str) -> meta.Index:
            id = self.__index.resources['RegistrationsBaseUrl/3.6.0'][0].id
            url = urljoin(id, f'{_package_name.lower()}/index.json')
            url = quote(url, safe='/:')
            resp = self.httpclient.get(url)
            json = resp.json()
            return meta.Index.create(json)

        index = get_index(package_name)
        version = meta.Version.create(package_version)
        metadata = find_metadata(index, version)
        catalogpages = get_catalogpages(metadata)
        return find_catalogitem(catalogpages, version)
