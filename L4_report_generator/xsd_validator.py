"""
L4: lxml XSD Validator

Validates the generated XML against the official FIU-IND XSD schema.
"""
from lxml import etree
from config import get_config

config = get_config()

def get_xsd_schema():
    """
    Loads the XSD schema from blob storage.
    """
    # TODO: Implement logic to download/cache the XSD schema from Azure Blob Storage
    # For now, we'll assume it's a local file.
    with open('L4_report_generator/schemas/fiu_ind_schema.xsd', 'rb') as f:
        schema_root = etree.XML(f.read())
    return etree.XMLSchema(schema_root)

def validate_xml(xml_content):
    """
    Validates the XML content against the schema.
    """
    schema = get_xsd_schema()
    xml_parser = etree.XMLParser(schema=schema)
    try:
        etree.fromstring(xml_content.encode('utf-8'), xml_parser)
        return True, None
    except etree.XMLSyntaxError as e:
        return False, str(e)
