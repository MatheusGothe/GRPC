import grpc
import mine_grpc_pb2
import mine_grpc_pb2_grpc
import inquirer
import hashlib
import threading

SERVER_ADDRESS = 'localhost:8080'
CLIENT_ID = 1  # cada cliente pode ter um ID único

def sha1_hash(solution):
    return hashlib.sha1(solution.encode()).hexdigest()

def mine_challenge(challenge_value):
    """
    Função simples de mineração: tenta soluções numéricas até encontrar
    um hash SHA-1 que satisfaça a condição challenge (ex: hash começando com '0'*challenge)
    """
    target_prefix = '0' * challenge_value
    found = None

    def worker(start, step):
        nonlocal found
        i = start
        while found is None:
            candidate = str(i)
            hash_val = sha1_hash(candidate)
            if hash_val.startswith(target_prefix):
                found = candidate
                break
            i += step

    # Cria threads para minerar
    threads = []
    for t in range(4):  # 4 threads
        thread = threading.Thread(target=worker, args=(t, 4))
        thread.start()
        threads.append(thread)

    for thread in threads:
        thread.join()

    return found

def connect():
    channel = grpc.insecure_channel(SERVER_ADDRESS)
    client = mine_grpc_pb2_grpc.apiStub(channel)
    res = client.registerClient(mine_grpc_pb2.void())
    CLIENT_ID = res.result
    print(f"[CLIENT] Meu ID registrado no servidor é: {CLIENT_ID}")

    opcoes = [
        "getTransactionID",
        "getChallenge",
        "getTransactionStatus",
        "submitChallenge",
        "getWinner",
        "getSolution",
        "Sair"
    ]

    while True:
        pergunta = [
            inquirer.List("operacao",
                          message="Escolha a operação:",
                          choices=opcoes)
        ]
        resposta = inquirer.prompt(pergunta)
        escolha = resposta["operacao"]

        if escolha == "Sair":
            print("Saindo...")
            break

        try:
            if escolha == "getTransactionID":
                res = client.getTransactionId(mine_grpc_pb2.void())
                print(f"TransactionID atual: {res.result}")

            elif escolha == "getChallenge":
                tid = int(input("Entre com transactionID: "))
                res = client.getChallenge(mine_grpc_pb2.transactionId(transactionId=tid))
                print(f"Challenge: {res.result}")

            elif escolha == "getTransactionStatus":
                tid = int(input("Entre com transactionID: "))
                res = client.getTransactionStatus(mine_grpc_pb2.transactionId(transactionId=tid))
                status_str = {0: "Resolvido", 1: "Pendente", -1: "Inválido"}
                print(f"Status: {status_str.get(res.result, 'Desconhecido')}")

            elif escolha == "getWinner":
                tid = int(input("Entre com transactionID: "))
                res = client.getWinner(mine_grpc_pb2.transactionId(transactionId=tid))
                print(f"Vencedor: {res.result if res.result != 0 else 'Ainda não há vencedor'}")

            elif escolha == "getSolution":
                tid = int(input("Entre com transactionID: "))
                res = client.getSolution(mine_grpc_pb2.transactionId(transactionId=tid))
                status_str = {0: "Resolvido", 1: "Pendente", -1: "Inválido"}
                print(f"Status: {status_str.get(res.status, 'Desconhecido')}, "
                      f"Solution: {res.solution}, Challenge: {res.challenge}")

            elif escolha == "submitChallenge":
                # Passo 1: pegar transactionID atual
                tid_res = client.getTransactionId(mine_grpc_pb2.void())
                tid = tid_res.result
                print(f"TransactionID atual: {tid}")

                # Passo 2: pegar challenge
                ch_res = client.getChallenge(mine_grpc_pb2.transactionId(transactionId=tid))
                challenge_value = ch_res.result
                print(f"Challenge recebido: {challenge_value}")

                # Passo 3: minerar localmente
                solution = mine_challenge(challenge_value)
                print(f"Solução encontrada: {solution}")

                # Passo 4: submeter solução ao servidor
                sub_res = client.submitChallenge(mine_grpc_pb2.challengeArgs(
                    transactionId=tid,
                    clientId=CLIENT_ID,
                    solution=solution
                ))
                status_map = {1: "Válida", 0: "Inválida", 2: "Já resolvida", -1: "TransactionID inválida"}
                print(f"Resultado do envio: {status_map.get(sub_res.result, 'Desconhecido')}")

        except Exception as e:
            print(f"Ocorreu um erro: {e}")

if __name__ == '__main__':
    connect()
