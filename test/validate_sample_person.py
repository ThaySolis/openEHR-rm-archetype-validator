import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'output'))

from archetype_validation import validate_archetype_DEMOGRAPHIC_PERSON_person_patient_v0
import json

with open("test/sample_person.json", "r") as f:
    text = f.read()

person = json.loads(text)

if validate_archetype_DEMOGRAPHIC_PERSON_person_patient_v0(person):
    print("O arquivo de exemplo CORRESPONDE ao arquetipo!")
else:
    print("O arquivo de exemplo NAO CORRESPONDE ao arquetipo!")