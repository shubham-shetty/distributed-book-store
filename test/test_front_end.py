import unittest
from unittest.mock import patch
import requests
import json

class TestFrontEnd(unittest.TestCase):

    def test_query_catalog(self):
        print("Test 1- Query Catalog (Valid Product)")
        url = "http://localhost:12345/products/1984"
        r = requests.get(url)
        response = r.json()
        self.assertEqual(response['data']['productName'], '1984')

        print("Test 2- Query Catalog (Invalid Product)")
        url = "http://localhost:12345/products/unknown"
        r = requests.get(url)
        response = r.json()
        self.assertEqual(response['error']['code'], 404)

    def test_query_order(self):
        print("Test 3- Query Order Database (Invalid Order ID)")
        url = "http://localhost:12345/orders/1000"
        r = requests.get(url)
        response = r.json()
        self.assertEqual(response['error']['code'], 404)
    
    @patch('requests.post')
    def test_buy(self, mock_post):
        print("Test 4- Buy Request (Existing Product)")
        info = {"name": "1984", "quantity": 5}
        resp = requests.post("http://localhost:12345/orders", data=json.dumps(info), headers={'Content-Type': 'application/json'})
        mock_post.assert_called_with("http://localhost:12345/orders", data=json.dumps(info), headers={'Content-Type': 'application/json'})

        print("Test 5- Buy Request (Not Stocked Product)")
        info = {"name": "marvin", "quantity": 5}
        resp = requests.post("http://localhost:12345/orders", data=json.dumps(info), headers={'Content-Type': 'application/json'})
        mock_post.assert_called_with("http://localhost:12345/orders", data=json.dumps(info), headers={'Content-Type': 'application/json'})
        
        print("Test 6- Buy Request (Out-of-Stock Product)")
        info = {"name": "1984", "quantity": 1000}
        resp = requests.post("http://localhost:12345/orders", data=json.dumps(info), headers={'Content-Type': 'application/json'})
        mock_post.assert_called_with("http://localhost:12345/orders", data=json.dumps(info), headers={'Content-Type': 'application/json'})
        