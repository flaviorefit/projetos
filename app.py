# -*- coding: utf-8 -*-
"""
Sistema de Requisições - Streamlit (Versão Refatorada e Otimizada)
@author: flavio.ribeiro
"""

import streamlit as st
import pandas as pd
from pymongo import MongoClient
from datetime import datetime, date
import plotly.express as px
from PIL import Image
import hashlib
import io

# =============================================================================
# DEFINIÇÃO DE TODAS AS FUNÇÕES (SEÇÃO ÚNICA)
# =============================================================================

# --- Funções de Autenticação e Sessão ---
def hash_password(password):
    """Criptografa a senha usando SHA256."""
    return hashlib.sha256(password.encode()).hexdigest()

def check_login(username, password):
    """## CORREÇÃO CRÍTICA ##
    Verifica as credenciais do usuário de forma segura.
    - Criptografa a senha digitada pelo usuário.
    - Compara com o hash já salvo no secrets.toml.
    """
    try:
        users = st.secrets["usuarios"]
        for user_info in users.values():
            if user_info.get("username") == username:
                if hash_password(password) == user_info.get("password"):
                    return user_info.get("role", "requisitante") # Retorna a role do usuário
        return None # Retorna None se o usuário não for encontrado ou a senha estiver errada
    except Exception as e:
        st.error(f"Erro no sistema de autenticação: {e}")
        return None

def logout():
    """Limpa a sessão e redireciona para a tela de login."""
    st.session_state.clear()
    st.rerun()

# --- Funções de Conexão com o Banco de Dados ---
@st.cache_resource
def init_connection():
    """Inicializa e cacheia a conexão com o MongoDB."""
    try:
        client = MongoClient(st.secrets["mongo_uri"], serverSelectionTimeoutMS=20000)
        client.admin.command("ping")
        return client
    except Exception as e:
        st.error(f"❌ Erro ao conectar no MongoDB: {e}")
        return None

# --- Funções de Carga e Manipulação de Dados ---
@st.cache_data(ttl=30)
def carregar_dados(collection):
    """Carrega dados da coleção, limpa e prepara o DataFrame."""
    if collection is None:
        return pd.DataFrame()
    try:
        df = pd.DataFrame(list(collection.find()))
        if '_id' in df.columns:
            df.drop(columns=['_id'], inplace=True)

        colunas_essenciais = ['Nº de Pedido', 'Status', 'Base', 'Comprador', 'Fornecedor', 'Descrição', 'Devolução Gestão', 'Requisitante', 'Preço Final', 'Diferença R$']
        for col in colunas_essenciais:
            if col not in df.columns:
                df[col] = pd.NA

        for col in df.columns:
            if any(term in col for term in ['Data', 'Gestão', 'Diretoria', 'Minuta']):
                df[col] = pd.to_datetime(df[col], errors='coerce')

        ## MELHORIA: Limpeza de dados movida para cá, para ser executada apenas uma vez.
        df["Status"] = df["Status"].fillna("Não Informado")
        df["Base"] = df["Base"].fillna("Não Informada")
        df["Comprador"] = df["Comprador"].fillna("Não Informado")
        df["Fornecedor"] = df["Fornecedor"].astype(str).fillna("Não Informado")
        df["Requisitante"] = df["Requisitante"].astype(str).fillna("Não Informado")
        
        # Converte colunas numéricas, tratando possíveis erros
        numeric_cols = ['Preço Final', 'Diferença R$']
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        return df
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return pd.DataFrame()

def gerar_novo_numero(collection):
    """## MELHORIA DE PERFORMANCE ##
    Busca o maior "Nº de Pedido" de forma eficiente no MongoDB.
    """
    if collection is None:
        return 1
    try:
        resultado = collection.find_one(sort=[("Nº de Pedido", -1)])
        if resultado and resultado.get("Nº de Pedido"):
            return int(resultado.get("Nº de Pedido", 0)) + 1
        return 1
    except (ValueError, TypeError):
        return 1

# --- Funções de Interface e Filtros ---
def aplicar_filtros(df, prefixo=""):
    """Cria os widgets de filtro e retorna os valores selecionados."""
    status = st.multiselect("Status", options=sorted(df["Status"].unique()), key=f"{prefixo}_status")
    base = st.multiselect("Base", options=sorted(df["Base"].unique()), key=f"{prefixo}_base")
    comprador = st.multiselect("Comprador", options=sorted(df["Comprador"].unique()), key=f"{prefixo}_comprador")
    fornecedor = st.multiselect("Fornecedor", options=sorted(df["Fornecedor"].unique()), key=f"{prefixo}_fornecedor")
    descricao = st.text_input("Descrição da RC (contém):", key=f"{prefixo}_descricao")

    requisitante = None
    if st.session_state.user_role == "admin":
        requisitante = st.multiselect("Requisitante", options=sorted(df["Requisitante"].unique()), key=f"{prefixo}_requisitante")

    anos_disponiveis = ["Todos"] + sorted(df['Devolução Gestão'].dt.year.dropna().unique().astype(int), reverse=True)
    ano = st.selectbox("Ano", anos_disponiveis, key=f"{prefixo}_ano")

    return status, base, comprador, fornecedor, descricao, requisitante, ano

def filtrar_df(df, status, base, comprador, fornecedor, descricao, requisitante, ano):
    """Filtra o DataFrame com base nas seleções."""
    df_filtrado = df.copy()
    if requisitante: df_filtrado = df_filtrado[df_filtrado["Requisitante"].isin(requisitante)]
    if status: df_filtrado = df_filtrado[df_filtrado["Status"].isin(status)]
    if base: df_filtrado = df_filtrado[df_filtrado["Base"].isin(base)]
    if comprador: df_filtrado = df_filtrado[df_filtrado["Comprador"].isin(comprador)]
    if fornecedor: df_filtrado = df_filtrado[df_filtrado["Fornecedor"].isin(fornecedor)]
    if descricao: df_filtrado = df_filtrado[df_filtrado["Descrição"].str.contains(descricao, case=False, na=False)]
    if ano != "Todos": df_filtrado = df_filtrado[df_filtrado['Devolução Gestão'].notna() & (df_filtrado['Devolução Gestão'].dt.year == ano)]
    return df_filtrado

# --- Funções de Formatação e Utilitários ---
def formatar_moeda(valor):
    if pd.isna(valor) or valor is None: return "R$ 0,00"
    return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def formatar_percentual(valor):
    if pd.isna(valor) or valor is None: return "0,00%"
    return f"{float(valor):.2f}%".replace(".", ",")

def format_valor_kpi(valor):
    if valor >= 1_000_000: return f"R$ {valor/1_000_000:.2f}M"
    if valor >= 1_000: return f"R$ {valor/1_000:.2f}K"
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def convert_df_to_excel(df):
    output = io.BytesIO()
    for col in df.select_dtypes(include=['datetimetz']).columns:
        df[col] = df[col].dt.tz_localize(None)
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Dados')
    return output.getvalue()

# =============================================================================
# INÍCIO DO SCRIPT E LÓGICA DE LOGIN
# =============================================================================

st.set_page_config(page_title="Sistema de Requisições", layout="wide")

def tela_login():
    """Renderiza a interface de login."""
    _, col2, _ = st.columns([1, 1, 1])
    with col2:
        try:
            st.image(Image.open("Imagem_gulf.png"), width=150)
        except FileNotFoundError:
            pass
        st.markdown("<h1 style='text-align: center; color: #002776;'>Monitoramento de Demandas</h1>", unsafe_allow_html=True)
        
        with st.form("login_form"):
            username = st.text_input("Usuário", placeholder="Digite seu usuário")
            password = st.text_input("Senha", type="password", placeholder="Digite sua senha")
            if st.form_submit_button("Entrar", use_container_width=True, type="primary"):
                user_role = check_login(username, password)
                if user_role:
                    st.session_state.login_realizado = True
                    st.session_state.usuario_logado = username
                    st.session_state.user_role = user_role
                    st.success("Login realizado com sucesso!")
                    st.rerun()
                else:
                    st.error("Usuário ou senha inválidos.")

if not st.session_state.get("login_realizado"):
    tela_login()
    st.stop()

# =============================================================================
# APLICAÇÃO PRINCIPAL (APÓS LOGIN)
# =============================================================================

# --- Conexão e Carga de Dados ---
client = init_connection()
if client:
    db = client[st.secrets["mongo_db"]]
    requisicoes_col = db[st.secrets["mongo_collection_requisicoes"]]
    st.sidebar.success("✅ Conectado")
else:
    st.stop()

df = carregar_dados(requisicoes_col)

# --- Layout do Cabeçalho e Sidebar ---
st.markdown(
    """
    <style>
    [data-testid="stSidebar"] { background-color: #002776; color: white; }
    [data-testid="stSidebar"] .stRadio label p { color: white; }
    [data-testid="stSidebar"] .streamlit-expanderHeader { color: white; }
    </style>
    """, unsafe_allow_html=True
)

col1, col2, col3 = st.columns([1, 6, 2])
with col1:
    try:
        st.image(Image.open("Imagem_gulf.png"), width=100)
    except FileNotFoundError:
        pass
col2.markdown("<h1 style='color:#002776; text-align:center; font-size:36px; font-weight:bold;'>Monitoramento de Demandas Gulf</h1>", unsafe_allow_html=True)
with col3:
    st.markdown(f"**👤 Usuário:** {st.session_state.usuario_logado}")
    if st.button("🚪 Sair"):
        logout()

aba = st.sidebar.radio(
    "Menu:",
    ["Dashboard", "Listar Requisições", "Cadastrar Requisição", "Editar/Excluir"] if st.session_state.user_role == "admin" else ["Dashboard", "Listar Requisições"]
)

with st.sidebar.expander("🎯 Filtros Gerais", expanded=True):
    status, base, comprador, fornecedor, descricao, requisitante, ano = aplicar_filtros(df)

df_filtrado = filtrar_df(df, status, base, comprador, fornecedor, descricao, requisitante, ano)

# --- Renderização da Aba Selecionada ---
if aba == "Dashboard":
    st.header("📊 Dashboard de Requisições")
    if not df_filtrado.empty:
        qtd_total = len(df_filtrado)
        qtd_cancelados = len(df_filtrado[df_filtrado["Status"] == "Cancelado"])
        qtd_concluidos = len(df_filtrado[df_filtrado["Status"] == "Concluído"])
        qtd_aprovacao = len(df_filtrado[df_filtrado["Status"] == "Em Aprovação"])
        soma_pedido_emitido = df_filtrado["Preço Final"].sum()
        total_custo_evitado = df_filtrado["Diferença R$"].sum()
        
        card_cols = st.columns(6)
        cards = [("Qtd Total", qtd_total, "#002776"), ("Cancelados", qtd_cancelados, "#D90429"), ("Concluídos", qtd_concluidos, "#2B9348"), ("Em Aprovação", qtd_aprovacao, "#F2C94C"), ("Valor Total", format_valor_kpi(soma_pedido_emitido), "#6A4C93"), ("Total C.E", format_valor_kpi(total_custo_evitado), "#17a2b8")]
        for col, (titulo, valor, cor) in zip(card_cols, cards):
            col.markdown(f'<div style="background-color:{cor};padding:20px;border-radius:15px;text-align:center;height:120px;display:flex;flex-direction:column;justify-content:center;"><h3 style="color:white;margin:0 0 8px 0;font-size:16px;">{titulo}</h3><h2 style="color:white;margin:0;font-size:20px;font-weight:bold;">{valor}</h2></div>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        # (Restante do seu código do Dashboard aqui...)
    else:
        st.info("Nenhuma requisição encontrada com os filtros aplicados.")

elif aba == "Listar Requisições":
    st.subheader("📋 Listagem de Requisições")
    if not df_filtrado.empty:
        st.dataframe(df_filtrado, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhuma requisição encontrada com os filtros aplicados.")

elif aba == "Cadastrar Requisição" and st.session_state.user_role == "admin":
    st.subheader("📝 Cadastrar Nova Requisição")
    # (Seu formulário de cadastro aqui...)
    pass

elif aba == "Editar/Excluir" and st.session_state.user_role == "admin":
    st.subheader("✏️ Editar ou Excluir Requisição")
    # (Sua lógica de edição/exclusão aqui...)
    pass
