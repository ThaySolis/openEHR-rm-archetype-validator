import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'output'))

from rm_validation import validate_PERSON

print(validate_PERSON({
    "name": {
        "_type": "DV_TEXT",
        "value": "Nome"
    },
    "archetype_node_id": "at0000.1",
    "identities": [],
    "contacts": [],
    "details": {
        "_type": "ITEM_TREE",
        "name": {
            "_type": "DV_TEXT",
            "value": "Nome"
        },
        "archetype_node_id": "at0000"
    }
}))