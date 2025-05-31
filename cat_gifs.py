import requests
import json

def get_cat():
    x = requests.get('https://cataas.com/cat/gif?position=center&json=true')
    response = x.json()
    return response['url']