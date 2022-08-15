# -*- coding: UTF-8 -*-
from os import walk
from os.path import join
import re
from xml.etree import ElementTree
from picocog import PicoWriter
from rm_validation_generator import analyze_types, analyzed_types, escape_type_name

INPUT_FOLDER = "resources/archetypes"
OUTPUT_FOLDER = "output"

# Stores the number of the next artificial node id
next_artificial_node_id = 1
# Stores the names of the available archetype files
available_archetypes = []
# Stores the names of reference model types used in the generated code.
# This is used to generate the imports
used_rm_types = set()

def generate_artificial_node_id():
    '''
    Generates artifical node ids for nodes whose node id is empty.

    Returns:
        An artificial node id.
    '''  
    global next_artificial_node_id
    generated_node_id = "gen" + str(next_artificial_node_id).zfill(4)
    next_artificial_node_id += 1
    return generated_node_id


def find_matching_archetypes(regular_expression):
    '''
    Searches the available archetypes for those that match the regular expression and returns a list with their names.

    Parameters:
        regular_expression - regular expression to match against available archetype names
        
    Returns:
        List containing the archetypes that match the regular expression
    '''    
    list=[]
    for archetype in available_archetypes:
        if re.search(regular_expression, archetype.split(".xml", 1)[0]):
            list.append(str(archetype).split(".xml", 1)[0])
    return list


def list_available_archetype_files():
    '''
    Lists the available archetype files in the INPUT_FOLDER folder and stores them in the available_archetypes variable.
    '''
    global available_archetypes
    for dirpath, dirnames, filenames in walk(INPUT_FOLDER):
        for file in filenames:
            available_archetypes.append(str(file))


def escape_archetype_name(original_name):
    '''
    Escapes an archetype name, replacing "-" and "." by "_"

    Parameters:
        original_name - the name of the archetype to be escaped
                
    Returns:
        Escaped name of the archetype
    '''
    return original_name.split("openEHR-", 1)[1].replace("-","_").replace(".","_")


def escape_node_id(original_value):
    '''
    Escapes a node id, replacing "." by "_"

    Parameters:
        original_value - the value of the node id to be escaped
                
    Returns:
        Escaped value of the node id
    '''
    return original_value.replace(".","_")


def generate_single_attribute_value_validation_code(writer, sub_writer, attribute, value_to_validate):
    '''
    Generates the validation code for the attribute's children when the attribute's type is C_SINGLE_ATTRIBUTE

    Parameters:
        writer: Picocog's writer where the verification code will be generated.
        sub_writer: Picocog's sub_writer where the function that validates the <children> will be generated.
        attribute: the XML <attribute> element.
        value_to_validate: the value which must be verified.
    '''
    condition = ""
    for children in attribute.findall("{http://schemas.openehr.org/v1}children"):
        # Ensures the node_id exists.
        children_node_id_element = children.find("{http://schemas.openehr.org/v1}node_id")
        if children_node_id_element.text is None or children_node_id_element.text == "":
            children_node_id_element.text = generate_artificial_node_id()
        # Generates the children validation function.
        if children.attrib["{http://www.w3.org/2001/XMLSchema-instance}type"]=="C_COMPLEX_OBJECT":
            generate_complex_object_validation_function(sub_writer, children)
        if children.attrib["{http://www.w3.org/2001/XMLSchema-instance}type"]=="ARCHETYPE_SLOT":
            generate_archetype_slot_validation_function(sub_writer, children)
        if children.attrib["{http://www.w3.org/2001/XMLSchema-instance}type"]=="C_CODE_PHRASE":
            generate_code_phrase_validation_function(sub_writer, children)
        if children.attrib["{http://www.w3.org/2001/XMLSchema-instance}type"]=="CONSTRAINT_REF":
            generate_constraint_ref_validation_function(sub_writer, children)
        if children.attrib["{http://www.w3.org/2001/XMLSchema-instance}type"]=="C_PRIMITIVE_OBJECT":
            generate_primitive_object_validation_function(sub_writer, children)   
        children_node_id_name = escape_node_id(children_node_id_element.text)
        if len(condition) > 0:
            condition += " and "
        condition += f"""not validate_{children_node_id_name}({value_to_validate})"""

    writer.writeln(f"""if {condition}:""")
    writer.indent_right()
    writer.writeln("return False")
    writer.indent_left()


def generate_multiple_attribute_value_validation_code(writer, sub_writer, attribute, value_to_validate):
    '''
    Generates the validation code for the attribute's children when the attribute's type is C_MULTIPLE_ATTRIBUTE.

    Parameters:
        writer - the object where the generated code is written to
        sub_writer: Picocog's sub_writer where the function that validates the <children> will be generated.
        attribute: the XML <attribute> element.
        value_to_validate: the value which must be verified.
    '''
    children_node_ids_list=[]
    counter={}
    condition=""
    for children in attribute.findall("{http://schemas.openehr.org/v1}children"):
        children_node_id_element = children.find("{http://schemas.openehr.org/v1}node_id")
        if children_node_id_element.text is None or children_node_id_element.text == "":
            children_node_id_element.text = generate_artificial_node_id()
        # Generates the children validation function.
        if children.attrib["{http://www.w3.org/2001/XMLSchema-instance}type"]=="C_COMPLEX_OBJECT":
            generate_complex_object_validation_function(sub_writer, children)
        if children.attrib["{http://www.w3.org/2001/XMLSchema-instance}type"]=="ARCHETYPE_SLOT":
            generate_archetype_slot_validation_function(sub_writer, children)
        if children.attrib["{http://www.w3.org/2001/XMLSchema-instance}type"]=="C_CODE_PHRASE":
            generate_code_phrase_validation_function(sub_writer, children)
        if children.attrib["{http://www.w3.org/2001/XMLSchema-instance}type"]=="CONSTRAINT_REF":
            generate_constraint_ref_validation_function(sub_writer, children)
        if children.attrib["{http://www.w3.org/2001/XMLSchema-instance}type"]=="C_PRIMITIVE_OBJECT":
            generate_primitive_object_validation_function(sub_writer, children)
        if condition != "":
            condition += " and "
        # Check occurences.
        # Lower
        children_occurrences_lower = children.find("{http://schemas.openehr.org/v1}occurrences").find("{http://schemas.openehr.org/v1}lower").text
       # Upper
        if children.find("{http://schemas.openehr.org/v1}occurrences").find("{http://schemas.openehr.org/v1}upper") in attribute:
            children_occurrences_upper = children.find("{http://schemas.openehr.org/v1}occurrences").find("{http://schemas.openehr.org/v1}upper").text
            condition += f"""{children_occurrences_lower} <= counter["{escape_node_id(children_node_id_element.text)}"] <= {children_occurrences_upper}"""
        # Upper_unbounded    
        else: 
            condition += f"""{children_occurrences_lower} <= counter["{escape_node_id(children_node_id_element.text)}"]"""
           
        children_node_ids_list.append(children_node_id_element)
    for node_id in children_node_ids_list:
        counter[escape_node_id(node_id.text)]=0
    writer.writeln(f"""counter = {counter}""")
    writer.writeln(f"""for item in {value_to_validate}:""")
    writer.indent_right()
    dict_key=0
    for key in counter:
        if dict_key==0:
            writer.writeln(f"""if validate_{key}(item):""")
            dict_key=1
            writer.indent_right()
            writer.writeln(f"""counter["{key}"] += 1""")
            writer.indent_left()
        elif dict_key==1:
            writer.writeln(f"""elif validate_{key}(item):""")
            writer.indent_right()
            writer.writeln(f"""counter["{key}"] += 1""")
            writer.indent_left()
    writer.writeln(f"""else:""")
    writer.indent_right()
    writer.writeln(f"""return False""")
    writer.indent_left()
    writer.indent_left()
    
    writer.writeln(f"""if not({condition}):""")
    writer.indent_right()
    writer.writeln(f"""return False""")
    writer.indent_left()


def generate_primitive_object_validation_function (writer, element):
    '''
    Generates a function (into the 'writer') for C_PRIMITIVE_OBJECT type validation contained in the given XML 'element'

    Parameters:
        writer - the object where the generated code is written to
        element - XML element whose information needs to be validated
    '''
    rm_type_name = escape_type_name(element.find("{http://schemas.openehr.org/v1}rm_type_name").text)
    if rm_type_name == "STRING":
        used_rm_types.add("String")
        node_id_name = escape_node_id(element.find("{http://schemas.openehr.org/v1}node_id").text)
        pattern = element.find("{http://schemas.openehr.org/v1}item").find("{http://schemas.openehr.org/v1}pattern").text
        writer.writeln(f"""def validate_{node_id_name}(obj):""")
        writer.indent_right()
        writer.writeln(f"""if not validate_String(obj):""")
        writer.indent_right()
        writer.writeln(f"""return False""")
        writer.indent_left()
        writer.writeln(f"""import re""")
        writer.writeln(f"""if not re.match('''^{pattern}$''',obj):""")
        writer.indent_right()
        writer.writeln(f"""return False""")
        writer.indent_left()
        writer.writeln(f"""return True""")
        writer.indent_left()

def generate_constraint_ref_validation_function (writer, element):
    '''
    Generates a function (into the 'writer') for CONSTRAINT_REF type validation contained in the given XML 'element'

    Parameters:
        writer - the object where the generated code is written to
        element - XML element whose information needs to be validated
    '''
    rm_type_name = escape_type_name(element.find("{http://schemas.openehr.org/v1}rm_type_name").text)
    used_rm_types.add(rm_type_name)
    node_id_name = escape_node_id(element.find("{http://schemas.openehr.org/v1}node_id").text)
    writer.writeln(f"""def validate_{node_id_name}(obj):""")
    writer.indent_right()
    writer.writeln(f"""if not validate_{rm_type_name}(obj):""")
    writer.indent_right()
    writer.writeln(f"""return False""")
    writer.indent_left()
    writer.writeln(f"""if "terminology_id" not in obj:""")
    writer.indent_right()
    writer.writeln(f"""return False""")
    writer.indent_left()
    writer.writeln(f"""if "code_string" not in obj:""")
    writer.indent_right()
    writer.writeln(f"""return False""")
    writer.indent_left()
    writer.writeln(f"""if obj["terminology_id"]["value"] != "local":""")
    writer.indent_right()
    writer.writeln(f"""return False""")
    writer.indent_left()
    writer.writeln(f"""if obj["code_string"] != "{element.find("{http://schemas.openehr.org/v1}reference").text}":""")
    writer.indent_right()
    writer.writeln(f"""return False""")
    writer.indent_left()
    writer.writeln(f"""return True""")
    writer.indent_left()

def generate_code_phrase_validation_function (writer, element):
    '''
    Generates a function (into the 'writer') for C_CODE_PHRASE type validation contained in the given XML 'element'

    Parameters:
        writer - the object where the generated code is written to
        element - XML element whose information needs to be validated
    '''
    rm_type_name = escape_type_name(element.find("{http://schemas.openehr.org/v1}rm_type_name").text)
    used_rm_types.add(rm_type_name)
    node_id_name = escape_node_id(element.find("{http://schemas.openehr.org/v1}node_id").text)
    writer.writeln(f"""def validate_{node_id_name}(obj):""")
    writer.indent_right()
    writer.writeln(f"""if not validate_{rm_type_name}(obj):""")
    writer.indent_right()
    writer.writeln(f"""return False""")
    writer.indent_left()
    writer.writeln(f"""if "terminology_id" not in obj:""")
    writer.indent_right()
    writer.writeln(f"""return False""")
    writer.indent_left()
    writer.writeln(f"""if "value" not in obj["terminology_id"]:""")
    writer.indent_right()
    writer.writeln(f"""return False""")
    writer.indent_left()
    writer.writeln(f"""if "code_string" not in obj:""")
    writer.indent_right()
    writer.writeln(f"""return False""")
    writer.indent_left()

    writer.writeln(f"""if obj["terminology_id"]["value"] != "{element.find("{http://schemas.openehr.org/v1}terminology_id").find("{http://schemas.openehr.org/v1}value").text}":""")
    writer.indent_right()
    writer.writeln(f"""return False""")
    writer.indent_left()
    code_string_list=[]
    for code_string in element.findall("{http://schemas.openehr.org/v1}code_list"):
        code_string_list.append(code_string.text)
    writer.writeln(f"""if obj["code_string"] not in {code_string_list}:""")
    writer.indent_right()
    writer.writeln(f"""return False""")
    writer.indent_left()
    writer.writeln(f"""return True""")
    writer.indent_left()

def generate_archetype_slot_validation_function(writer, element):
    '''
    Generates a function (into the 'writer') for ARCHETYPE_SLOT type validation contained in the given XML 'element'

    Parameters:
        writer - the object where the generated code is written to
        element - XML element whose information needs to be validated
    '''
    rm_type_name = escape_type_name(element.find("{http://schemas.openehr.org/v1}rm_type_name").text)
    used_rm_types.add(rm_type_name)
    writer.writeln("")
    node_id_name = escape_node_id(element.find("{http://schemas.openehr.org/v1}node_id").text)
    writer.writeln(f"""def validate_{node_id_name}(obj):""")
    writer.indent_right()
    for include in element.findall("{http://schemas.openehr.org/v1}includes"):
        regular_expression=include.find("{http://schemas.openehr.org/v1}expression").find("{http://schemas.openehr.org/v1}right_operand").find("{http://schemas.openehr.org/v1}item").find("{http://schemas.openehr.org/v1}pattern").text
        compatible_archetypes = find_matching_archetypes(regular_expression)    
        
        for archetype_name in compatible_archetypes:
            archetype=escape_archetype_name(archetype_name)
            writer.writeln(f"""if validate_archetype_{archetype}(obj):""")
            writer.indent_right()
            writer.writeln("return True")
            writer.indent_left()
    
    writer.writeln("return False")
    writer.indent_left()


def generate_complex_object_validation_function(writer, element):
    '''
    Generates a function (into the 'writer') for C_COMPLEX_OBJECT type validation contained in the given XML 'element'

    Parameters:
        writer - the object where the generated code is written to
        element - XML element whose information needs to be validated
    '''
    # Creates a deferred writer which will be used for writing the functions that validate subnodes of the archetype
    sub_writer = writer.create_deferred_writer()
    writer.writeln("")
    rm_type_name = escape_type_name(element.find("{http://schemas.openehr.org/v1}rm_type_name").text)
    node_id_name = escape_node_id(element.find("{http://schemas.openehr.org/v1}node_id").text)

    writer.writeln(f"""def validate_{node_id_name}(obj):""")
    writer.indent_right()
    writer.writeln(f"""if not validate_{rm_type_name}(obj):""")
    # Registers that the type rm_type_name has been used.
    # This is used later on to add the imports 
    used_rm_types.add(rm_type_name)
    writer.indent_right()
    writer.writeln("return False")
    writer.indent_left()
    if element.tag != "{http://schemas.openehr.org/v1}definition)":
        if "archetype_node_id" in analyzed_types[rm_type_name]:
            if not node_id_name.startswith("gen"):
                writer.writeln(f"""if obj["archetype_node_id"] != "{node_id_name}":""")
                writer.indent_right()
                writer.writeln("return False")
                writer.indent_left()

    for attribute in element.findall("{http://schemas.openehr.org/v1}attributes"):
        attribute_name = attribute.find("{http://schemas.openehr.org/v1}rm_attribute_name").text
        if attribute.attrib["{http://www.w3.org/2001/XMLSchema-instance}type"]=="C_SINGLE_ATTRIBUTE":
            # Checks if the attribute is optional (lower == 0)
            if (attribute.find("{http://schemas.openehr.org/v1}existence").find("{http://schemas.openehr.org/v1}lower").text=="0"):
                # The attribute is optional
                # validate the attribute if it exists
                writer.writeln(f"""if "{attribute_name}" in obj:""")
                writer.indent_right()
                # If the attribute is a list (according to the reference model)
                if analyzed_types[rm_type_name][attribute_name]["is_array"]:
                    # Checks if the attribute is a list (if not, the validation fails)
                    writer.writeln(f"""if type(obj["{attribute_name}"]) != list:""")
                    writer.indent_right()
                    writer.writeln("return False")
                    writer.indent_left()
                    # Checks if the list has more than one element (since the attribute is "C_SINGLE_ATTRIBUTE", if the list has more than one element, the validation fails)
                    writer.writeln(f"""if len(obj["{attribute_name}"]) > 1:""")
                    writer.indent_right()
                    writer.writeln("return False")
                    writer.indent_left()
                    # Checks if the list has exactly one element, if so checks if it matches the children validation
                    writer.writeln(f"""if len(obj["{attribute_name}"]) == 1:""")
                    writer.indent_right()
                    # Generates the function that validates the children element
                    generate_single_attribute_value_validation_code(writer, sub_writer, attribute, f"""obj["{attribute_name}"][0]""")
                    writer.indent_left()
                # If the attribute is not a list    
                else:
                    # Generates the function that validates the children element
                    generate_single_attribute_value_validation_code(writer, sub_writer, attribute, f"""obj["{attribute_name}"]""")
                writer.indent_left()
            # If the attribute is not optional
            else:
                # If the attribute does not exist, the validation fails
                writer.writeln(f"""if "{attribute_name}" not in obj:""")
                writer.indent_right()
                writer.writeln("return False")
                writer.indent_left()
                # If the attribute is a list (according to the reference model)
                if analyzed_types[rm_type_name][attribute_name]["is_array"]:
                    # If the attribute value is not a list, the validtaion fails
                    writer.writeln(f"""if type(obj["{attribute_name}"]) != list:""")
                    writer.indent_right()
                    writer.writeln("return False")
                    writer.indent_left()
                    # If the list does not have exactly one element, the validation fails (since the attribute is "C_SINGLE_ATTRIBUTE")
                    writer.writeln(f"""if len(obj["{attribute_name}"]) != 1:""")
                    writer.indent_right()
                    writer.writeln("return False")
                    writer.indent_left()
                    # Generates the function that validates the children element
                    generate_single_attribute_value_validation_code(writer, sub_writer, attribute, f"""obj["{attribute_name}"][0]""")
                # If the attribute is not a list 
                else:
                    # Generates the function that validates the children element
                    generate_single_attribute_value_validation_code(writer, sub_writer, attribute, f"""obj["{attribute_name}"]""")
        if attribute.attrib["{http://www.w3.org/2001/XMLSchema-instance}type"]=="C_MULTIPLE_ATTRIBUTE":
            writer.writeln(f"""if "{attribute_name}" not in obj:""")
            writer.indent_right()
            writer.writeln("return False")
            writer.indent_left()
            writer.writeln(f"""if type(obj["{attribute_name}"]) != list:""")
            writer.indent_right()
            writer.writeln("return False")
            writer.indent_left()
            generate_multiple_attribute_value_validation_code(writer, sub_writer, attribute, f"""obj["{attribute_name}"]""")
            
    # When execution reaches this line, it means that no validation has failed
    writer.writeln("return True")
    writer.indent_left()


def generate_archetype_validation_function(writer, archetype):
    '''
    Generates a function (into the 'writer') that validates an archetype

    Parameters:
        writer - the object where the generated code is written to
        archetype - the XML element with the archetype to be validated
    '''
    writer.writeln("")
    definition = archetype.find("{http://schemas.openehr.org/v1}definition")
    node_id_name = escape_node_id(definition.find("{http://schemas.openehr.org/v1}node_id").text)
    archetype_name = archetype.find("{http://schemas.openehr.org/v1}archetype_id").find("{http://schemas.openehr.org/v1}value").text

    writer.writeln(f"""def validate_archetype_{escape_archetype_name(archetype_name)}(obj):""")
    writer.indent_right()
    writer.writeln(f"""'''""")
    writer.writeln(f"""Checks if a given JSON object (Python dict) matches the archetype '{archetype_name}'""")
    writer.writeln("")
    writer.writeln(f"""Parameters:""")
    writer.indent_right()
    writer.writeln(f"""obj - The JSON object to check""")
    writer.writeln("")
    writer.indent_left()
    writer.writeln(f"""Returns:""")
    writer.indent_right()
    writer.writeln(f"""True if the object matches the arquetype, False otherwise.""")
    writer.indent_left()
    writer.writeln(f"""'''""")
    generate_complex_object_validation_function(writer, definition)
    writer.writeln(f"""return validate_{node_id_name}(obj)""")
    writer.indent_left()


def main():
    global used_rm_types
    # Read the metadata of the reference model types into the analyzed types variable
    # This is used to check which attributes are lists or not
    analyze_types()
    # Creates the objetct where the generated code is written to
    writer = PicoWriter()
    # Creates a deferred writer where the imports are written to (after all code is generated)
    imports_writer = writer.create_deferred_writer()
    # Stores the names of all available archetype files
    list_available_archetype_files()
    # For each available archetype file, reads the archetype and generates its validation function
    for item in available_archetypes:
        tree = ElementTree.parse(join(INPUT_FOLDER,item))
        archetype = tree.getroot()
        generate_archetype_validation_function(writer, archetype)
    # Generates the UTF-8 marker
    imports_writer.writeln(f"""# -*- coding: UTF-8 -*-""")
    # Generates the imports on top of the generated code    
    for rm_type in used_rm_types:
        imports_writer.writeln(f"""from .rm_validation import validate_{rm_type}""")
    # Saves the generated code to the $OUTPUT_FOLDER/archetype_validation.py file
    code = str(writer)
    with open(join(OUTPUT_FOLDER,"archetype_validation.py"), "w", encoding="utf-8") as o:
        o.write(code)

if __name__ == '__main__':
    main()




