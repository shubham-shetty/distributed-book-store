from collections import defaultdict
from concurrent import futures
import json
import threading
import logging
import argparse, configparser
import os
import random
from time import sleep

import grpc
import order_pb2
import order_pb2_grpc
import catalog_pb2
import catalog_pb2_grpc


class Order(order_pb2_grpc.OrderServicer):
    
    def __init__(self, db_file="data/order_database.json", cat_host="localhost", cat_port="50042", order_service_addrs=['localhost:50043', 'localhost:50044', 'localhost:50045']):
        self.db_file = db_file
        self.rw_lock = threading.Lock()
        self.cat_host = cat_host
        self.cat_port = cat_port
        self.order_service_addrs = order_service_addrs
        # Init in-memory
        with open(db_file, 'r') as f:
            data = json.load(f)
        self.data = data
        if len(self.data) == 0:
            self.count = 0
        else:
            curr_orders = [int(i) for i in self.data.keys()]
            self.count = max(curr_orders)

        # Sync on Init
        sleep(1)
        sync_replica = random.choice(self.order_service_addrs)
        print(f"Syncing with {sync_replica} and order_num:{self.count}")
        self.do_sync(sync_replica, self.count)


    def do_sync(self, sync_replica, order_num, prod_name=None, prod_qty=None):
        # Synchronize with other replicas on recovery and startup
        with grpc.insecure_channel(sync_replica) as channel:
            sync_stub = order_pb2_grpc.OrderStub(channel)
            sync_result = self.request_sync(sync_stub, str(order_num), prod_name, prod_qty)
            print(sync_result)
            try:
                for result in sync_result:
                    if result.response == "0":
                        # Init or In Sync
                        print("In Sync")
                    elif result.response == "1":
                        self.data[result.orderNumber] = {
                            "product": result.productName,
                            "quantity": result.productQty
                        }
                        self.count += 1
                        with open(self.db_file, 'w') as f:
                            json.dump(self.data, f)
                    elif result.response == "-1":
                        print("Non-Leader?")
                        pass
            except:
                print("Initial Server Synced")
    
    def request_sync(self, stub, orderNum, prodName=None, prodQty=None):
        # Sync request to other replicas
        syncRequest = order_pb2.SyncRequest(orderNumber=orderNum, productName=prodName,\
                                            productQty=prodQty)
        syncResponse = stub.Sync(syncRequest)
        return syncResponse

    def Sync(self, request, context):
        # Receives a sync request and checks with DB
        remote_max_order_num = int(request.orderNumber)
        remote_prod_name = request.productName
        remote_prod_qty = request.productQty
        if self.count > remote_max_order_num:
            # Need to back sync
            print("Back syncing servers")
            for order_num in range(remote_max_order_num+1, self.count+1):
                print(f"Back Sync Order Number: {order_num}")
                with open(self.db_file, 'r') as f:
                    log = json.load(f)
                prod_name = log[str(order_num)]["product"]
                prod_qty = log[str(order_num)]["quantity"]
                yield order_pb2.SyncResponse(response="1", orderNumber=str(order_num), \
                                            productName=prod_name, productQty=prod_qty)
        elif self.count == remote_max_order_num:
            # Already synced
            print("Already in sync")
            return order_pb2.SyncResponse(response="0")
        else:
            # Sync this server 
            print(f"Non-leaders committing {remote_max_order_num}:{remote_prod_name},{remote_prod_qty}")
            self.data[str(remote_max_order_num)] = {
                    "product": remote_prod_name,
                    "quantity": remote_prod_qty
                }
            self.count += 1
            with open(self.db_file, 'w') as f:
                json.dump(self.data, f)
            return order_pb2.SyncResponse(response="-1")

    def HealthCheck(self, request, context):
        # Respond to health check from frontend
        healthCheck = request.healthCheck
        return order_pb2.HealthCheckResponse(healthy=1)

    def Notify(self, request, context):
        # Know leader status
        leader = request.leader
        self.leader_port = leader
        return order_pb2.NotifyResponse(response = "1")

    def update(self, stub, productName, quantity):
        # gRPC
        updateRequest = catalog_pb2.UpdateRequest(productName=productName, quantity=quantity)
        update_result = stub.Update(updateRequest)
        return update_result

    def Buy(self, request, context):
        product_name = request.productName
        product_quantity = request.quantity

        # Send buy request to Catalog service
        with grpc.insecure_channel(f"{self.cat_host}:{self.cat_port}") as channel:
            update_stub = catalog_pb2_grpc.CatalogStub(channel)
            update_result = self.update(update_stub, product_name, product_quantity)
            # Unsuccessful
            if update_result.response == -1:
                buy_response = -1
            elif update_result.response == 0:
                buy_response = 0
            # Update
            elif update_result.response == 1:
                self.count += 1
                with open(self.db_file, 'r') as f:
                    log = json.load(f)
                log[self.count] = {
                    "product": product_name,
                    "quantity": product_quantity
                }
                with open(self.db_file, 'w') as f:
                    json.dump(log, f)
                buy_response = self.count
                for order_service_addr in self.order_service_addrs:
                    self.do_sync(order_service_addr, buy_response, product_name, product_quantity)

        return order_pb2.BuyResponse(orderNumber=buy_response)

    def OrderQuery(self, request, context):
        order_number = request.orderNumber
        # Read db file under rw_lock and respond
        with self.rw_lock:
            with open(self.db_file, 'r') as f:
                data = json.load(f)
        if str(order_number) in data.keys():
            return order_pb2.OrderQueryResponse(orderNumber=order_number, \
                    productName=data[str(order_number)]["product"], \
                    productQty=data[str(order_number)]["quantity"])
        else:
            return order_pb2.OrderQueryResponse(orderNumber="-1")
    
def serve(num_threads, cat_host, cat_port, order_service_addrs):
    # Define database file for the service ID and synchronization lock
    global ORDER_PORT
    _DB = f'order/data/order_database_{ORDER_PORT}.json'
    # Create file if it does not exist
    # Ideally never done, only needed if file gets lost and needs to be recreated
    if not os.path.exists(_DB):
        f = open(_DB, 'x')
        f.write('{}')
        f.close()
    order_service = Order(_DB, cat_host, cat_port, order_service_addrs)

    # Launch Service
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=num_threads))
    order_pb2_grpc.add_OrderServicer_to_server(
        order_service, server)
    server.add_insecure_port(f"[::]:{ORDER_PORT}")
    server.start()
    print("Order Service started")
    server.wait_for_termination()


def main():
    # Launch service
    parser = argparse.ArgumentParser(description='Order Service command line args')
    parser.add_argument("-n", "--num_threads", default=10, help="Size of static thread pool for order service")
    parser.add_argument("-p", "--port", default="50043", help="Order Server Port")
    parser.add_argument('--cat_host', default='localhost', help='Catalog Service IP')
    #parser.add_argument('--cat_port', default="50042", help='Catalog Service Port')
    #parser.add_argument('--id', default=0, help='ID of the order service, for leader election')
    parser.add_argument('--c', '--config', default='config.cfg', help='Config File')
    parser.add_argument('--order_hosts', default=None,
                         help='Comma-separated hosts for the order replicas, in the same order as '
                              'order_ports in the config file (e.g. for one-container-per-replica '
                              'deployments). Defaults to "localhost" for every replica.')
    args = parser.parse_args()
    logging.basicConfig()

    # Read Config
    config = configparser.RawConfigParser()
    config.read(args.c)
    cnfg_dict = dict(config.items('DEV'))

    # Define global ports/addresses
    global ORDER_PORT, CATALOG_PORT
    CATALOG_PORT = cnfg_dict["catalog_port"]
    order_ports = [port.strip() for port in cnfg_dict["order_ports"].split(",")]
    order_hosts = [h.strip() for h in args.order_hosts.split(",")] if args.order_hosts \
        else ["localhost"] * len(order_ports)
    ORDER_PORT = args.port

    # Peer replica addresses, excluding this instance's own port
    peer_pairs = [(h, p) for h, p in zip(order_hosts, order_ports) if p != ORDER_PORT]
    order_service_addrs = [f"{h}:{p}" for h, p in peer_pairs]

    serve(int(args.num_threads), args.cat_host, CATALOG_PORT, order_service_addrs)


if __name__ == '__main__':
    main()