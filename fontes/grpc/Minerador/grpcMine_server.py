import grpc
from concurrent import futures
import mine_grpc_pb2
import mine_grpc_pb2_grpc
import threading
import random
import hashlib

PORT = 8080
transactions = {}
transactions_lock = threading.Lock()
current_transaction_id = 0
client_id_counter = 0
clients = set()
clients_lock = threading.Lock()
winners_history = []
def generate_challenge():
    """Gera desafio aleatório entre 1 e 6"""
    value = random.randint(1, 6)
    # se quiser setar padrão
    # value = 5
    print(f"[DEBUG] Challenge gerado: {value}")
    return value

def sha1_hash(solution):
    return hashlib.sha1(solution.encode()).hexdigest()

def init_transaction():
    global current_transaction_id
    with transactions_lock:
        transactions[current_transaction_id] = {
            'challenge': generate_challenge(),
            'solution': None,
            'winner': -1
        }
    print(f"Transação inicial criada: ID={current_transaction_id}, desafio={transactions[current_transaction_id]['challenge']}")

class MinerServicer(mine_grpc_pb2_grpc.apiServicer):
    def getTransactionId(self, request, context):
        with transactions_lock:
            return mine_grpc_pb2.intResult(result=current_transaction_id)

    def getChallenge(self, request, context):
        tid = request.transactionId
        with transactions_lock:
            tx = transactions.get(tid)
            return mine_grpc_pb2.intResult(result=tx['challenge'] if tx else -1)

    def getTransactionStatus(self, request, context):
        tid = request.transactionId
        with transactions_lock:
            tx = transactions.get(tid)
            if not tx:
                return mine_grpc_pb2.intResult(result=-1)
            return mine_grpc_pb2.intResult(result=1 if tx['solution'] is None else 0)

    def submitChallenge(self, request, context):
        global current_transaction_id
        tid = request.transactionId
        client_id = request.clientId
        solution = request.solution

        with transactions_lock:
            tx = transactions.get(tid)
            if not tx:
                return mine_grpc_pb2.intResult(result=-1)
            if tx['solution'] is not None:
                return mine_grpc_pb2.intResult(result=2)

            target_prefix = '0' * tx['challenge']
            if sha1_hash(solution).startswith(target_prefix):
                tx['solution'] = solution
                tx['winner'] = client_id
                winners_history.append((tid, client_id))
                print(f"Transação {tid} resolvida pelo Cliente {client_id} com solução {solution}")
                # Cria nova transação
                current_transaction_id += 1
                transactions[current_transaction_id] = {
                    'challenge': generate_challenge(),
                    'solution': None,
                    'winner': -1
                }
                print(f"Nova transação criada: ID={current_transaction_id}, desafio={transactions[current_transaction_id]['challenge']}")
                return mine_grpc_pb2.intResult(result=1)
            else:
                return mine_grpc_pb2.intResult(result=0)

    def getWinner(self, request, context):
        tid = request.transactionId
        with transactions_lock:
            tx = transactions.get(tid)
            if not tx:
                return mine_grpc_pb2.intResult(result=-1)
            return mine_grpc_pb2.intResult(result=tx['winner'] if tx['winner'] != -1 else 0)

    def getSolution(self, request, context):
        tid = request.transactionId
        with transactions_lock:
            tx = transactions.get(tid)
            if not tx:
                return mine_grpc_pb2.structResult(status=-1, solution="", challenge=0)
            status = 1 if tx['solution'] is None else 0
            return mine_grpc_pb2.structResult(
                status=status,
                solution=tx['solution'] or "",
                challenge=tx['challenge']
            )
    def registerClient(self, request, context):
        global client_id_counter

        with clients_lock:
            client_id_counter += 1
            new_client_id = client_id_counter
            clients.add(new_client_id)

        print(f"[SERVER] Novo cliente registrado → ID={new_client_id}")
        return mine_grpc_pb2.intResult(result=new_client_id)


def serve():
    init_transaction()
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    mine_grpc_pb2_grpc.add_apiServicer_to_server(MinerServicer(), server)
    server.add_insecure_port(f'[::]:{PORT}')
    print(f"Servidor Minerador rodando na porta {PORT}")
    server.start()
    server.wait_for_termination()

if __name__ == "__main__":
    serve()
