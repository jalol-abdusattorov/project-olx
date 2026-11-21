import os
from dotenv import find_dotenv, load_dotenv
from pymongo import MongoClient


dotenv_path = find_dotenv()
load_dotenv(dotenv_path)

MONGO_URI = os.getenv('MONGO_URI')

client = MongoClient(MONGO_URI)
db = client.olx

users_collection = db.users
categories_collection = db.categories
subcategories_collection = db.subcategories
listings_collection = db.listings
reviews_collection = db.reviews
attributes_collection = db.attributes
filters_collection = db.filters