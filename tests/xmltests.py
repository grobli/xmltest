import xml.etree.ElementTree as ET
import unittest

from nuget.xml import Consts, PackageReference

# TODO - write real tests...

class TestXmlMethods(unittest.TestCase):
    def test_pref(self):
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
        
