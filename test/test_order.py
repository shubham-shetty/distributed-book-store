import pytest

from order_pb2 import BuyRequest, OrderQueryRequest


# Define Stubs and Services

@pytest.fixture(scope='module')
def grpc_add_to_server():
    from order_pb2_grpc import add_OrderServicer_to_server
    return add_OrderServicer_to_server

@pytest.fixture(scope='module')
def grpc_servicer():
    from order import Order
    return Order()

@pytest.fixture(scope='module')
def grpc_stub(grpc_channel):
    from order_pb2_grpc import OrderStub
    return OrderStub(grpc_channel)


# Unit Tests

def test_order_query_successful(grpc_stub):
    request = OrderQueryRequest(orderNumber="1")
    response = grpc_stub.OrderQuery(request)
    assert response.orderNumber == "1"

def test_order_query_invalid(grpc_stub):
    request = OrderQueryRequest(orderNumber="2000")
    response = grpc_stub.OrderQuery(request)
    assert response.orderNumber == "-1"

def test_buy_successful(grpc_stub):
    request = BuyRequest(productName="1984", quantity=1)
    response = grpc_stub.Buy(request)
    assert response.orderNumber > 0

def test_buy_invalid(grpc_stub):
    request = BuyRequest(productName="unknown", quantity=1)
    response = grpc_stub.Buy(request)
    assert response.orderNumber == -1