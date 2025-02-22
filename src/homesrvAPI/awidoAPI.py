#!/usr/bin/python
"""
awidoAPI
(c) 2024 by Christian Rödel 
"""

import requests
import csv
import locale
from io import StringIO
from datetime import datetime, timedelta
import logging
from homesrv.config import cfg

#================================================
class awidoAPI:
    base_url = "https://awido.cubefour.de/"
    all_waste_types = [
        "Bioabfall",
        "Restmülltonne 40-240 L",
        "Papiertonne 4-wöchentlich",
        "Wertstofftonne 80-1100 L",
        "Papiercontainer 2-wöchentlich",
        "Restmüllcontainer 660-1100 L",
        "Problemmüll"
    ]

    #-----------------------------------
    def __init__(self):
        self.awido_data = []
        self.refresh_date = None
        self.region = cfg.get("awido_region")
        self.oid = cfg.get("awido_oid")
        self.waste_types = cfg.get("awido_waste_types")
        self.title = cfg.get("awido_title", "home")
        locale.setlocale(locale.LC_ALL, "")

    #-----------------------------------
    def set_location(self, region, oid, title=None):
        self.region = region
        self.oid = oid
        if title:
            self.title = title

    #-----------------------------------
    def set_waste_types(self, waste_types):
        self.waste_types = waste_types

    #-----------------------------------
    def all_collections(self): 
        self._refresh_awido_data()
        now = datetime.now()

        collections = []
        for collection in self.awido_data:
            if not self.waste_types or collection["waste_type"] in self.waste_types: # add future rows with matching waste_type 
                item = collection.copy()
                item["date"] = item["date"].strftime("%a %d.%m.%Y")
                collections.append(item)
        return collections    

    #-----------------------------------
    def upcoming_collections(self): 
        self._refresh_awido_data()
        now = datetime.now()
        today = now - timedelta(hours=now.hour, minutes=now.minute, seconds=now.second, microseconds=now.microsecond) # round to day
        
        collections = []
        for collection in self.awido_data:
            if collection["date"] >= today and collection["date"] - now < timedelta(days=cfg["awido_recent_days"]) and (not self.waste_types or collection["waste_type"] in self.waste_types): 
                # add future rows with matching waste_type 
                item = collection.copy()
                item["date"] = item["date"].strftime("%a %d.%m.%Y")
                collections.append(item)
        return collections    

    #-----------------------------------
    def current_collections(self): 
        self._refresh_awido_data()
        now = datetime.now()
        today = now - timedelta(hours=now.hour, minutes=now.minute, seconds=now.second, microseconds=now.microsecond) # round to day
        
        collections = []
        for collection in self.awido_data:
            if collection["date"] >= today and collection["date"] - now < timedelta(hours=18) and (not self.waste_types or collection["waste_type"] in self.waste_types): 
                # add future rows with matching waste_type 
                item = collection.copy()
                if item["date"] <= datetime.now():
                    item["date"] = "heute"
                else:
                    item["date"] = "morgen"
                collections.append(item)
        return collections    

    #-----------------------------------
    def _refresh_awido_data(self):
        if not self.region or not self.oid:
            logging.error( "Location is not set. Please set a location before you retrieve data." )
            return
        
        now = datetime.now()
        if not self.refresh_date or self.refresh_date < now-timedelta(hours=1): 
            logging.info("Refreshing awido info")
            self.awido_data.clear()           
            years = [now.year]
            if now.month >= 11: # Starting in Nov -> retrieve data for next year
                years.append(now.year+1) 
            
            for year in years:
                url = "Customer/{}/KalenderCSV.aspx?oid={}&jahr={}&fraktionen=".format(self.region, self.oid, year)    
                data_orig = self._do_API_call( url )
                if data_orig:
                    self.current_data = []
                    string_io = StringIO(data_orig.content.decode('ISO-8859-1'))
                    data = csv.DictReader(string_io)
                    for row in data:
                        item={}
                        item["location"] = row["ORT"]
                        item["district"] = row["ORTSTEIL"]
                        item["site"] = row["STANDORT"]
                        item["waste_type"] = row["FRAKTION"]
                        item["date"] = datetime.strptime(row["TERMIN"][3:], "%d.%m.%Y")    
                        self.awido_data.append(item)
                    self.refresh_date = now    
                else:
                    logging.error( "Couldn't refresh awido data for {}".format(year) )

    #-----------------------------------
    def retrieve_places(self, region):
        url = "WebServices/Awido.Service.svc/getPlaces/client={}".format(region)
        data = self._do_API_call( url )
        if data:
            places = {}
            for row in data.json():
                places[row["value"]] = row["key"]
            return places    
        else:
            logging.error("Couldn't retrieve places")
            return None

    #-----------------------------------
    def retrieve_streets(self, region, place_key):
        url = "WebServices/Awido.Service.svc/getGroupedStreets/{}?client={}".format(place_key, region)
        data = self._do_API_call( url )
        if data:            
            streets = {}
            for row in data.json():
                streets[row["value"]] = row["key"]
            return streets    
        else:
            logging.error("Couldn't retrieve streets")
            return None

    #-----------------------------------
    def retrieve_street_parts(self, region, street_key):
        url = "WebServices/Awido.Service.svc/getStreetAddons/{}?client={}".format(street_key, region)
        data = self._do_API_call( url )
        if data:
            street_parts = {}
            for row in data.json():
                street_parts[row["value"]] = row["key"]
            return street_parts    
        else:
            logging.error("Couldn't retrieve street parts")
            return None            
        
    #---------------------------
    def _do_API_call( self, url ):
        url = self.base_url + url
        try:
            response = requests.get(url, timeout=5)
        except requests.exceptions.RequestException as err:
            logging.error( "Couldn't request awido API: {} Exception {:s}".format(url, str(err)) )
        else:
            if response.status_code == 200:
                return response
            else:
                logging.error( "Error while requesting awido API: {:s} -> {:d} {:s}".format( url, response.status_code, response.reason) )
        return None  

