from collections import defaultdict
from concurrent import futures
import json
import pdb
import threading
import logging
import argparse
import requests
from http.client import HTTPConnection

import grpc
import catalog_pb2
import catalog_pb2_grpc

class RepeatTimer(threading.Timer):
    def run(self):
        while not self.finished.wait(self.interval):
            self.function(*self.args, **self.kwargs)

class Catalog(catalog_pb2_grpc.CatalogServicer):
    
    def __init__(self, db_file="data/database.json", frontend_host="localhost", frontend_port="12345"):
        self.db_file = db_file
        self.rw_lock = threading.Lock()
        self.frontend_host = frontend_host
        self.frontend_port = frontend_port
        with open(db_file, 'r') as f:
            data = json.load(f)
        self.data = data
        t = RepeatTimer(10.0, self.restock)
        t.start()

    def send_invalidate(self, product_name):
        # Send HTTP PUT message to frontend
        self.h = HTTPConnection(self.frontend_host, self.frontend_port)
        self.h.request('PUT', f"/invalidate/{product_name}")
        #requests.put(f"http://localhost:{self.frontend_port}/invalidate/{product_name}")

    def restock(self):
        # Restock function that runs on the timer thread
        with self.rw_lock:
            inv_flag = 0
            for item in self.data.keys():
                #print(item)
                if self.data[item]["quantity"] <= 0:
                    self.data[item]["quantity"] = 100
                    # Send cache invalidate message to frontend
                    self.send_invalidate(item)
                    inv_flag = 1
            if inv_flag == 1:
                with open(self.db_file, 'w') as f:
                    json.dump(self.data, f)
            else:
                #print("No Restock")
                pass

    def Query(self, request, context):
        product_name = request.productName
        if product_name in self.data.keys():
            self.rw_lock.acquire()
            productName = product_name
            price = float(self.data[product_name]['price'])
            quantity = int(self.data[product_name]['quantity'])
            self.rw_lock.release()
        else:
            productName = product_name
            price = -1
            quantity = -1
        return catalog_pb2.QueryResponse(productName=productName, price=price, quantity=quantity)

    def Update(self, request, context):
        # Update the database after being called from order service
        product_name = request.productName
        product_quantity = request.quantity
        print("RUNNING UPDATE")
        # Product not available
        if product_name not in self.data.keys():
            resp = -1
        else:
            # Stock over
            if int(self.data[product_name]["quantity"]) == 0:
                resp = 0
            # This can/should never happen
            elif int(self.data[product_name]["quantity"]) < 0:
                raise Exception("Some update error")
            else:
                self.rw_lock.acquire()

                # Updating file
                with open(self.db_file, 'w') as f:
                
                    new_quantity = self.data[product_name]["quantity"] - product_quantity
                    # In case requested quantity is more than available stock
                    if new_quantity < 0:
                        self.rw_lock.release()
                        return catalog_pb2.UpdateResponse(response=-1)

                    self.data[product_name]["quantity"] = new_quantity
                    json.dump(self.data, f)
                
                # Send cache invalidate message to frontend
                print("INVALIDATING CACHE")
                self.send_invalidate(product_name)
                self.rw_lock.release()
                resp = 1
        return catalog_pb2.UpdateResponse(response=resp)


def serve(catalog_service, num_threads, port):
    # Use a threaded server and setup grpc
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=num_threads))
    catalog_pb2_grpc.add_CatalogServicer_to_server(
        catalog_service, server)
    server.add_insecure_port(f"[::]:{port}")
    server.start()
    print("Catalog Service started")
    server.wait_for_termination()


def main():
    # Define database file and synchronization lock
    _DB = 'catalog/data/database.json'

    # Launch service
    parser = argparse.ArgumentParser(description='Catalog Service command line args')
    parser.add_argument("-n", "--num_threads", default=10, help="Size of static thread pool")
    parser.add_argument("-p", "--port", default="50042", help="Server Port")
    parser.add_argument("-fh", "--frontend_host", default="localhost", help="Front-end Host")
    parser.add_argument("-fp", "--frontend_port", default="12345", help="Front-end Port")
    args = parser.parse_args()

    catalog_service = Catalog(_DB, args.frontend_host, args.frontend_port)
    logging.basicConfig()
    serve(catalog_service, int(args.num_threads), args.port)

if __name__ == '__main__':
    main()