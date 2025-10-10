# -*- coding: utf-8 -*-
"""
Sistema de Projetos - Streamlit (Versão Final com Login Alinhado e Segurança Aprimorada)
@author: flavio.ribeiro
"""

import streamlit as st
import pandas as pd
from pymongo import MongoClient
from datetime import datetime
import plotly.express as px
from PIL import Image
import io
import hashlib
import bcrypt # Importar a biblioteca bcrypt
import logging # Importar a biblioteca de logging

# Configurar o logger (pode ser feito uma vez no início da aplicação)
logging.basicConfig(filename="app_errors.log", level=logging.ERROR,
                    format="%(asctime)s - %(levelname)s - %(message)s")

# =============================================================================
# DEFINIÇÃO DE TODAS AS FUNÇÕES (SEÇÃO ÚNICA)
# =============================================================================

# --- Funções de Login e Autenticação ---
def hash_password(password):
    """Gera um hash bcrypt para a senha fornecida."""
    # Gerar um salt aleatório e hash da senha
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    return hashed.decode("utf-8") # Armazenar como string UTF-8

def check_credentials(username, password):
    """Verifica as credenciais e retorna a 'role' do usuário em caso de sucesso."""
    try:
        users = st.secrets["usuarios"]
        for user_info in users.values():
            if user_info.get("username") == username:
                # Verificar a senha usando bcrypt
                # A senha armazenada em st.secrets["usuarios"] deve ser o hash bcrypt
                if bcrypt.checkpw(password.encode("utf-8"), user_info.get("password").encode("utf-8")):
                    return user_info.get("role")
        # Retorna None se o usuário ou a senha estiverem incorretos.
        return None
    except Exception as e:
        logging.error(f"Erro ao verificar credenciais: {e}") # Logar o erro
        st.error("Ocorreu um erro ao verificar as credenciais. Tente novamente.") # Mensagem genérica
        return None

# --- Funções de Conexão com o Banco de Dados ---
@st.cache_resource
def get_mongo_collection(collection_key_name):
    """Função única para conectar e retornar uma coleção específica."""
    try:
        connection_string = st.secrets["mongo"]["uri"]
        client = MongoClient(connection_string, serverSelectionTimeoutMS=20000)
        client.admin.command("ping")
        
        db_name = st.secrets["mongo"]["database"]
        db = client[db_name]
        
        collection_name = st.secrets["mongo"][collection_key_name]
        return db[collection_name]

    except Exception as e:
        logging.error(f"Erro ao conectar ao MongoDB: {e}") # Logar o erro
        st.error("Falha na conexão com o serviço. Por favor, tente novamente mais tarde.") # Mensagem genérica
        return None

# --- Funções de Manipulação e Carga de Dados ---
@st.cache_data(ttl=10)
def carregar_dados():
    """Carrega os dados da coleção do MongoDB para um DataFrame."""
    projetos_col = get_mongo_collection("collection_projetos")
    if projetos_col is None:
        return pd.DataFrame()

    df = pd.DataFrame(list(projetos_col.find()))
    if "_id" in df.columns: df.drop(columns=["_id"], inplace=True)
    if "Link_dos_Arquivos" not in df.columns: df["Link_dos_Arquivos"] = ""
    colunas_numericas = ["Budget","Baseline","Melhor_Proposta","Preco_Inicial","Preco_Final","Saving_R$","Percent_Saving","CE_Baseline_R$","Percent_CE_Baseline","CE_R$","Percent_CE","Dias","Progresso_Percent"]
    for col in colunas_numericas:
        if col in df.columns: 
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    colunas_data = ["Data_Inicio","Data_Termino"]
    for col in colunas_data:
        if col in df.columns: df[col] = pd.to_datetime(df[col], errors="coerce")
    return df

def filtrar_df(df, status_fil, area_fil, resp_fil, cat_fil, desc_fil):
    """Aplica os filtros selecionados ao DataFrame."""
    df_f = df.copy()
    if status_fil != "Todos": df_f = df_f[df_f["Status"]==status_fil]
    if area_fil != "Todos": df_f = df_f[df_f["Area_Setor"]==area_fil]
    if resp_fil != "Todos": df_f = df_f[df_f["Responsavel"]==resp_fil]
    if cat_fil != "Todos": df_f = df_f[df_f["Categoria"]==cat_fil]
    if desc_fil and "Atividades_Descricao" in df_f.columns: df_f = df_f[df_f["Atividades_Descricao"].str.contains(desc_fil,case=False,na=False)]
    return df_f

def gerar_novo_numero():
    """Gera um novo ID de projeto sequencial."""
    projetos_col = get_mongo_collection("collection_projetos")
    if projetos_col is None or projetos_col.count_documents({}) == 0: 
        return 1
    
    numeros = [int(doc["ID_Projeto"][4:]) for doc in projetos_col.find({},{"ID_Projeto":1}) if str(doc.get("ID_Projeto","")).startswith("PROJ")]
    return max(numeros) + 1 if numeros else 1

# --- Funções de Formatação e Cálculo ---
def formatar_moeda(valor):
    if pd.isna(valor) or valor is None: return "R$ 0,00"
    return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def formatar_percentual(valor):
    if pd.isna(valor) or valor is None: return "0,00%"
    return f"{float(valor):.2f}%".replace(".", ",")

def convert_df_to_excel(df):
    output = io.BytesIO()
    for col in df.select_dtypes(include=["datetimetz"]).columns:
        df[col] = df[col].dt.tz_localize(None)
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Dados")
    return output.getvalue()

def calcular_kpis_financeiros(tem_budget, tem_baseline, budget, baseline, melhor_proposta, preco_inicial, preco_final):
    saving_r, percent_saving, ce_baseline_r, percent_ce_baseline, ce_r, percent_ce = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
    if tem_budget:
        saving_r = budget - melhor_proposta
        if melhor_proposta > 0: percent_saving = (saving_r / melhor_proposta) * 100
    if tem_baseline:
        ce_baseline_r = baseline - melhor_proposta
        if melhor_proposta > 0: percent_ce_baseline = (ce_baseline_r / melhor_proposta) * 100
    ce_r = preco_inicial - preco_final
    if preco_final > 0: percent_ce = (ce_r / preco_final) * 100
    return {"Saving_R$": saving_r, "Percent_Saving": percent_saving, "CE_Baseline_R$": ce_baseline_r, "Percent_CE_Baseline": percent_ce_baseline, "CE_R$": ce_r, "Percent_CE": percent_ce}

def format_valor_kpi(valor):
    if pd.isna(valor) or valor is None: return "R$ 0,00"
    valor = float(valor)
    if valor >= 1_000_000: return f"R$ {valor/1_000_000:.2f}M"
    if valor >= 1_000: return f"R$ {valor/1_000:.2f}K"
    return formatar_moeda(valor)

# =============================================================================
# INÍCIO DA EXECUÇÃO DO SCRIPT
# =============================================================================

st.set_page_config(page_title="Sistema de Projetos", layout="wide")

if "login_realizado" not in st.session_state:
    st.session_state["login_realizado"] = False
if "usuario_logado" not in st.session_state:
    st.session_state["usuario_logado"] = ""

# --- TELA DE LOGIN ---
if not st.session_state["login_realizado"]:
    col1_ext, col2_ext, col3_ext = st.columns([1,1,1]) # Colunas externas para centralizar
    with col2_ext: # Usamos col2_ext para centralizar o conteúdo
        
        # Criamos colunas INTERNAS para a imagem e o título
        img_col, title_col = st.columns([0.4, 0.6]) # Proporções: 40% para imagem, 60% para título
        
        with img_col:
            try:
                st.image(Image.open("Imagem_adm.png"), width=150) # Tamanho da imagem
            except FileNotFoundError:
                st.warning("Imagem 'Imagem_adm.png' não encontrada.")
        
        with title_col:
            # CSS para alinhar verticalmente o título com a imagem
            st.markdown("""
                <style>
                .vertical-align {
                    display: flex;
                    align-items: center;
                    height: 150px; /* Mesma altura ou um pouco mais que a imagem */
                }
                </style>
                <div class="vertical-align">
                    <h1 style=\'color: #002776;\'>Sistema de Projetos</h1>
                </div>
            """, unsafe_allow_html=True)
        
        st.markdown("---") # Linha divisória
        
        username = st.text_input("Usuário", key="login_user")
        password = st.text_input("Senha", type="password", key="login_pass")
        
        if st.button("Entrar", use_container_width=True):
            with st.spinner("Verificando credenciais..."):
                if check_credentials(username, password):
                    st.session_state["login_realizado"] = True
                    st.session_state["usuario_logado"] = username
                    st.rerun()
                else:
                    st.error("Usuário ou senha inválidos.")
# --- APLICAÇÃO PRINCIPAL ---
else:
    with st.spinner("Conectando ao banco de dados..."):
        if get_mongo_collection("collection_projetos") is None:
            st.sidebar.error("❌ Falha na conexão")
            st.stop()
        else:
            st.sidebar.success("✅ Conectado")

    df = carregar_dados()
    
    status_options = ["Á Iniciar","Em andamento","Atrasado","Concluído","Stand By","Cancelado"]
    empresas_options = ["Postos Gulf","Alpha Matrix","Am Gestao Filz","Am Gestao Mtz","Bcag Sp 0002","Carneiros Go","Carinthia Rj 01","Carinthia Rj 03","Churchill","Clio","Direcional Es","Direcional Fil","Direcional Mt","Direcional Sp","Estrela","Fatro","Fair Energy","Fera Rj","Fera Sp","Fit Marine","Fit Marine Filial","Fit Marine Matriz","Fitfiber","Flagler Go","Flagler Rj","Flagler Sp","Gooil Hub","Gooil","Logfit Filial Aruja","Logfit Filial Caxias","Logfit Filial Rj","Logfit Rj 0002","Logfit Rj 0004","Logfit Sp 0001","Logfit Sp 0006","Logfit Tms Filial","Magro Adv Fil","Magro Adv Matriz","Manguinhos Fil","Manguinhos Filial","Manguinhos Matriz","Manguinhos Mtz","Maximus To","Ornes Gestao","Paradise Td 0001","Petro Go 0006","Petro Rj 0006","Petro Rj 0007","Petro To 0001","Petro To 0004","Port Brazil","Refit Filial Alagoas","Refit Filial Amapa","Refit Matriz","Renomeada 57","Renomeada 61","Renomeada 62","Renomeada 65","Renomeada 66","Roar Fl 0003","Roar Rj 0004","Roar Matriz","Rodopetro Cn","Rodopetro Mtz","Rodopetro Rj Dc","Tiger Matriz","Tig","Uma Cidadania","Valsinha","Vascam","Xyz Sp","Yield Filial","Yield Matriz"]

    st.markdown("""
    <style>
    [data-testid="stSidebar"] { background-color: #002776; }
    .sidebar-radio-title { color: white !important; font-weight: bold; font-size: 16px; }
    [data-testid="stSidebar"] div[role="radiogroup"] label p { color: white !important; }
    </style>
    """, unsafe_allow_html=True)

    c1, c2, c3 = st.columns([1, 6, 2])
    with c1:
        try: c1.image(Image.open("Imagem_adm.png"), width=100)
        except: pass
    c2.markdown("<h1 style=\'color:#002776; text-align:center;font-size:38px; font-weight:bold;\'>Monitoramento de Projetos</h1>", unsafe_allow_html=True)
    c3.markdown(f"**👤 Usuário:** {st.session_state.usuario_logado}")

    aba = st.sidebar.radio("Escolha uma opção:",["Dashboard","Cadastrar Projeto","Atualizar Projeto"])

    with st.sidebar.expander("Filtros", expanded=True):
        if df.empty:
            st.warning("Não há dados para filtrar.")
            status_fil, area_fil, resp_fil, cat_fil, desc_fil = "Todos", "Todos", "Todos", "Todos", ""
        else:
            status_fil = st.selectbox("Status", ["Todos"] + sorted(df["Status"].dropna().unique()), key="f_status")
            area_fil = st.selectbox("Área/Setor", ["Todos"] + sorted(df["Area_Setor"].dropna().unique()), key="f_area")
            resp_fil = st.selectbox("Responsável", ["Todos"] + sorted(df["Responsavel"].dropna().unique()), key="f_resp")
            cat_fil = st.selectbox("Categoria", ["Todos"] + sorted(df["Categoria"].dropna().unique()), key="f_cat")
            desc_fil = st.text_input("Descrição (contém)", key="f_desc")
    
    st.sidebar.write("---")
    if st.sidebar.button("Sair", use_container_width=True):
        st.session_state["login_realizado"] = False
        st.session_state["usuario_logado"] = ""
        st.rerun()

    df_filtrado = filtrar_df(df, status_fil, area_fil, resp_fil, cat_fil, desc_fil)

    if aba == "Dashboard":
        st.markdown("<h2 style=\'font-size: 28px; text-align: center;\'>📊 Dashboard de Projetos</h2>", unsafe_allow_html=True)

        if not df_filtrado.empty and "Status" in df_filtrado.columns:
            status_counts = df_filtrado["Status"].value_counts()
            qtd_total = len(df_filtrado)
            qtd_concluidos = status_counts.get("Concluído", 0)
            qtd_em_andamento = status_counts.get("Em andamento", 0)
            qtd_cancelados = status_counts.get("Cancelado", 0)
            
            soma_valor_total = pd.to_numeric(df_filtrado["Preco_Final"], errors="coerce").sum() + \
                               pd.to_numeric(df_filtrado["Melhor_Proposta"], errors="coerce").sum()
            
            soma_total_ce = pd.to_numeric(df_filtrado["Saving_R$"], errors="coerce").sum() + \
                            pd.to_numeric(df_filtrado["CE_R$"], errors="coerce").sum() + \
                            pd.to_numeric(df_filtrado["CE_Baseline_R$"], errors="coerce").sum()
        else:
            qtd_total = qtd_concluidos = qtd_em_andamento = qtd_cancelados = soma_valor_total = soma_total_ce = 0
            
        card_cols = st.columns(6)
        cards = [("Qtd Total", qtd_total, "#002776"), ("Cancelados", qtd_cancelados, "#D90429"), ("Concluídos", qtd_concluidos, "#2B9348"), ("Em Andamento", qtd_em_andamento, "#F2C94C"), ("Valor Total", format_valor_kpi(soma_valor_total), "#17a2b8"), ("Total C.E.", format_valor_kpi(soma_total_ce), "#17a2b8")]
        for col, (titulo, valor, cor) in zip(card_cols, cards):
            col.markdown(f\'\n<div style="background-color:{cor};padding:20px;border-radius:15px;text-align:center;height:120px;display:flex;flex-direction:column;justify-content:center;"><h3 style="color:white;margin:0 0 8px 0;font-size:16px;">{titulo}</h3><h2 style="color:white;margin:0;font-size:20px;font-weight:bold;">{valor}</h2></div>\n\', unsafe_allow_html=True)

        st.markdown("<hr>", unsafe_allow_html=True)

        if not df_filtrado.empty:
            paleta = [\'#F2C94C\', \'#2B9348\', \'#3596B5\', \'#9BAEBC\', \'#E74C3C\', \'#5D6D7E\']
            if "Status" in df_filtrado and not df_filtrado["Status"].empty:
                status_counts = df_filtrado["Status"].value_counts().reset_index()
                status_counts.columns = ["Status", "Quantidade"]
                fig_status = px.bar(status_counts, x="Status", y="Quantidade", color="Status", color_discrete_sequence=paleta, text_auto=True, title="Quantidade de Projetos por Status")
                fig_status.update_traces(textposition="outside")
                max_val = status_counts["Quantidade"].max() if not status_counts.empty else 1
                fig_status.update_yaxes(tickmode="linear", dtick=1, range=[0, max_val * 1.15])
                st.plotly_chart(fig_status, use_container_width=True)

            if "Responsavel" in df_filtrado and not df_filtrado["Responsavel"].dropna().empty:
                resp_counts = df_filtrado["Responsavel"].value_counts().reset_index()
                resp_counts.columns = ["Responsavel", "Quantidade"]
                fig_resp = px.bar(resp_counts, x="Responsavel", y="Quantidade", color="Quantidade", color_continuous_scale="Blues", text_auto=True, title="Quantidade de Projetos por Responsável")
                fig_resp.update_traces(textposition="outside")
                max_val = resp_counts["Quantidade"].max() if not resp_counts.empty else 1
                fig_resp.update_yaxes(tickmode="linear", dtick=1, range=[0, max_val * 1.15])
                st.plotly_chart(fig_resp, use_container_width=True)

        st.markdown("<hr>", unsafe_allow_html=True)
        df_gantt = df_filtrado.dropna(subset=["Data_Inicio", "Data_Termino"]).copy()
        
        if df_gantt.empty:
            st.info("Nenhum projeto com datas de início e término para exibir no cronograma.")
        else:
            mapa_de_cores = {"Concluído": "#28B463", "Em andamento": "#3498DB", "Á Iniciar": "#F39C12", "Atrasado": "#E74C3C", "Cancelado": "#85929E", "Stand By": "#5D6D7E"}
            df_gantt = df_gantt.sort_values(by="Data_Inicio")
            fig = px.timeline(df_gantt, x_start="Data_Inicio", x_end="Data_Termino", y="Atividades_Descricao", color="Status", color_discrete_map=mapa_de_cores, title="Linha do Tempo dos Projetos (Gráfico de Gantt)", hover_data=["Responsavel", "Atividades_Descricao", "Status"])
            fig.update_yaxes(categoryorder="total ascending")
            
            hoje_str = pd.Timestamp.now().strftime("%Y-%m-%d")
            fig.add_vline(x=hoje_str, line_width=2, line_dash="dash", line_color="grey")

            fig.add_annotation(
                x=hoje_str,
                y=1,
                yref="paper",
                text="Hoje",
                showarrow=False,
                yshift=10,
                font=dict(color="grey")
            )
            st.plotly_chart(fig, use_container_width=True)
