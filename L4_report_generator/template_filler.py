"""
L4: Jinja2 Template Filler

Populates the goAML XML template from case state fields.
"""
from jinja2 import Environment, FileSystemLoader

def populate_template(case_data):
    """
    Fills the goAML XML template with data from the case.
    """
    env = Environment(loader=FileSystemLoader('L4_report_generator/templates'))
    template = env.get_template('goaml_template.xml')
    return template.render(case=case_data)
