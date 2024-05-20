from dataclasses import dataclass
from typing import Any


@dataclass(init=False)
class Version:
    major: int
    minor: int
    patch: int
    release: str | None
    text: str

    @property
    def text(self) -> str:
        return f'{self.major}.{self.minor}.{self.patch}{self.release if self.release else ""}'

    @staticmethod
    def create(version_str: str) -> 'Version':
        release = None
        patch = None

        release_delimiter = '-'
        parts = version_str.strip().split(release_delimiter, maxsplit=1)
        if len(parts) == 1:
            parts = parts[0]
            release_delimiter = '+'
            parts = parts.split(release_delimiter, maxsplit=1)

        if len(parts) > 1:
            parts, release = parts
            release = f'{release_delimiter}{release}'
        else:
            parts = parts[0]

        parts = parts.split('.')

        if len(parts) == 2:
            major, minor = parts
        elif len(parts) == 3:
            major, minor, patch = parts
        elif len(parts) > 3:
            major, minor, patch, release = parts
            release = f'.{release}'
        v = Version()
        v.major = int(major)
        v.minor = int(minor)
        v.patch = int(patch) if patch else 0
        v.release = release
        return v

    def copy(self) -> 'Version':
        return Version.create(self.text)

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, Version):
            return False
        return self.text == value.text

    def __gt__(self, value: object) -> bool:
        if not isinstance(value, Version):
            raise ValueError(
                'cannot compare Version object with non-Version object')
        if self == value:
            return False

        if self.major > value.major:
            return True

        if self.major == value.major:
            if self.minor > value.minor:
                return True
            if self.minor == value.minor and self.patch > value.patch:
                return True
        return False

    def __lt__(self, value: object) -> bool:
        if not isinstance(value, Version):
            raise ValueError(
                'cannot compare Version object with non-Version object')
        if self == value:
            return False

        return not self > value

    def __ge__(self, value: object) -> bool:
        if not isinstance(value, Version):
            raise ValueError(
                'cannot compare Version object with non-Version object')
        return self == value or self > value

    def __le__(self, value: object) -> bool:
        if not isinstance(value, Version):
            raise ValueError(
                'cannot compare Version object with non-Version object')
        return self == value or self < value


@dataclass(repr=False)
class VersionRange:
    minimum: Version | None
    maximum: Version | None
    min_inclusive: bool = True
    max_inclusive: bool = True

    def __repr__(self) -> str:
        left_bracket = '[' if self.min_inclusive else '('
        right_bracket = ']' if self.max_inclusive else ')'
        minimum = self.minimum.text if self.minimum else ''
        maximum = self.maximum.text if self.maximum else ''
        return f'{left_bracket}{minimum}, {maximum}{right_bracket}'

    @staticmethod
    def from_rangestring(rangestr: str) -> 'VersionRange':
        min_inclusive = not rangestr.startswith('(')
        max_inclusive = not rangestr.endswith(')')
        minimum = None
        maximum = None

        parts = [p.strip() for p in rangestr.split(',')]
        if len(parts) == 1:
            versionstr = parts[0]
            if '[' in versionstr and ']' in versionstr:
                version = Version.create(versionstr[1:-1])
                minimum = version
                maximum = version
            else:
                version = Version.create(version)
                minimum = version
        elif len(parts) == 2:
            left, right = parts
            if not (left == '(' and right == ')'):
                if left == '(' or left == '[':
                    version = Version.create(right[:-1])
                    maximum = version
                elif right == ')':
                    version = Version.create(left[1:])
                    minimum = version
                else:
                    minimum = Version.create(left[1:])
                    maximum = Version.create(right[:-1])

        vrange = VersionRange(minimum, maximum, min_inclusive, max_inclusive)
        return vrange

    def inrange(self, version: Version) -> bool:
        if self.minimum:
            if self.minimum == version:
                return self.min_inclusive

            if self.minimum > version:
                return False

        if self.maximum:
            if self.maximum == version:
                return self.max_inclusive

            if self.maximum < version:
                return False
        return True

    def common_minimum_version(self, other: 'VersionRange') -> Version | None:
        minimum = None
        if self.minimum and other.minimum:
            if self.minimum > other.minimum and self.min_inclusive:
                minimum = self.minimum.copy()
            elif self.minimum < other.minimum and other.min_inclusive:
                minimum = other.minimum.copy()

        if self.minimum and not other.minimum and self.min_inclusive:
            minimum = self.minimum.copy()

        if other.minimum and not self.minimum and other.min_inclusive:
            minimum = other.minimum.copy()

        if self.maximum and other.maximum:
            if minimum:
                if self.maximum <= minimum and self.max_inclusive:
                    minimum = self.maximum.copy()
                if other.maximum <= minimum and other.max_inclusive:
                    minimum = other.maximum.copy()
            else:
                if self.maximum and other.maximum:
                    if self.maximum < other.maximum and self.max_inclusive:
                        minimum = self.maximum.copy()
                    elif self.maximum > other.maximum and other.max_inclusive:
                        minimum = other.maximum.copy()

        return minimum


@dataclass(init=False)
class IndexItem:
    url: str
    commit_id: str | None
    commit_timestamp: str | None
    count: int
    version_range: VersionRange

    @staticmethod
    def create(item_json: dict[str, Any]) -> 'IndexItem':
        item = IndexItem()
        item.url = item_json['@id']
        item.commit_id = item_json.get('commitId')
        item.commit_timestamp = item_json.get('commitTimeStamp')
        item.count = item_json['count']

        lower = Version.create(item_json['lower'])
        upper = Version.create(item_json['upper'])
        item.version_range = VersionRange(lower, upper)
        return item


@dataclass(init=False)
class Index:
    url: str
    commit_id: str | None
    commit_timestamp: str | None
    count: int
    items: list[IndexItem]

    @staticmethod
    def create(metadata_index_json: dict[str, Any]) -> 'Index':
        items: list[IndexItem] = []
        for item_json in metadata_index_json['items']:
            items.append(IndexItem.create(item_json))

        index = Index()
        index.url = metadata_index_json['@id']
        index.commit_id = metadata_index_json.get('commitId')
        index.commit_timestamp = metadata_index_json.get('commitTimeStamp')
        index.count = metadata_index_json['count']
        index.items = items
        return index


@dataclass(init=False)
class Dependency:
    url: str
    type: str
    name: str
    range: VersionRange

    @staticmethod
    def create(depjson: dict[str, Any]) -> 'Dependency':
        d = Dependency()
        d.url = depjson['@id']
        d.type = depjson['@type']
        d.name = depjson['id']

        rangestr = depjson.get('range')
        rangestr = rangestr if rangestr else '(, )'
        d.range = VersionRange.from_rangestring(rangestr)
        return d


@dataclass(init=False)
class DependencyGroup:
    target_framework: str | None
    dependencies: list[Dependency]

    @staticmethod
    def create(depgroupjson: dict[str, Any]) -> 'DependencyGroup':
        dg = DependencyGroup()
        dg.target_framework = depgroupjson.get('targetFramework')
        dg.target_framework = dg.target_framework.lower() if dg.target_framework else None
        deps: list[Dependency] = []
        if 'dependencies' in depgroupjson:
            for dep in depgroupjson['dependencies']:
                d = Dependency.create(dep)
                deps.append(d)
        dg.dependencies = deps
        return dg


@dataclass(init=False)
class Vulnerability:
    advisory_url: str
    severity: int
    severity_name: str

    @property
    def severity_name(self) -> str:
        return ['Low', 'Moderate', 'High', 'Critical'][self.severity]

    @staticmethod
    def create(vulnerability_json: dict[str, str]) -> 'Vulnerability':
        v = Vulnerability()
        v.advisory_url = vulnerability_json['advisoryUrl']
        v.severity = vulnerability_json['severity']
        return v


@dataclass(init=False)
class CatalogEntry:
    url: str
    dependency_groups: list[DependencyGroup]
    name: str
    version: Version
    vulnerabilities: list[Vulnerability]

    @staticmethod
    def create(entryjson: dict[str, Any]) -> 'CatalogEntry':
        ce = CatalogEntry()
        ce.url = entryjson['@id']
        ce.name = entryjson['id']
        ce.version = Version.create(entryjson['version'])

        dgroups: list[DependencyGroup] = []
        if dgjsons := entryjson.get('dependencyGroups'):
            for dgjson in dgjsons:
                dg = DependencyGroup.create(dgjson)
                dgroups.append(dg)
        ce.dependency_groups = dgroups

        vulnerabs: list[Vulnerability] = []
        if vjsons := entryjson.get('vulnerabilities'):
            for vjson in vjsons:
                v = Vulnerability.create(vjson)
                vulnerabs.append(v)
        ce.vulnerabilities = vulnerabs

        return ce


@dataclass(init=False)
class CatalogItem:
    url: str
    type: str
    commit_id: str | None
    commit_timestamp: str | None
    entry: CatalogEntry

    @staticmethod
    def create(catalogitem_json: dict[str, Any]) -> 'CatalogItem':
        ci = CatalogItem()
        ci.url = catalogitem_json['@id']
        ci.type = catalogitem_json['@type']
        ci.commit_id = catalogitem_json.get('commitId')
        ci.commit_timestamp = catalogitem_json.get('commitTimeStamp')
        ci.entry = CatalogEntry.create(catalogitem_json['catalogEntry'])
        return ci


@dataclass(init=False)
class CatalogPage:
    url: str
    commit_id: str | None
    commit_timestamp: str | None
    count: int
    items: list[CatalogItem]
    version_range: VersionRange

    @staticmethod
    def create(catalogpage_json: dict[str, Any]) -> 'CatalogPage':
        cp = CatalogPage()
        cp.url = catalogpage_json['@id']
        cp.commit_id = catalogpage_json.get('commitId')
        cp.commit_timestamp = catalogpage_json.get('commitTimeStamp')
        cp.count = catalogpage_json['count']

        lower = Version.create(catalogpage_json['lower'])
        upper = Version.create(catalogpage_json['upper'])
        cp.version_range = VersionRange(lower, upper)

        items: list[CatalogItem] = []
        for itemjson in catalogpage_json['items']:
            ci = CatalogItem.create(itemjson)
            items.append(ci)
        cp.items = items
        return cp
