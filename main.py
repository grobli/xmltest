import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from multiprocessing.pool import ThreadPool

from nuget.models.metadata import Dependency, VersionRange, Version
from nuget.nugetclient import NugetClient


class Consts:
    class XML:
        class Attributes:
            INCLUDE = 'Include'
            VERSION = 'Version'
            VERSION_OVERRIDE = 'VersionOverride'

        class Elements:
            PACKAGE_REFERENCE = 'PackageReference'
            PROPERTY_GROUP = 'PropertyGroup'
            ITEM_GROUP = 'ItemGroup'
            PROJECT = 'Project'


@dataclass(init=False)
class PackageReference:
    xml: ET.Element = field(repr=False)
    root: ET.Element = field(repr=False)
    name: str
    vendor: str
    version: str | None
    version_override: str | None

    @property
    def name(self) -> str:
        return self.xml.get(Consts.XML.Attributes.INCLUDE)

    @property
    def version(self) -> str:
        return self.xml.get(Consts.XML.Attributes.VERSION)

    @version.setter
    def version(self, value: str | None) -> None:
        VERSION = Consts.XML.Attributes.VERSION

        if value and not self.version_override:
            self.xml.set(VERSION, value)
            return

        if not value and VERSION in self.xml.attrib:
            del self.xml.attrib[VERSION]

    @property
    def version_override(self) -> str | None:
        return self.xml.get(Consts.XML.Attributes.VERSION_OVERRIDE)

    @version_override.setter
    def version_override(self, value: str | None) -> None:
        VERSION = Consts.XML.Attributes.VERSION
        VERSION_OVERRIDE = Consts.XML.Attributes.VERSION_OVERRIDE

        if isinstance(value, property):
            return

        if VERSION_OVERRIDE in self.xml.attrib and not value:
            del self.xml.attrib[VERSION_OVERRIDE]
            return

        if value:
            self.xml.set(VERSION_OVERRIDE, value)
            if VERSION in self.xml.attrib:
                del self.xml.attrib[VERSION]

    @property
    def vendor(self) -> str:
        vendor = self.name.split('.')[0]
        vendor = f'{vendor[0].upper()}{vendor[1:]}'
        return vendor

    @staticmethod
    def create(element: ET.Element, item_group: ET.Element) -> 'PackageReference':
        pref = PackageReference()
        pref.root = item_group
        pref.xml = element
        pref.version = element.get(Consts.XML.Attributes.VERSION)
        return pref

    def __del__(self):
        self.root.remove(self.xml)


def get_package_references(csproj_filepath: str) -> list[PackageReference]:
    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
    tree = ET.parse(csproj_filepath, parser=parser)
    root = tree.getroot()

    XPATH = f'./{Consts.XML.Elements.ITEM_GROUP}[{
        Consts.XML.Elements.PACKAGE_REFERENCE}]'

    prefs: list[PackageReference] = []
    itemgroups = root.findall(XPATH)
    for ig in itemgroups:
        for elem in ig.iter():
            if elem.tag == Consts.XML.Elements.PACKAGE_REFERENCE:
                pref = PackageReference.create(elem, ig)
                prefs.append(pref)
    return prefs


def test_pref():
    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))

    tree = ET.parse('test.xml', parser=parser)

    root = tree.getroot()

    XPATH = f'./{Consts.XML.Elements.ITEM_GROUP}[{
        Consts.XML.Elements.PACKAGE_REFERENCE}]'

    elems = root.findall(XPATH)

    pref = PackageReference.create(list(elems[0].iter())[2], elems[0])

    print(pref)

    print(ET.tostring(root, encoding='unicode'), '\n\n')

    pref.version_override = '2.0'

    print(pref)
    print(ET.tostring(root, encoding='unicode'), '\n\n')

    pref.version_override = None

    print(pref)
    print(ET.tostring(root, encoding='unicode'), '\n\n')

    pref.version = None

    print(pref)
    print(ET.tostring(root, encoding='unicode'), '\n\n')

    pref.version = '3.2'

    print(pref)
    print(ET.tostring(root, encoding='unicode'), '\n\n')

    del pref

    print(ET.tostring(root, encoding='unicode'), '\n\n')
    print(pref)


if __name__ == '__main__':
    prefs = get_package_references('test.xml')

    client = NugetClient()

    with ThreadPool() as pool:
        args = ((pref.name, pref.version) for pref in prefs)
        async_result = pool.starmap_async(client.get_metadata, args)
        results = async_result.get()

    grouped_deps: dict[str, list[tuple[str, str]]] = {}
    for result in results:

        # print(result.entry.name, 'dependecies:', '\n')
        metadata = result
        if metadata:
            deps = []
            depgroup = [
                dg for dg in metadata.entry.dependency_groups if 'netstandard2.' in dg.target_framework or 'net5.0' in dg.target_framework][0]
            for dep in depgroup.dependencies:
                if not dep.name in grouped_deps:
                    grouped_deps[dep.name] = []
                grouped_deps[dep.name].append(
                    (f'{dep.name} {dep.range}', metadata.entry.name))

                deps.append(dep)
                # print(dep.name, dep.range, depgroup.target_framework)

        # print('____________________________________________________')

    for key in grouped_deps.keys():
        print(key, ':')
        for item in grouped_deps[key]:
            print(item)
        print('___________________________________')

    depnames = [k.lower() for k in grouped_deps.keys()]
    metapackages = [pref for pref in prefs if pref.name.lower()
                    not in depnames]

    print()
    print('META PACKAGES:')
    for mp in sorted(metapackages, key=lambda pf: pf.name):
        print(mp.name)

    print()

    impostors = [pref for pref in prefs if pref.name.lower() in depnames]
    print('IMPOSTOR PACKAGES:')
    for imp in sorted(impostors, key=lambda pf: pf.name):
        print(imp.name)

    print()

    print('TRANSITIVE PACKAGES')
    for transitive in sorted(depnames):
        print(transitive)

    vrange1 = VersionRange.from_rangestring('(5.0.13, 5.0.16]')
    vrange2 = VersionRange.from_rangestring('(5.0.11, 5.0.14]')

    print(vrange1.common_minimum_version(vrange2))
