import paho.mqtt.client as mqtt
import json
import random
import time
import threading
import sys
import hashlib

# --- CONFIGURAÇÕES ---
BROKER = "broker.emqx.io"  # Broker público para teste (ou use "localhost")
PORT = 1883
TOPIC_PREFIX = "sd/matheus_grupo_X/"
NUM_PARTICIPANTES = 3  # Quantos processos precisam estar rodando para começar

# Tópicos
TOPIC_INIT = f"{TOPIC_PREFIX}init"
TOPIC_ELECTION = f"{TOPIC_PREFIX}election"
TOPIC_CHALLENGE = f"{TOPIC_PREFIX}challenge"
TOPIC_SOLUTION = f"{TOPIC_PREFIX}solution"
TOPIC_RESULT = f"{TOPIC_PREFIX}result"

# --- ESTADOS DO SISTEMA ---
STATE_INIT = 0
STATE_ELECTION = 1
STATE_RUNNING = 2

# --- VARIÁVEIS GLOBAIS ---
my_client_id = random.randint(1, 65000)
my_vote_id = random.randint(1, 65000)
current_state = STATE_INIT

# Armazenamento de Eleição
peers_found = set()      # IDs recebidos no INIT
votes_received = {}      # {client_id: vote_id} recebidos na ELECTION

# Variáveis de Controle (Líder/Minerador)
am_i_leader = False
leader_id = -1

# Variáveis de Transação
current_transaction_id = 0
current_challenge = 0
transaction_resolved = False

# Eventos para sincronização de Threads
evt_election_start = threading.Event()
evt_election_end = threading.Event()
evt_challenge_received = threading.Event()
evt_solution_verified = threading.Event()

# Lock para print não embaralhar
print_lock = threading.Lock()

def log(msg):
    with print_lock:
        print(f"[{my_client_id}] {msg}")

# --- REAPROVEITAMENTO DA LÓGICA DE MINERAÇÃO (DO SEU CODIGO ANTIGO) ---
def sha1_hash(solution):
    return hashlib.sha1(solution.encode()).hexdigest()

def mine_challenge_logic(challenge_value):
    target_prefix = '0' * challenge_value
    found = None
    start_time = time.time()
    
    # Flag para parar se alguém resolver antes (opcional, mas bom ter)
    stop_mining = False

    def worker():
        nonlocal found
        while found is None and not stop_mining:
            candidate_int = random.getrandbits(64)
            candidate = str(candidate_int)
            hash_val = hashlib.sha1(candidate.encode()).hexdigest()
            if hash_val.startswith(target_prefix):
                found = candidate
                break

    threads = []
    # Usando 4 threads como no seu original
    for _ in range(4): 
        t = threading.Thread(target=worker)
        t.start()
        threads.append(t)

    # Espera as threads terminarem ou acharem solução
    while found is None:
        time.sleep(0.1)
        # Aqui poderíamos checar se chegou mensagem de RESULT de outro user para parar
        pass

    for t in threads:
        t.join()

    total_time = time.time() - start_time
    log(f"Mineração concluída em {total_time:.2f}s. Solução: {found}")
    return found

# --- CALLBACKS MQTT ---

def on_connect(client, userdata, flags, rc, properties):
    if rc == 0:
        log("Conectado ao Broker MQTT.")
        # Assina todos os tópicos do sistema
        client.subscribe(f"{TOPIC_PREFIX}#")
    else:
        log(f"Falha na conexão. Código: {rc}")

def on_message(client, userdata, msg):
    try:
        topic = msg.topic
        payload = json.loads(msg.payload.decode())
        
        # 1. FASE DE INIT
        if topic == TOPIC_INIT:
            sender_id = payload["clientId"]
            if sender_id not in peers_found:
                peers_found.add(sender_id)
                log(f"Peer encontrado: {sender_id}. Total: {len(peers_found)}/{NUM_PARTICIPANTES}")

        # 2. FASE DE ELEIÇÃO
        elif topic == TOPIC_ELECTION:
            sender_id = payload["clientId"]
            vote = payload["voteId"]            
            if sender_id not in peers_found:
                peers_found.add(sender_id)
                log(f"Peer detectado via Eleição (Adiantado): {sender_id}. Total: {len(peers_found)}/{NUM_PARTICIPANTES}")
            #
            votes_received[sender_id] = vote
            
        # 3. FASE DE OPERAÇÃO - CHALLENGE
        elif topic == TOPIC_CHALLENGE:
            # Só interessa se eu NÃO for o líder
            if not am_i_leader:
                global current_transaction_id, current_challenge
                current_transaction_id = payload["transactionId"]
                current_challenge = payload["challenge"]
                log(f"Novo desafio recebido! ID: {current_transaction_id}, Dificuldade: {current_challenge}")
                evt_challenge_received.set()

        # 4. FASE DE OPERAÇÃO - SOLUTION
        elif topic == TOPIC_SOLUTION:
            # Só interessa se eu FOR o líder (para validar)
            if am_i_leader:
                log(f"Solução recebida de {payload['clientId']} para transação {payload['transactionId']}")
                validate_solution(client, payload)

        # 5. FASE DE OPERAÇÃO - RESULT
        elif topic == TOPIC_RESULT:
            if "result" not in payload or "clientId" not in payload:
                log(f"Mensagem inválida recebida em {topic}: {payload}")
                return

            result = payload["result"]
            winner = payload["clientId"]
            
            if result != 0:
                log(f"Transação encerrada! Vencedor: {winner}")

    except Exception as e:
        log(f"Erro ao processar mensagem: {e}")

# --- FUNÇÕES DO CONTROLADOR (LÍDER) ---

def start_controller_loop(client):
    log("=== INICIANDO MODO CONTROLADOR ===")
    global current_transaction_id
    global current_challenge
    
    while True:
        # 1. Gerar nova transação
        current_transaction_id += 1
        #challenge_val = random.randint(1, 5) # Dificuldade baixa para teste rápido. PDF pede 1..20
        current_challenge = random.randint(1, 5)
        # 2. Publicar Desafio
        msg = {
            "transactionId": current_transaction_id,
            "challenge": current_challenge
        }
        log(f"Publicando desafio {current_transaction_id} (Dificuldade: {current_challenge})...")
        client.publish(TOPIC_CHALLENGE, json.dumps(msg))
        
        # 3. Aguardar solução (Bloqueia até que on_message processe uma solução válida)
        global transaction_resolved
        transaction_resolved = False
        
        while not transaction_resolved:
            time.sleep(1)
            
        log("Preparando próxima rodada em 5 segundos...\n")
        time.sleep(5)

def validate_solution(client, payload):
    global transaction_resolved
    
    if transaction_resolved:
        return # Já foi resolvido por outro
        
    tid = payload["transactionId"]
    cid = payload["clientId"]
    sol = payload["solution"]
    
    # Verifica se ID bate
    if tid != current_transaction_id:
        return # Transação antiga ou futura
        
    # Verifica hash
    # Recalcula o hash da solução enviada
    calculated_hash = sha1_hash(sol)
    
    # Verifica dificuldade (seu codigo antigo: target_prefix)
    # Precisamos saber o challenge atual
    # Como sou lider, eu sei o challenge enviado na msg anterior, 
    # mas o payload de solution nao traz o challenge, eu uso o local.
    # OBS: O PDF diz que o payload de solution tem ClientID, TransactionID, Solution.
    
    # Recupera o challenge que eu gerei para este ID
    # (Para simplificar, assumimos que current_challenge variavel global guarda o ultimo gerado)
    # Mas aqui no loop do controlador eu não salvei numa global, vamos corrigir:
    # No loop do controlador eu mandei challenge_val.
    # Mas para validar preciso saber qual foi.
    # Vamos assumir que a validação é simples: Hash deve começar com zeros.
    
    # Simplificação: O controlador precisa guardar o challenge atual.
    # Vamos assumir que o payload['challenge'] foi guardado no dicionario de transacoes
    # Mas como simplifiquei, vamos assumir que o controlador sabe qual dificuldade ele pediu.
    # NOTA: O código do controlador precisa de acesso à dificuldade atual.
    
    # Correção rápida: vamos extrair a dificuldade do próprio hash? Não.
    # Vamos assumir que o controlador manteve o estado. 
    # Vou buscar challenge_val da logica do start_controller_loop se tornasse global,
    # mas aqui vou fazer uma validação genérica baseada no que foi pedido.
    
    # Para validar corretamente, o controlador deve ter armazenado. 
    # Vou pular a validação estrita de "qual era o número" e validar se o hash é válido matematicamente 
    # para ALGUM nível? Não, tem que ser o pedido.
    
    # VAMOS REFAZER A ESTRUTURA DE DADOS DO LIDER RAPIDAMENTE
    # O Controller Loop define o challenge. Vamos salvar numa tabela simples global aqui.
    # Como é síncrono, só existe UM desafio por vez.
    pass 

    # Na função start_controller_loop, eu preciso salvar o challenge atual numa global para a validação ler
    # Vou ajustar a start_controller_loop para atualizar 'current_challenge' global.

    target_prefix = '0' * current_challenge 
    
    valid = False
    if calculated_hash.startswith(target_prefix):
        valid = True
        transaction_resolved = True
        
        # Publica Resultado Positivo
        res_msg = {
            "clientId": cid,
            "transactionId": tid,
            "solution": sol,
            "result": 1 # Válido
        }
        client.publish(TOPIC_RESULT, json.dumps(res_msg))
        log(f"Solução VÁLIDA de {cid}. Hash: {calculated_hash}")
    else:
        # Publica Resultado Negativo (opcional se quiser avisar que falhou, mas PDF pede)
        res_msg = {
            "clientId": cid,
            "transactionId": tid,
            "solution": sol,
            "result": 0 # Inválido
        }
        client.publish(TOPIC_RESULT, json.dumps(res_msg))
        log(f"Solução INVÁLIDA de {cid}.")

# --- FUNÇÕES DO MINERADOR (WORKER) ---

def start_miner_loop(client):
    log("=== INICIANDO MODO MINERADOR ===")
    
    while True:
        log("Aguardando desafio...")
        evt_challenge_received.wait() # Bloqueia até chegar mensagem no on_message
        evt_challenge_received.clear()
        
        log(f"Trabalhando no desafio {current_transaction_id} com dificuldade {current_challenge}")
        
        # Executa a mineração (Bloqueante ou Threaded - aqui usando sua logica)
        solution = mine_challenge_logic(current_challenge)
        
        # Envia solução
        msg = {
            "clientId": my_client_id,
            "transactionId": current_transaction_id,
            "solution": solution
        }
        client.publish(TOPIC_SOLUTION, json.dumps(msg))
        log("Solução enviada. Aguardando resultado...")
        
        # Pequena pausa para não floodar
        time.sleep(1)

# --- FLUXO PRINCIPAL ---

def main():
    log("Iniciando Node...")
    
    # Configura MQTT
    client = mqtt.Client(
    client_id=f"Node-{my_client_id}",
    callback_api_version=mqtt.CallbackAPIVersion.VERSION2
)
    client.on_connect = on_connect
    client.on_message = on_message
    
    try:
        client.connect(BROKER, PORT, 60)
        client.loop_start() # Thread separada para rede
    except:
        log("Não foi possível conectar ao Broker. Verifique internet ou firewall.")
        return

    # --- FASE 1: INIT ---
    # Publica meu ID e espera até ter N participantes
    while len(peers_found) < NUM_PARTICIPANTES:
        # Publica minha presença
        msg = {"clientId": my_client_id}
        client.publish(TOPIC_INIT, json.dumps(msg))
        
        # Verifica se eu mesmo já estou na lista (loopback do mqtt)
        # Se o broker não suportar loopback, adicione manualmente:
        if my_client_id not in peers_found:
            peers_found.add(my_client_id)
            
        time.sleep(2) # Reenvia a cada 2s
        
    log("Fase de Init concluída. Todos os participantes encontrados.")
    time.sleep(2) # Margem de segurança

    # --- FASE 2: ELEIÇÃO ---
    log("Iniciando Eleição...")
    
    # Publica Voto
    while len(votes_received) < NUM_PARTICIPANTES:
        msg = {
            "clientId": my_client_id,
            "voteId": my_vote_id
        }
        client.publish(TOPIC_ELECTION, json.dumps(msg))
        
        # Auto-voto caso loopback falhe
        if my_client_id not in votes_received:
            votes_received[my_client_id] = my_vote_id
            
        time.sleep(2)
        
    log("Votos recebidos. Contabilizando...")
    
    # Algoritmo de decisão: Maior VoteID ganha. Empate = Maior ClientID.
    winner_id = -1
    max_vote = -1
    
    for cid, vote in votes_received.items():
        log(f"Candidato {cid} votou {vote}")
        if vote > max_vote:
            max_vote = vote
            winner_id = cid
        elif vote == max_vote:
            # Desempate pelo ID
            if cid > winner_id:
                winner_id = cid
                
    global am_i_leader, leader_id
    leader_id = winner_id
    am_i_leader = (my_client_id == leader_id)
    
    log(f"Eleição concluída. LÍDER: {leader_id}. Sou eu? {am_i_leader}")
    time.sleep(2)

    # --- FASE 3: RUNNING ---
    if am_i_leader:
        # O Controlador precisa atualizar a global current_challenge dentro do loop
        # para a validação funcionar. Vamos fazer um wrapper.
        try:
            global current_challenge 
            # Loop do Controlador
            while True:
                # 1. Gerar nova transação
                global current_transaction_id, transaction_resolved
                current_transaction_id += 1
                current_challenge = random.randint(1, 5) # Ajuste a dificuldade aqui
                
                # 2. Publicar Desafio
                msg = {
                    "transactionId": current_transaction_id,
                    "challenge": current_challenge
                }
                log(f"CONTROLADOR: Publicando desafio {current_transaction_id} (Nível: {current_challenge})...")
                client.publish(TOPIC_CHALLENGE, json.dumps(msg))
                
                # 3. Aguardar solução
                transaction_resolved = False
                while not transaction_resolved:
                    time.sleep(0.5)
                
                log("CONTROLADOR: Rodada finalizada. Próxima em 5s...\n")
                time.sleep(5)
                
        except KeyboardInterrupt:
            pass
    else:
        # Loop do Minerador
        try:
            start_miner_loop(client)
        except KeyboardInterrupt:
            pass

    client.loop_stop()
    client.disconnect()

if __name__ == "__main__":
    # Pega numero de participantes do argumento ou usa padrão
    if len(sys.argv) > 1:
        NUM_PARTICIPANTES = int(sys.argv[1])
        
    print(f"Sistema configurado para aguardar {NUM_PARTICIPANTES} participantes.")
    main()