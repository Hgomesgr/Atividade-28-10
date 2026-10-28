from __future__ import annotations

import json
import os
import sys
import streamlit as st
from dotenv import find_dotenv, load_dotenv
from openai import AzureOpenAI

from database import inicializar_banco, consultar_estoque, reservar_produto

# Inicializa o banco de dados SQLite local
inicializar_banco()

st.set_page_config(page_title="BookBot - Azure OpenAI Agent", page_icon="📚")

st.title("📚 BookBot - Agente de IA com Azure OpenAI")
st.write("Assistente de inventário inteligente integrado via Azure OpenAI com Function Calling.")

# Configuração e validação do ambiente Azure OpenAI
REQUIRED_VARS = (
    "AZURE_OPENAI_ENDPOINT",
    "AZURE_OPENAI_API_KEY",
    "AZURE_OPENAI_DEPLOYMENT",
)

def load_config() -> dict[str, str]:
    """Carrega e valida as variáveis de ambiente utilizando dotenv."""
    env_path = find_dotenv(usecwd=True)
    load_dotenv(env_path, override=True)

    config: dict[str, str] = {}
    for name in REQUIRED_VARS:
        value = (os.getenv(name) or "").strip().strip('"').strip("'")
        if not value:
            st.error(f"[config] A variável de ambiente `{name}` está vazia ou ausente.")
            return {}
        config[name] = value

    endpoint = config["AZURE_OPENAI_ENDPOINT"]
    if not endpoint.startswith("https://") or "/openai/" in endpoint:
        st.error(f"[config] Endpoint suspeito: {endpoint}. Use apenas a raiz (ex: https://seu-recurso.openai.azure.com/)")
        return {}

    return config

# Carrega a configuração
config = load_config()

if not config:
    st.warning("⚠️ Configure as credenciais do Azure OpenAI no seu ficheiro `.env` para iniciar o chat.")
else:
    api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2025-04-01-preview").strip()
    
    try:
        # Remove variáveis de proxy do ambiente para evitar conflitos no SDK
        for var in ["http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"]:
            os.environ.pop(var, None)

        client = AzureOpenAI(
            azure_endpoint=config["AZURE_OPENAI_ENDPOINT"],
            api_key=config["AZURE_OPENAI_API_KEY"],
            api_version=api_version,
            timeout=30.0,
        )
    except Exception as e:
        st.error(f"Erro ao inicializar cliente AzureOpenAI: {e}")
        st.stop()

    # Definição das ferramentas (Tools) mapeadas para o Agente
    tools = [
        {
            "type": "function",
            "function": {
                "name": "consultar_estoque",
                "description": "Consulta o estoque de um livro específico na livraria pelo seu ID.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "item_id": {
                            "type": "integer",
                            "description": "O ID numérico do livro no banco de dados."
                        }
                    },
                    "required": ["item_id"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "reservar_produto",
                "description": "Realiza a reserva de uma quantidade específica de um livro no estoque.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "item_id": {
                            "type": "integer",
                            "description": "O ID numérico do livro."
                        },
                        "quantidade": {
                            "type": "integer",
                            "description": "A quantidade de unidades a serem reservadas."
                        }
                    },
                    "required": ["item_id", "quantidade"]
                }
            }
        }
    ]

    # Gerenciamento do histórico do chat no Streamlit
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {"role": "system", "content": "Você é o BookBot, um assistente virtual inteligente especializado em gerenciar o inventário de uma livraria. Use sempre as ferramentas disponíveis para consultar ou reservar livros quando solicitado pelo usuário."}
        ]

    # Exibe as mensagens anteriores na interface
    for message in st.session_state.messages:
        if message["role"] != "system":
            with st.chat_message(message["role"]):
                content = message.get("content")
                if content:
                    st.markdown(content)

    # Caixa de entrada do usuário
    if prompt_usuario := st.chat_input("Digite sua mensagem (ex: Consulte o estoque do livro ID 1):"):
        st.session_state.messages.append({"role": "user", "content": prompt_usuario})
        with st.chat_message("user"):
            st.markdown(prompt_usuario)

        with st.chat_message("assistant"):
            with st.spinner("O Agente está a pensar..."):
                try:
                    # Primeira chamada ao Azure OpenAI passando as tools
                    response = client.chat.completions.create(
                        model=config["AZURE_OPENAI_DEPLOYMENT"],
                        messages=st.session_state.messages,
                        tools=tools,
                        tool_choice="auto",
                        max_completion_tokens=256,
                    )
                    
                    response_message = response.choices[0].message
                    tool_calls = response_message.tool_calls

                    # Verifica se o modelo decidiu chamar alguma função
                    if tool_calls:
                        st.session_state.messages.append(response_message)
                        
                        for tool_call in tool_calls:
                            function_name = tool_call.function.name
                            function_args = json.loads(tool_call.function.arguments)
                            
                            st.info(f"🛠️ **Ferramenta acionada pelo Azure:** `{function_name}` com argumentos `{function_args}`")

                            # Executa a função correspondente no SQLite
                            if function_name == "consultar_estoque":
                                function_response = consultar_estoque(item_id=function_args.get("item_id"))
                            elif function_name == "reservar_produto":
                                function_response = reservar_produto(
                                    item_id=function_args.get("item_id"),
                                    quantidade=function_args.get("quantidade")
                                )
                            else:
                                function_response = {"erro": "Função não encontrada"}

                            # Adiciona a resposta da ferramenta ao histórico
                            st.session_state.messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "content": json.dumps(function_response)
                            })

                        # Segunda chamada para o Azure OpenAI gerar a resposta final formatada
                        second_response = client.chat.completions.create(
                            model=config["AZURE_OPENAI_DEPLOYMENT"],
                            messages=st.session_state.messages,
                            max_completion_tokens=256,
                        )
                        
                        final_reply = second_response.choices[0].message.content
                        st.markdown(final_reply)
                        st.session_state.messages.append({"role": "assistant", "content": final_reply})

                    else:
                        final_reply = response_message.content
                        st.markdown(final_reply)
                        st.session_state.messages.append({"role": "assistant", "content": final_reply})

                except Exception as e:
                    st.error(f"Erro na comunicação com o Azure OpenAI: {e}")