import sqlite3
from contextlib import contextmanager

DB_NAME = "livraria.db"

@contextmanager
def get_db_connection():
    """Context manager para gerenciar conexões com o SQLite com segurança."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def inicializar_banco():
    """Inicializa o banco de dados e cria dados de exemplo se não existirem."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS produtos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                preco REAL NOT NULL,
                quantidade_estoque INTEGER NOT NULL
            )
        """)
        # Verifica se já existem dados para evitar duplicação
        cursor.execute("SELECT COUNT(*) FROM produtos")
        if cursor.fetchone()[0] == 0:
            produtos_iniciais = [
                ("O Senhor dos Anéis", 89.90, 15),
                ("1984 - George Orwell", 45.00, 8),
                ("Clean Code", 120.50, 4),
                ("O Pequeno Príncipe", 29.90, 20)
            ]
            cursor.executemany("""
                INSERT INTO produtos (nome, preco, quantidade_estoque) 
                VALUES (?, ?, ?)
            """, produtos_iniciais)
            conn.commit()

def consultar_estoque(item_id: int) -> dict:
    """
    Consulta o estoque de um produto específico na livraria pelo ID.
    
    Args:
        item_id (int): ID do produto/livro no banco de dados.
        
    Returns:
        dict: Informações do produto ou mensagem de erro.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, nome, preco, quantidade_estoque FROM produtos WHERE id = ?", (item_id,))
            row = cursor.fetchone()
            
            if row:
                return {
                    "status": "sucesso",
                    "item_id": row["id"],
                    "nome": row["nome"],
                    "preco": row["preco"],
                    "quantidade_estoque": row["quantidade_estoque"]
                }
            return {"status": "erro", "mensagem": "Produto não encontrado no estoque."}
            
    except sqlite3.Error as e:
        return {"status": "erro", "mensagem": f"Erro interno no banco de dados: {str(e)}"}

def reservar_produto(item_id: int, quantidade: int) -> dict:
    """
    Realiza a reserva de uma quantidade específica de um produto no estoque.
    
    Args:
        item_id (int): ID do produto/livro.
        quantidade (int): Quantidade a ser reservada/retirada.
        
    Returns:
        dict: Status da operação e estoque atualizado.
    """
    if quantidade <= 0:
        return {"status": "erro", "mensagem": "A quantidade para reserva deve ser maior que zero."}
        
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, nome, quantidade_estoque FROM produtos WHERE id = ?", (item_id,))
            row = cursor.fetchone()
            
            if not row:
                return {"status": "erro", "mensagem": "Produto não encontrado."}
                
            estoque_atual = row["quantidade_estoque"]
            
            if estoque_atual < quantidade:
                return {
                    "status": "erro", 
                    "mensagem": f"Estoque insuficiente. Disponível: {estoque_atual}, solicitado: {quantidade}"
                }
                
            novo_estoque = estoque_atual - quantidade
            cursor.execute("UPDATE produtos SET quantidade_estoque = ? WHERE id = ?", (novo_estoque, item_id))
            conn.commit()
            
            return {
                "status": "sucesso",
                "mensagem": f"Reserva realizada com sucesso para o item {row['nome']}.",
                "quantidade_reservada": quantidade,
                "novo_estoque": novo_estoque
            }
            
    except sqlite3.Error as e:
        return {"status": "erro", "mensagem": f"Erro interno ao atualizar banco de dados: {str(e)}"}

# Executa inicialização local se rodado diretamente
if __name__ == "__main__":
    inicializar_banco()
    print("Banco de dados inicializado com sucesso.")