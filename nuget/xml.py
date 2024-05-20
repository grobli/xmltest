import xml.etree.ElementTree as ET
from dataclasses import dataclass, field


class Consts:
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
        return self.xml.get(Consts.Attributes.INCLUDE)

    @property
    def version(self) -> str:
        return self.xml.get(Consts.Attributes.VERSION)

    @version.setter
    def version(self, value: str | None) -> None:
        VERSION = Consts.Attributes.VERSION

        if value and not self.version_override:
            self.xml.set(VERSION, value)
            return

        if not value and VERSION in self.xml.attrib:
            del self.xml.attrib[VERSION]

    @property
    def version_override(self) -> str | None:
        return self.xml.get(Consts.Attributes.VERSION_OVERRIDE)

    @version_override.setter
    def version_override(self, value: str | None) -> None:
        VERSION = Consts.Attributes.VERSION
        VERSION_OVERRIDE = Consts.Attributes.VERSION_OVERRIDE

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
        pref.version = element.get(Consts.Attributes.VERSION)
        return pref

    def __del__(self):
        self.root.remove(self.xml)


def get_package_references(csproj_filepath: str) -> list[PackageReference]:
    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
    tree = ET.parse(csproj_filepath, parser=parser)
    root = tree.getroot()

    XPATH = f'./{Consts.Elements.ITEM_GROUP}[{
        Consts.Elements.PACKAGE_REFERENCE}]'

    prefs: list[PackageReference] = []
    itemgroups = root.findall(XPATH)
    for ig in itemgroups:
        for elem in ig.iter():
            if elem.tag == Consts.Elements.PACKAGE_REFERENCE:
                pref = PackageReference.create(elem, ig)
                prefs.append(pref)
    return prefs
