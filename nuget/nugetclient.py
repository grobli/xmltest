from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import quote, urljoin

import requests

from .models import main_index as main
from .models import metadata as meta


@dataclass(init=False)
class CacheEntry:
    timestamp = datetime
    data: Any

    @staticmethod
    def create(data: Any) -> 'CacheEntry':
        ce = CacheEntry()
        ce.timestamp = datetime.now()
        ce.data = data
        return ce
    
class Cache:
    def __init__(self, cache_dirpath) -> None:
        pass


class NugetClient:
    NUGETORG_API_BASEURL = 'https://api.nuget.org/'

    def __init__(self, baseurl: str = None) -> None:
        self.baseurl = baseurl if baseurl else NugetClient.NUGETORG_API_BASEURL
        self.__index: main.Index = self.__get_index()
        pass

    def __get_index(self, version='v3') -> main.Index:
        url = urljoin(self.baseurl, f'/{version}/index.json')
        url = quote(url, safe="/:")
        resp = requests.get(url)
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

            response = requests.get(metadata.url)
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
            resp = requests.get(url)
            json = resp.json()
            index = meta.Index.create(json)
            return index

        index = get_index(package_name)
        version = meta.Version.create(package_version)
        metadata = find_metadata(index, version)
        catalogpages = get_catalogpages(metadata)
        return find_catalogitem(catalogpages, version)
