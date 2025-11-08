

## 1. Tecnologias Utilizadas

* **Python 3**
* **gRPC (`grpcio`, `grpcio-tools`):** Framework RPC do Google.
* **Protocol Buffers (Protobuf):** Para definição da interface de serviço.
* **`inquirer`:** Para a criação de menus interativos no cliente.
* **`pybreaker`:** Para a implementação do padrão Circuit Breaker no cliente da calculadora.
* **`threading`:** Para paralelizar a mineração no cliente e para gerenciar concorrência no servidor.

---

## 2. Instruções de Instalação e Execução

É altamente recomendado usar um ambiente virtual (`venv`) para gerenciar as dependências.

### 2.1. Instalação

1.  Clone este repositório:
    ```bash
    git clone https://github.com/MatheusGothe/GRPC.git
    cd <nome-do-repositorio>
    ```

2.  Crie e ative um ambiente virtual:
    ```bash
    # Linux/macOS
    python3 -m venv venv
    source venv/bin/activate

    # Windows
    python -m venv venv
    .\venv\Scripts\activate
    ```

3.  Instale as dependências necessárias:
    ```bash
    pip install grpcio grpcio-tools pybreaker inquirer
    ```

### 2.2. Regenerando os Stubs (Opcional)

Os arquivos `_pb2.py` e `_pb2_grpc.py` já estão incluídos. Caso precise regenerá-los (após modificar um arquivo `.proto`), use os comandos abaixo a partir da pasta `fontes/grpc/`:

```bash
# Para a Calculadora
python -m grpc_tools.protoc --proto_path=Calculadora/ --python_out=Calculadora/ --grpc_python_out=Calculadora/ Calculadora/grpcCalc.proto

# Para o Minerador
python -m grpc_tools.protoc --proto_path=Minerador/ --python_out=Minerador/ --grpc_python_out=Minerador/ Minerador/mine_grpc.proto