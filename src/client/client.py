import argparse
from http.client import HTTPConnection
import json
import random
import time


class Client:

    def __init__(self, p):
        self.p = p
        
    def connect_to_frontend(self, host, port):
        # Setup Connection to front-end service 
        self.h = HTTPConnection(host, port)
    
    def query_request(self, product_name):
        # Send request for 'product_name'
        self.h.request('GET', f"/products/{product_name}")
        response = self.h.getresponse()
        response_json = json.loads(response.read().decode())
        # Error json returned from frontend
        if "error" in response_json.keys():
            print(f"Error {response_json['error']['code']}: {response_json['error']['message']}")
        # Product out of stock, cannot order
        elif response_json['data']['quantity'] == 0:
            print(f'Product {product_name} is out of stock.')
        # Order with probability p
        elif response_json['data']['quantity'] > 0:
            print(f"{product_name} in stock (price:{response_json['data']['price']}, current stock: {response_json['data']['quantity']})")
            if random.uniform(0,1) <= self.p:
                print("Making Order Request")
                self.order_request(product_name, 1)
                # Quantity fixed to 1 here, may be parameterized if needed
                return 1
            else:
                self.h.close()
                return 0


    def order_request(self, product_name, product_quantity):
        # Send HTTP message for order request
        headers = {'Content-type': 'application/json'}
        body = {
            'name': product_name,
            'quantity': product_quantity
            }
        order_json = json.dumps(body)
        self.h.request('POST', '/orders', order_json, headers)
        response = self.h.getresponse()
        response_json = json.loads(response.read().decode())
        if "error" in response_json.keys():
            print(f"Error {response_json['error']['code']}: {response_json['error']['message']}")
        # Print order number from the logs
        else:
            print(f"Order Number: {response_json['data']['order_number']}")
        self.h.close()


    def query_order_request(self, order_number):
        # Send request for 'order_number'
        self.h.request('GET', f"/orders/{order_number}")
        response = self.h.getresponse()
        response_json = json.loads(response.read().decode())
        # Error json returned from frontend
        if "error" in response_json.keys():
            print(f"Error {response_json['error']['code']}: {response_json['error']['message']}")
        else:
            name = response_json['data']['name']
            quantity = response_json['data']['quantity']
            print(f"Order Number: {order_number}, Product Name: {name}, Order Quantity: {quantity}")
        self.h.close()
        #return 0

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--p', '--probability', type=float, default=1.0, help='Probability of query 2')
    parser.add_argument('--t', '--title', default='1984', help='Book Title')
    parser.add_argument('--o', '--order_num', default='-1', help='Order number to query')
    parser.add_argument('--host', default='localhost', help='Server frontend hostname')
    parser.add_argument('--port', type=int, default=12345, help='Server frontend port number')
    parser.add_argument('--lt', default=False, help='Boolean flag to do loadtest')
    args = parser.parse_args()

    # Check for valid probability
    if args.p > 1 or args.p < 0:
        raise Exception('Invalid value of p')

    #  If order number is not -1, query order
    if args.o != '-1':
        client = Client(args.p)
        client.connect_to_frontend(args.host, args.port)
        client.query_order_request(args.o)
        return None

    resp_times = []
    # Send 10 query + (optional) order requests
    for _ in range(10):
        c = Client(args.p)
        c.connect_to_frontend(args.host, args.port)
        start_time = time.time()
        _ = c.query_request(args.t)
        end_time = time.time()
        resp_times.append(end_time - start_time)

    # Test latency if true
    if bool(args.lt) == True:
        print (f"Avg latency = {sum(resp_times)/len(resp_times)}")

if __name__ == '__main__':
    main()