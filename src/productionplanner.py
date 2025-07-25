"""Functions related to handling data from the production planner"""

import re


def remove_friends_night_tag(act_name: str):
    """Removes any tag indicating a "Vriendenavond" (Friends Night) production from an act name"""
    return re.sub(r" *[@[\(] *vrienden *(avond)*[]\)]*$", "", act_name, 1, flags=re.IGNORECASE)
