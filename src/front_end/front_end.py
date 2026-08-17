import argparse, configparser
from csv import excel
import json
from http.server import BaseHTTPRequestHandler, HTTPServer, ThreadingHTTPServer
import re
import logging
import time
from collections import defaultdict
from async_timeout import timeout

import grpc
import catalog_pb2
import catalog_pb2_grpc
import order_pb2
import order_pb2_grpc


# Define Service Stubs
def query(stub, productName):
    # Execute query function on Catalog server
    queryRequest = catalog_pb2.QueryRequest(productName=productName)
    query_result = stub.Query(queryRequest)
    return query_result

def buy(stub, productName, quantity):
    # Execute buy function on Order server
    buyRequest = order_pb2.BuyRequest(productName=productName, quantity=quantity)
    buy_result = stub.Buy(buyRequest, timeout=1)
    return buy_result

def order_query(stub, order_number):
    # Query the order database on Order server
    orderRequest = order_pb2.OrderQueryRequest(orderNumber=order_number)
    order_request_result = stub.OrderQuery(orderRequest, timeout=1)
    return order_request_result

def health_check(stub):
    # Health check on Order server
    # FIXME Parameterize timeout?
    healthCheck = 1
    healthCheckRequest = order_pb2.HealthCheckRequest(healthCheck = healthCheck)
    health_check_response = stub.HealthCheck(healthCheckRequest, timeout=1)
    return health_check_response

def notify(stub, order_service_leader):
    # Notify the order service non-leaders about the leader
    notifyRequest = order_pb2.NotifyRequest(leader=order_service_leader)
    notify_resp = stub.Notify(notifyRequest, timeout=1)
    return notify_resp


class HTTPRequestHandler(BaseHTTPRequestHandler):
    '''
    Class to handle HTTP requests coming in to the front-end service of the server
    Defines actions for the GET and POST methods
    '''

    def _make_json(self, product):
        # Create JSON Response for Catalog Query 
        resp = {
               "productName": product.productName,
               "price": product.price,
               "quantity": product.quantity
            }
        return {"data": resp}


    def _send_response(self, status_code, json_body):
        # Send response to client
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        # Return the json as output stream
        output = json.dumps(json_body) 
        self.wfile.write(output.encode('utf8'))
        # self.wfile.flush()


    def queryCatalog(self):
        product_name = self.path.split('/')[-1]
        # Check cache first
        if product_name in cache.keys():
            self._send_response(200, cache[product_name])
        else:
            with grpc.insecure_channel(CATALOG_ADDR) as channel:
                catalog_stub = catalog_pb2_grpc.CatalogStub(channel)
                payload = query(catalog_stub, product_name) 
            
            # Update cache
            cache[product_name] = self._make_json(payload)

            # If available
            if payload.price != -1 and payload.quantity != -1:
                status_code = 200
                self._send_response(status_code, self._make_json(payload))

            # If one condition not met
            else:
                err = {
                    "error": {
                        "code": 404,
                        "message": "product not found"
                    }
                }
                self._send_response(404, err)


    def queryOrder(self):
        # Query order by order number
        global ORDER_ADDR
        order_number = self.path.split('/')[-1]
        if ORDER_ADDR is None:
            ORDER_ADDR = pick_order_service_leader(order_service_addrs)
        if ORDER_ADDR is None:
            err = {"error": {"code": 503, "message": "Order service unavailable"}}
            self._send_response(503, err)
            return
        with grpc.insecure_channel(ORDER_ADDR) as channel:
            order_stub = order_pb2_grpc.OrderStub(channel)
            try:
                query_resp = order_query(order_stub, order_number)
            except grpc.RpcError as e:
                #e.details()
                status_code = e.code()
                logging.debug(f"gRPC Exception {status_code.name}: {status_code.value}")
                ORDER_ADDR = pick_order_service_leader(order_service_addrs)
        if int(query_resp.orderNumber) <= 0:
            err = {
                "error": {
                    "code": 404,
                    "message": "Order number does not exist"
                }
            }
            self._send_response(404, err)
        elif int(query_resp.orderNumber) > 0:
            resp = {
                "number": query_resp.orderNumber,
                "name": query_resp.productName,
                "quantity": query_resp.productQty
                }
            self._send_response(200, {"data": resp})


    def do_GET(self):
        print("EXECUTE GET")
        if re.search('/products/*', self.path):
            # Query Catalog
            self.queryCatalog()
        elif re.search('/orders/*', self.path):
            # Query Order
            self.queryOrder()
        else:
            # Invalid GET request received
            err = {
                "error": {
                    "code": 405,
                    "message": "Invalid GET request received"
                }
            }
            self._send_response(405, err)


    def postOrder(self):
        global ORDER_ADDR
        input_length = int(self.headers.get('content-length'))
        data = self.rfile.read(input_length).decode('utf8')
        json_data = json.loads(data)
        product_name = json_data["name"]
        product_quantity = json_data["quantity"]
        order_flag = 0
        while order_flag == 0:
            if ORDER_ADDR is None:
                ORDER_ADDR = pick_order_service_leader(order_service_addrs)
            if ORDER_ADDR is None:
                err = {"error": {"code": 503, "message": "Order service unavailable"}}
                self._send_response(503, err)
                return
            with grpc.insecure_channel(ORDER_ADDR) as channel:
                order_stub = order_pb2_grpc.OrderStub(channel)
                try:
                    buy_resp = buy(order_stub, product_name, product_quantity)
                    msg = int(buy_resp.orderNumber)
                    order_flag = 1
                except grpc.RpcError as e:
                    #e.details()
                    print(f"Caused Exception {e}")
                    status_code = e.code()
                    logging.debug(f"gRPC Exception {status_code.name}: {status_code.value}")
                    ORDER_ADDR = pick_order_service_leader(order_service_addrs)
        # If the order number is valid
        print(f"orderNumber: {msg}")
        if msg > 0:
            json_response = {
                "data": {
                    "order_number": msg
                }
            }
            self._send_response(200, json_response)
        # Not in stock
        elif msg == 0:
            err = {
                "error": {
                    "code": 404,
                    "message": "Not in stock"
                }
            }
            self._send_response(404, err)
        # Book not stocked
        elif msg == -1:
            err = {
                "error": {
                    "code": 405,
                    "message": "Book not stocked"
                }
            }
            self._send_response(404, err)


    def do_POST(self):
        print("EXECUTE POST", flush=True)
        if re.search('/orders', self.path):
            # Create Order Request
            self.postOrder()
        # Invalid POST request
        else:
            err = {
                "error": {
                    "code": 405,
                    "message": "Invalid request"
                }
            }
            self._send_response(405, err)


    def do_PUT(self):
        print("EXECUTE PUT")
        if re.search('/invalidate/*', self.path):
            product_name = self.path.split('/')[-1]
            # Check if it's in cache
            if product_name in cache:
                del cache[product_name]


def pick_order_service_leader(order_service_addrs, retries=15, retry_delay=1):
    '''
    Picks the order service leader on startup, retrying briefly in case the
    order replicas are still coming up (e.g. containers starting concurrently).
    '''
    for attempt in range(retries):
        for order_service_addr in order_service_addrs:
            with grpc.insecure_channel(order_service_addr) as channel:
                order_stub = order_pb2_grpc.OrderStub(channel)
                try:
                    health_check_resp = health_check(order_stub)
                    if health_check_resp.healthy == 1:
                        notify_non_leaders(order_service_addrs, order_service_addr)
                        return order_service_addr
                except grpc.RpcError as e:
                    #e.details()
                    status_code = e.code()
                    logging.debug(f"gRPC Exception {status_code.name}: {status_code.value}")
                    continue
        if attempt < retries - 1:
            logging.debug("No order service leader found, retrying...")
            time.sleep(retry_delay)
    return None


def notify_non_leaders(order_service_addrs, order_service_leader):
    '''
    Notifies non-leaders of the leader
    '''
    for order_service_addr in order_service_addrs:
        if order_service_addr != order_service_leader:
            with grpc.insecure_channel(order_service_addr) as channel:
                try:
                    order_stub = order_pb2_grpc.OrderStub(channel)
                    notify_resp = notify(order_stub, order_service_leader)
                except grpc.RpcError as e:
                    #e.details()
                    status_code = e.code()
                    logging.debug(f"gRPC Exception {status_code.name}: {status_code.value}")
                    continue

def main():
    # Define global cache variable =
    global cache 
    # Format:
    # { "product_name": {"data": resp} }
    cache = defaultdict(dict)

    # Front-end acts as an interface for clients, clients send HTTP Requests to front-end
    # Front-end HTTP Request Handler redirects the requests to appropriate services
    parser = argparse.ArgumentParser()
    parser.add_argument('--hn', '--hostname', default='localhost', help='HTTP Server Hostname (IP)')
    parser.add_argument('--p', '--port', type=int, default=12345, help='Listening port for HTTP Server')
    parser.add_argument('--c', '--config', default='config.cfg', help='Config File for Order Server Ports')
    parser.add_argument('--catalog_host', default='localhost', help='Catalog Service Host (e.g. a container/service name)')
    parser.add_argument('--order_hosts', default=None,
                         help='Comma-separated hosts for the order replicas, in the same order as '
                              'order_ports in the config file (e.g. for one-container-per-replica '
                              'deployments). Defaults to "localhost" for every replica.')
    args = parser.parse_args()

    # Read Config
    config = configparser.RawConfigParser()
    config.read(args.c)
    cnfg_dict = dict(config.items('DEV'))

    # Pick a leader, define global addresses
    global ORDER_ADDR, CATALOG_ADDR, order_service_addrs
    CATALOG_ADDR = f"{args.catalog_host}:{cnfg_dict['catalog_port']}"
    order_ports = [port.strip() for port in cnfg_dict["order_ports"].split(",")]
    order_hosts = [h.strip() for h in args.order_hosts.split(",")] if args.order_hosts \
        else ["localhost"] * len(order_ports)
    order_service_addrs = [f"{h}:{p}" for h, p in zip(order_hosts, order_ports)]
    ORDER_ADDR = pick_order_service_leader(order_service_addrs)
    print("Order Service Leader: ", ORDER_ADDR)

    # Start Front-End Server
    server = ThreadingHTTPServer((args.hn, args.p), HTTPRequestHandler)
    print("Front-End Server Up")
    logging.debug('Server up...')
    server.serve_forever()


if __name__ == '__main__':
    main()