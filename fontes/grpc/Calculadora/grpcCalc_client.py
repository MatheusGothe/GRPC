import grpc
import grpcCalc_pb2
import grpcCalc_pb2_grpc
import pybreaker
import inquirer

breaker = pybreaker.CircuitBreaker(fail_max=2, reset_timeout=2)

@breaker
def connect():
    channel = grpc.insecure_channel('localhost:8080')
    client = grpcCalc_pb2_grpc.apiStub(channel)

    opcoes = ["Adição", "Subtração", "Multiplicação", "Divisão", "Sair"]

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
            num1 = float(input("Entre com o primeiro número: "))
            num2 = float(input("Entre com o segundo número: "))
        except ValueError:
            print("Número inválido!")
            continue

        try:
            if escolha == "Adição":
                res = client.sum(grpcCalc_pb2.Operacao(num1=num1, num2=num2))
            elif escolha == "Subtração":
                res = client.sub(grpcCalc_pb2.Operacao(num1=num1, num2=num2))
            elif escolha == "Multiplicação":
                res = client.mult(grpcCalc_pb2.Operacao(num1=num1, num2=num2))
            elif escolha == "Divisão":
                res = client.divide(grpcCalc_pb2.Operacao(num1=num1, num2=num2))
            
            print(f"Resultado: {res.valor}")

        except pybreaker.CircuitBreakerError:
            print("Erro: Circuit Breaker ativado! Servidor indisponível momentaneamente.")

if __name__ == '__main__':
    connect()
