## Testing the Services

Code present in this directory was used to unit-test our application. Before running the unit tests, ensure that your system has `pytest` and `pytest-grpc` installed (this should be covered by the `requirements.txt` file). In order to separately install these modules, run -  

```shell
pip3 install pytest  
pip3 install pytest-grpc
```  

Next, unit-tests for each service can be run as -  

1. Catalog Service
```shell
PYTHONPATH=../src/catalog pytest test_catalog.py --grpc-fake-server
```  

2. Order Service
```shell
PYTHONPATH=../src/order pytest test_order.py --grpc-fake-server
```  

3. Front-End Service  
```shell
python3 -m unittest test_front_end.py
```  

Outputs for the test cases can be found in the `test_output.pdf` file.

Note: `test_update_successful` (catalog) and `test_buy_successful`/`test_buy_invalid` (order) call
out synchronously to a peer service that isn't running in isolation, so they only pass when the
full stack is already up via `../src/build.sh`.

Reference - https://github.com/kataev/pytest-grpc
