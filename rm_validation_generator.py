# -*- coding: utf-8 -*-

from os import listdir
from os.path import isfile, join
import json
from picocog import PicoWriter

INPUT_FOLDER = "resources/json_schema"
OUTPUT_FOLDER = "output"

# A dictionary where:
    # each key is a reference model type name.
    # each value is another dictionary where 
        # each key is an attribute of the type
        # each value is a dictionary with the following keys:
            # required: True if the attribute is required, False otherwise
            # type: The reference model type name of the attribute values
            # is_array: True if the attribute is an array, False otherwise
            # values (only if the type is 'enum'): the list of values that the attribute may have
analyzed_types = {}

# A list containing all the reference model type names of the types which are abstract
abstract_types = []

def escape_type_name(original_type_name):
    '''
    Escapes a type name, replacing "<" by "_of_" and ">" by ""

    Parameters:
        original_type_name - the name of the type to be escaped
                
    Returns:
        Escaped name of the type
    '''
    return str(original_type_name).replace("<", "_of_").replace(">","")


def analyze_types():
    '''
    Reads all the files in the INPUT_FOLDER folder and analyzes then, storing the results in the analyzed_types variable
    '''
    file_list=[f for f in listdir(INPUT_FOLDER) if isfile(join(INPUT_FOLDER, f))]
    for file_name in file_list:
        with open(join(INPUT_FOLDER, file_name), 'r', encoding='utf8') as file:
            plaintext_json = file.read()
        object = json.loads(plaintext_json)
        analyze_type(object)

def analyze_type(object):
    '''
    Processes a parsed JSON file (Python dict) representing a type and stores its metadata in the analyzed_types variable

    Parameters:
        object - the parsed JSON file representing the type
    '''
    global analyzed_types
    global abstract_types
    type_name = object['title']
    type_name=escape_type_name(type_name)
    if '$abstract' in object and object['$abstract']==True:
        abstract_types.append(type_name)
    analyzed_types[type_name]={}
    properties = object['properties']
    required = object['required'] if 'required' in object else []

    for property_name in properties:
        analyzed_types[type_name][property_name]={}
        if property_name in required:
            analyzed_types[type_name][property_name]['required']=True
        else:
            analyzed_types[type_name][property_name]['required']=False
        property = properties[property_name]
        if '$ref' in property:
            analyzed_types[type_name][property_name]['type']=property['$ref'].split('/')[-1]
            analyzed_types[type_name][property_name]['is_array']=False
        elif 'items' in property:
            analyzed_types[type_name][property_name]['type']=property['items']['$ref'].split('/')[-1]
            analyzed_types[type_name][property_name]['is_array']=True
        elif 'enum' in property:
            analyzed_types[type_name][property_name]['type']='enum'
            analyzed_types[type_name][property_name]['values']=property['enum']
            analyzed_types[type_name][property_name]['is_array']=False
        else:
            raise(Exception("Erro"))

def print_analyzed_types():
    '''
    Prints the data in the analyzed_types variable for debugging purposes
    '''
    for type_name in analyzed_types:
        print(str(type_name) + ": {")
        for property in analyzed_types[type_name]:
            print("\t" + property + ": {\n")
            for key in analyzed_types[type_name][property]:
                print("\t\t" + str(key) + ": " + str(analyzed_types[type_name][property][key]))
            print("\t}")
    print("}\n")

def create_validate_type(writer, type_name):
    '''
    Generates a function (into the 'writer') for validating the given type

    Parameters:
        writer - the object where the generated code is written to
        type_name - the name of the type whose code will be generated (the type must exist in the analyzed_types variable)
    '''
    parameter_name = str(type_name).lower()
    writer.writeln(f"def validate_{type_name}({parameter_name}):")
    writer.indent_right()
    for property_name in analyzed_types[type_name]:
        property = analyzed_types[type_name][property_name]
        if property['required'] == True:
            writer.writeln(f"if '{property_name}' not in {parameter_name}:")
            writer.indent_right()
            writer.writeln("return False")
            writer.indent_left()
            if property['type']!="T":
                if property['type']=="enum":
                    writer.writeln(f"if " + parameter_name + "['" + property_name + "'] not in ['" + "','".join(property['values']) +"']:")
                    writer.indent_right()
                    writer.writeln("return False")
                    writer.indent_left()
                elif property['is_array'] == False:
                    writer.writeln(f"if not validate_{property['type']}({parameter_name}['{property_name}']):")
                    writer.indent_right()
                    writer.writeln("return False")
                    writer.indent_left()
                else:
                    writer.writeln(f"if type(" + parameter_name + "['" + property_name + "']) != list:")
                    writer.indent_right()
                    writer.writeln("return False")
                    writer.indent_left()
                    writer.writeln(f"if len(" + parameter_name + "['" + property_name + "']) == 0:")
                    writer.indent_right()
                    writer.writeln("return False")
                    writer.indent_left()
                    writer.writeln(f"for element in {parameter_name}['{property_name}']:")
                    writer.indent_right()
                    writer.writeln(f"if not validate_{property['type']}(element):")
                    writer.indent_right()
                    writer.writeln("return False")
                    writer.indent_left()
                    writer.indent_left()
        else:
            if property['type']!="T":
                if property['type']=="enum":
                    writer.writeln(f"if '{property_name}' in {parameter_name}:")
                    writer.indent_right()
                    writer.writeln(f"if " + parameter_name + "['" + property_name + "'] not in ['" + "','".join(property['values']) +"']:")
                    writer.indent_right()
                    writer.writeln("return False")
                    writer.indent_left()
                    writer.indent_left()
                elif property['is_array'] == False:
                    writer.writeln(f"if '{property_name}' in {parameter_name}:")
                    writer.indent_right()
                    writer.writeln(f"if not validate_{property['type']}({parameter_name}['{property_name}']):")
                    writer.indent_right()
                    writer.writeln("return False")
                    writer.indent_left()
                    writer.indent_left()
                else:
                    writer.writeln(f"if '{property_name}' in {parameter_name}:")
                    writer.indent_right()
                    writer.writeln(f"if type(" + parameter_name + "['" + property_name + "']) != list:")
                    writer.indent_right()
                    writer.writeln("return False")
                    writer.indent_left()
                    writer.writeln(f"for element in {parameter_name}['{property_name}']:")
                    writer.indent_right()
                    writer.writeln(f"if not validate_{property['type']}(element):")
                    writer.indent_right()
                    writer.writeln("return False")
                    writer.indent_left()
                    writer.indent_left()
                    writer.indent_left()
    if type_name in abstract_types:
        for concrete_type_name in analyzed_types[type_name]["_type"]["values"]:
            type_value=concrete_type_name
            concrete_type_name=escape_type_name(concrete_type_name)
            writer.writeln(f"if {parameter_name}['_type']=='{type_value}':")
            writer.indent_right()
            writer.writeln(f"if not validate_{concrete_type_name}({parameter_name}):")
            writer.indent_right()
            writer.writeln("return False")
            writer.indent_left()
            writer.indent_left()
    writer.writeln("return True")
    writer.indent_left()

def create_validate_String(writer):
    '''
    Generates a function (into the 'writer') for validating the String type.

    Parameters:
        writer - the object where the generated code is written to
    '''
    writer.writeln("def validate_String(parameter):")
    writer.indent_right()
    writer.writeln("return type(parameter) == str")
    writer.indent_left()

def create_validate_Character(writer):
    '''
    Generates a function (into the 'writer') for validating the Character type.

    Parameters:
        writer - the object where the generated code is written to
    '''
    writer.writeln("def validate_Character(parameter):")
    writer.indent_right()
    writer.writeln("return type(parameter)==str and len(parameter)==1")
    writer.indent_left()
    
def create_validate_Boolean(writer):
    '''
    Generates a function (into the 'writer') for validating the Boolean type.

    Parameters:
        writer - the object where the generated code is written to
    '''
    writer.writeln("def validate_Boolean(parameter):")
    writer.indent_right()
    writer.writeln("return type(parameter)==bool")
    writer.indent_left()

def create_validate_Double(writer):
    '''
    Generates a function (into the 'writer') for validating the Double type.

    Parameters:
        writer - the object where the generated code is written to
    '''
    writer.writeln("def validate_Double(parameter):")
    writer.indent_right()
    writer.writeln("return type(parameter)==float or type(parameter)==int")
    writer.indent_left()

def create_validate_Real(writer):
    '''
    Generates a function (into the 'writer') for validating the Real type.

    Parameters:
        writer - the object where the generated code is written to
    '''
    writer.writeln("def validate_Real(parameter):")
    writer.indent_right()
    writer.writeln("return type(parameter)==float or type(parameter)==int")
    writer.indent_left()

def create_validate_Integer(writer):
    '''
    Generates a function (into the 'writer') for validating the Integer type.

    Parameters:
        writer - the object where the generated code is written to
    '''
    writer.writeln("def validate_Integer(parameter):")
    writer.indent_right()
    writer.writeln("return type(parameter)==int")
    writer.indent_left()

def create_validate_Integer64(writer):
    '''
    Generates a function (into the 'writer') for validating the Integer64 type.

    Parameters:
        writer - the object where the generated code is written to
    '''
    writer.writeln("def validate_Integer64(parameter):")
    writer.indent_right()
    writer.writeln("return type(parameter)==int")
    writer.indent_left()

def create_code(writer):
    '''
    Generates the whole validation code (into the 'writer') including all basic types as well as the types in the analyzed_types variable

    Parameters:
        writer - the object where the generated code is written to
    '''
    for type_name in analyzed_types:
        create_validate_type(writer, type_name)

    create_validate_String(writer)
    create_validate_Character(writer)
    create_validate_Boolean(writer)
    create_validate_Double(writer)
    create_validate_Integer(writer)
    create_validate_Integer64(writer)
    create_validate_Real(writer)

def main():
    analyze_types()

    writer = PicoWriter()
    # Generates the UTF-8 marker
    writer.writeln(f"""# -*- coding: UTF-8 -*-""")
    create_code(writer)
    code = str(writer)
    with open(join(OUTPUT_FOLDER, "rm_validation.py"), "w", encoding="utf-8") as file_output:
        file_output.write(code)

if __name__ == '__main__':
    main()
