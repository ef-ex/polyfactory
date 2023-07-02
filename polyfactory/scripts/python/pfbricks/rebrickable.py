import csv, json
import os
import re

from polyfactory import utils as pfUtils

RBLIB = '{}/library/rebrickable'.format(os.getenv('POLYFACTORY'))

def get_category_id(cat):
    with open(f'{RBLIB}/part_categories.csv') as csvFile:
        reader = csv.DictReader(csvFile)
        for row in reader:
            if cat == row['name']:
                return row['id']
    return None


def get_parts(cat):
    catID = get_category_id(cat)
    parts = {}
    with open(f'{RBLIB}/parts.csv') as csvFile:
        reader = csv.DictReader(csvFile)
        for row in reader:
            if row['part_cat_id'] == catID:
                result = re.search(r'^([0-9]*)(.*)', row['part_num'])
                pID = result.group(1)
                pVariant = result.group(2)

                if not pID in parts:
                    parts[pID] = {'variants':{}}

                if pVariant:
                    parts[pID]['variants'][row['part_num']] = row['name']
                else:
                    parts[pID]['name'] = row['name']    
    return parts


def get_brickdimensions(name):
    name = name.lower()
    regex = r'^(.*)(.[0-9]* x .[0-9]* x .[0-9]*|.[0-9]* x .[0-9]*)(.*)'
    result = re.search(regex, name)
    return pfUtils.unpack(result.group(2).split(' x '), 3, 1)


def get_tiledimensions(name):
    name = name.lower()
    regex = r'^([a-zA-Z ]*)(.[0-9]* x .[0-9]*)(.*)'
    result = re.search(regex, name)
    return pfUtils.unpack(result.group(2).split(' x '), 2, 1)