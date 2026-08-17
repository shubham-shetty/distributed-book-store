import pytest

from catalog_pb2 import QueryRequest, UpdateRequest


# Define Stubs and Services

@pytest.fixture(scope='module')
def grpc_add_to_server():
    from catalog_pb2_grpc import add_CatalogServicer_to_server
    return add_CatalogServicer_to_server

@pytest.fixture(scope='module')
def grpc_servicer():
    from catalog import Catalog
    return Catalog()

@pytest.fixture(scope='module')
def grpc_stub(grpc_channel):
    from catalog_pb2_grpc import CatalogStub
    return CatalogStub(grpc_channel)


# Unit Tests

def test_query_successful(grpc_stub):
    request = QueryRequest(productName="1984")
    response = grpc_stub.Query(request)
    assert round(response.price,2) == 15.99

def test_query_invalid(grpc_stub):
    request = QueryRequest(productName="unknown")
    response = grpc_stub.Query(request)
    assert response.price == -1

def test_update_successful(grpc_stub):
    request = UpdateRequest(productName="1984", quantity=1)
    response = grpc_stub.Update(request)
    assert response.response == 1

def test_update_invalid(grpc_stub):
    request = UpdateRequest(productName="unknown")
    response = grpc_stub.Update(request)
    assert response.response == -1