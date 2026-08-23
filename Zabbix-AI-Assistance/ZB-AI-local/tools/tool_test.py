from elasticsearch import Elasticsearch
from config.settings import ES_URL, ES_API_KEY, ES_INDEX

es = Elasticsearch(ES_URL, api_key=ES_API_KEY) if ES_API_KEY else Elasticsearch(ES_URL)