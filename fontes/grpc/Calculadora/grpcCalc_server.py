import grpc
import time
from concurrent import futures
import grpcCalc_pb2
import grpcCalc_pb2_grpc


def serve():
    grpc_server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    grpcCalc_pb2_grpc.add_apiServicer_to_server(CalculatorServicer(), grpc_server)
    grpc_server.add_insecure_port('[::]:8080')
    print("Servidor rodando na porta 8080")
    grpc_server.start()
    grpc_server.wait_for_termination()


class CalculatorServicer(grpcCalc_pb2_grpc.apiServicer):

     def sum(self, request, context):
        return grpcCalc_pb2.Resultado(valor=request.num1 + request.num2)

     def sub(self, request, context):
        return grpcCalc_pb2.Resultado(valor=request.num1 - request.num2)

     def mult(self, request, context):
        return grpcCalc_pb2.Resultado(valor=request.num1 * request.num2)

     def divide(self, request, context):
        if request.num2 == 0:
            #Evita divisão por zero
            return grpcCalc_pb2.Resultado(valor=0)
        return grpcCalc_pb2.Resultado(valor=request.num1 / request.num2)


if __name__ == '__main__':
    serve()
    
