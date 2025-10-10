# -*- coding: utf-8 -*-
"""
Sistema de Projetos - Streamlit (Versão com Cálculos de Card Ajustados)
@author: flavio.ribeiro
"""

import streamlit as st
import pandas as pd
from pymongo import MongoClient
from datetime import datetime
import plotly.express as px
from PIL import Image
import io
import hashlib  ## NOVO ## - Biblioteca para criptografar a senha

# =======================
# FUNÇÕES AUXILIARES E DE LOGIN ## AJUSTE ##
# =======================

## NOVO ## - Função para verificar as credenciais
def check_credentials(username, password):
    """Verifica se o usuário e a senha correspondem aos dados em secrets.toml."""
    try:
        # Pega a lista de usuários do arquivo de segredos
        users = st.secrets["usuarios"]
        
        # Procura pelo usuário na lista
        for user_key in users:
            user_data = users[user_key]
            if user_data["username"] == username:
                # Criptografa a senha digitada para comparar com a senha armazenada
                hashed_password = hashlib.sha256(password.encode()).hexdigest()
                if hashed_password == user_data["password"]:
                    return True # Credenciais corretas
        return False # Usuário não encontrado ou senha incorreta
    except Exception as e:
        st.error(f"Erro ao verificar credenciais: {e}")
        return False

def formatar_moeda(valor):
    if pd.isna(valor) or valor is None:
        return "R$ 0,00"
    valor_float = float(valor)
    return f"R$ {valor_float:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def formatar_percentual(valor):
    if pd.isna(valor) or valor is None:
        return "0,00%"
    valor_float = float(valor)
    return f"{valor_float:.2f}%".replace(".", ",")

def convert_df_to_excel(df):
    output = io.BytesIO()
    for col in df.select_dtypes(include=['datetimetz']).columns:
        df[col] = df[col].dt.tz_localize(None)
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Dados')
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

# =======================
# CONFIGURAÇÃO PÁGINA
# =======================
st.set_page_config(page_title="Sistema de Projetos", layout="wide")

# =======================
# SESSION STATE ## AJUSTE ##
# =======================
# Inicia o estado de login como Falso. O app vai sempre começar na tela de login.
if "login_realizado" not in st.session_state:
    st.session_state["login_realizado"] = False
if "usuario_logado" not in st.session_state:
    st.session_state["usuario_logado"] = ""


# =======================
# TELA DE LOGIN ## NOVO ##
# =======================
if not st.session_state["login_realizado"]:
    col1, col2, col3 = st.columns([1,1,1])
    with col2:
        st.markdown("<h1 style='text-align: center; color: #002776;'>Sistema de Projetos</h1>", unsafe_allow_html=True)
        try:
            st.image(Image.open("Imagem_gulf.png"))
        except:
            st.warning("Imagem 'Imagem_gulf.png' não encontrada.")
        
        username = st.text_input("Usuário", key="login_user")
        password = st.text_input("Senha", type="password", key="login_pass")
        
        if st.button("Entrar", use_container_width=True):
            if check_credentials(username, password):
                st.session_state["login_realizado"] = True
                st.session_state["usuario_logado"] = username
                st.rerun() # Roda o script novamente para mostrar a aplicação principal
            else:
                st.error("Usuário ou senha inválidos.")
else:
    # =============================================================================
    # APLICAÇÃO PRINCIPAL (SÓ RODA DEPOIS DO LOGIN)
    # =============================================================================

    # =======================
    # SIDEBAR E ESTILOS GERAIS
    # =======================
    st.markdown("""
    <style>
    [data-testid="stSidebar"] { background-color: #002776; }
    .sidebar-radio-title { color: white !important; font-weight: bold; font-size: 16px; }
    [data-testid="stSidebar"] div[role="radiogroup"] label p { color: white !important; }
    </style>
    """, unsafe_allow_html=True)

    # =======================
    # CABEÇALHO
    # =======================
    col1, col2, col3 = st.columns([1, 6, 2])
    with col1:
        try: st.image(Image.open("Imagem_gulf.png"), width=100)
        except: pass
    with col2: st.markdown("<h1 style='color:#002776; text-align:center;font-size:38px; font-weight:bold;'>Monitoramento de Projetos</h1>", unsafe_allow_html=True)
    with col3: st.markdown(f"**👤 Usuário:** {st.session_state.usuario_logado}")

    # =======================
    # CONEXÃO MONGO
    # =======================
@st.cache_resource
def get_mongo_collection(collection_name):
    """Função única para conectar e retornar uma coleção específica."""
    try:
        # Pega a string de conexão do secrets.toml
        connection_string = st.secrets["mongo"]["mongo_uri"]
        client = MongoClient(connection_string, serverSelectionTimeoutMS=20000)
        
        # Pega o nome do banco de dados do secrets.toml
        db_name = st.secrets["mongo"]["mongo_db"]
        db = client[db_name]
        
        # Retorna a coleção solicitada
        return db[collection_name]

    except Exception as e:
        st.error(f"Erro ao conectar ao MongoDB: {e}")
        return None

# --- Como usar no seu script principal ---

# Pega a coleção de projetos
projetos_col = get_mongo_collection(st.secrets["mongo"]["mongo_collection_projetos"])

if projetos_col is not None:
    st.sidebar.success("✅ Conectado")
    # Agora você já pode usar 'projetos_col' diretamente
    # Ex: df = pd.DataFrame(list(projetos_col.find()))
else:
    st.sidebar.error("❌ Falha na conexão")
    st.stop()

    # =======================
    # CARREGAR DADOS
    # =======================
    @st.cache_data(ttl=10)
    def carregar_dados():
        df = pd.DataFrame(list(projetos_col.find()))
        if '_id' in df.columns: df.drop(columns=['_id'], inplace=True)
        if 'Link_dos_Arquivos' not in df.columns: df['Link_dos_Arquivos'] = ""
        colunas_numericas = ['Budget','Baseline','Melhor_Proposta','Preco_Inicial','Preco_Final','Saving_R$','Percent_Saving','CE_Baseline_R$','Percent_CE_Baseline','CE_R$','Percent_CE','Dias','Progresso_Percent']
        for col in colunas_numericas:
            if col in df.columns: 
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        colunas_data = ['Data_Inicio','Data_Termino']
        for col in colunas_data:
            if col in df.columns: df[col] = pd.to_datetime(df[col], errors='coerce')
        return df
    df = carregar_dados()

    # =======================
    # LISTAS AUXILIARES
    # =======================
    status_options = ["Á Iniciar","Em andamento","Atrasado","Concluído","Stand By","Cancelado"]
    empresas_options = ["Postos Gulf","Alpha Matrix","Am Gestao Filz","Am Gestao Mtz","Bcag Sp 0002","Carneiros Go","Carinthia Rj 01","Carinthia Rj 03","Churchill","Clio","Direcional Es","Direcional Fil","Direcional Mt","Direcional Sp","Estrela","Fatro","Fair Energy","Fera Rj","Fera Sp","Fit Marine","Fit Marine Filial","Fit Marine Matriz","Fitfiber","Flagler Go","Flagler Rj","Flagler Sp","Gooil Hub","Gooil","Logfit Filial Aruja","Logfit Filial Caxias","Logfit Filial Rj","Logfit Rj 0002","Logfit Rj 0004","Logfit Sp 0001","Logfit Sp 0006","Logfit Tms Filial","Magro Adv Fil","Magro Adv Matriz","Manguinhos Fil","Manguinhos Filial","Manguinhos Matriz","Manguinhos Mtz","Maximus To","Ornes Gestao","Paradise Td 0001","Petro Go 0006","Petro Rj 0006","Petro Rj 0007","Petro To 0001","Petro To 0004","Port Brazil","Refit Filial Alagoas","Refit Filial Amapa","Refit Matriz","Renomeada 57","Renomeada 61","Renomeada 62","Renomeada 65","Renomeada 66","Roar Fl 0003","Roar Rj 0004","Roar Matriz","Rodopetro Cn","Rodopetro Mtz","Rodopetro Rj Dc","Tiger Matriz","Tig","Uma Cidadania","Valsinha","Vascam","Xyz Sp","Yield Filial","Yield Matriz"]

    def gerar_novo_numero():
        if projetos_col.count_documents({}) == 0: return 1
        numeros = [int(doc["ID_Projeto"][4:]) for doc in projetos_col.find({},{"ID_Projeto":1}) if str(doc.get("ID_Projeto","")).startswith("PROJ")]
        return max( numeros ) + 1 if numeros else 1

    # =======================
    # MENU LATERAL E FILTROS
    # =======================
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

    def filtrar_df(df):
        df_f = df.copy()
        if status_fil != "Todos": df_f = df_f[df_f["Status"]==status_fil]
        if area_fil != "Todos": df_f = df_f[df_f["Area_Setor"]==area_fil]
        if resp_fil != "Todos": df_f = df_f[df_f["Responsavel"]==resp_fil]
        if cat_fil != "Todos": df_f = df_f[df_f["Categoria"]==cat_fil]
        if desc_fil and "Atividades_Descricao" in df_f.columns: df_f = df_f[df_f["Atividades_Descricao"].str.contains(desc_fil,case=False,na=False)]
        return df_f
    df_filtrado = filtrar_df(df)

    # =======================
    # ABA DASHBOARD
    # =======================
    if aba=="Dashboard":
        st.markdown("<h2 style='font-size: 28px; text-align: center;'>📊 Dashboard de Projetos</h2>", unsafe_allow_html=True)

        if not df_filtrado.empty and "Status" in df_filtrado.columns:
            status_counts = df_filtrado["Status"].value_counts()
            qtd_total = len(df_filtrado)
            qtd_concluidos = status_counts.get("Concluído", 0)
            qtd_em_andamento = status_counts.get("Em andamento", 0)
            qtd_cancelados = status_counts.get("Cancelado", 0)
            soma_valor_total = df_filtrado['Preco_Final'].sum() + df_filtrado['Melhor_Proposta'].sum()
            soma_total_ce = df_filtrado['Saving_R$'].sum() + df_filtrado['CE_R$'].sum() + df_filtrado['CE_Baseline_R$'].sum()
        else:
            qtd_total = qtd_concluidos = qtd_em_andamento = qtd_cancelados = soma_valor_total = soma_total_ce = 0

        card_col1, card_col2, card_col3, card_col4, card_col5, card_col6 = st.columns(6)
        cards = [
            ("Qtd Total", qtd_total, "#002776"), 
            ("Cancelados", qtd_cancelados, "#D90429"), 
            ("Concluídos", qtd_concluidos, "#2B9348"), 
            ("Em Andamento", qtd_em_andamento, "#F2C94C"),
            ("Valor Total", format_valor_kpi(soma_valor_total), "#17a2b8"), 
            ("Total C.E.", format_valor_kpi(soma_total_ce), "#17a2b8")
        ]
        
        for col, (titulo, valor, cor) in zip([card_col1, card_col2, card_col3, card_col4, card_col5, card_col6], cards):
            col.markdown(f'<div style="background-color:{cor};padding:20px;border-radius:15px;text-align:center;height:120px;display:flex;flex-direction:column;justify-content:center;"><h3 style="color:white;margin:0 0 8px 0;font-size:16px;">{titulo}</h3><h2 style="color:white;margin:0;font-size:20px;font-weight:bold;">{valor}</h2></div>', unsafe_allow_html=True)

        st.markdown("<hr>", unsafe_allow_html=True)

        if not df_filtrado.empty:
            paleta = ['#F2C94C', '#2B9348', '#3596B5', '#9BAEBC', '#E74C3C', '#5D6D7E']
            
            if 'Status' in df_filtrado and not df_filtrado['Status'].empty:
                status_counts = df_filtrado['Status'].value_counts().reset_index()
                status_counts.columns = ['Status', 'Quantidade']
                fig_status = px.bar(status_counts, x='Status', y='Quantidade', color='Status', color_discrete_sequence=paleta, text_auto=True, title='Quantidade de Projetos por Status')
                fig_status.update_traces(textposition='outside')
                max_val = status_counts['Quantidade'].max()
                fig_status.update_yaxes(tickmode='linear', dtick=1, range=[0, max_val * 1.15])
                st.plotly_chart(fig_status, use_container_width=True)

            if 'Responsavel' in df_filtrado and not df_filtrado['Responsavel'].dropna().empty:
                resp_counts = df_filtrado['Responsavel'].value_counts().reset_index()
                resp_counts.columns = ['Responsavel', 'Quantidade']
                fig_resp = px.bar(resp_counts, x='Responsavel', y='Quantidade', color='Quantidade', color_continuous_scale='Blues', text_auto=True, title='Quantidade de Projetos por Responsável')
                fig_resp.update_traces(textposition='outside')
                max_val = resp_counts['Quantidade'].max()
                fig_resp.update_yaxes(tickmode='linear', dtick=1, range=[0, max_val * 1.15])
                st.plotly_chart(fig_resp, use_container_width=True)

        st.markdown("<hr>", unsafe_allow_html=True)
        df_gantt = df_filtrado.dropna(subset=['Data_Inicio', 'Data_Termino']).copy()
        
        if df_gantt.empty:
            st.info("Nenhum projeto com datas de início e término para exibir no cronograma.")
        else:
            mapa_de_cores = {'Concluído': '#28B463', 'Em andamento': '#3498DB', 'Á Iniciar': '#F39C12', 'Atrasado': '#E74C3C', 'Cancelado': '#85929E', 'Stand By': '#5D6D7E'}
            df_gantt = df_gantt.sort_values(by='Data_Inicio')
            fig = px.timeline(df_gantt, x_start="Data_Inicio", x_end="Data_Termino", y="Atividades_Descricao", color="Status", color_discrete_map=mapa_de_cores, title="Linha do Tempo dos Projetos (Gráfico de Gantt)", hover_data=["Responsavel", "Atividades_Descricao", "Status"])
            fig.update_yaxes(categoryorder='total ascending')
            fig.add_vline(x=pd.Timestamp.now(), line_width=2, line_dash="dash", line_color="grey", annotation_text="Hoje")
            fig.update_traces(hovertemplate="<br>".join(["<b>%{y}</b>", "<b>Status:</b> %{customdata[2]}", "<b>Responsável:</b> %{customdata[0]}", "<b>Início:</b> %{base|%d/%m/%Y}", "<b>Fim:</b> %{x[1]|%d/%m/%Y}", "<extra></extra>"]))
            st.plotly_chart(fig, use_container_width=True)
            
        st.subheader("Tabela de Dados")
        st.dataframe(df_filtrado, use_container_width=True, hide_index=True, column_config={"Link_dos_Arquivos": st.column_config.LinkColumn("Link dos Arquivos", display_text="Abrir ↗")})
        st.download_button("📥 Download Excel", convert_df_to_excel(df_filtrado),"dashboard_projetos.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        
    # =======================
    # CADASTRAR PROJETO
    # =======================
    elif aba=="Cadastrar Projeto":
        st.header("Cadastrar Novo Projeto")
        st.markdown("##### Opções de Orçamento")
        col_b_ext, col_bl_ext, _ = st.columns([1,1,2])
        tem_budget = col_b_ext.checkbox("Tem Budget")
        tem_baseline = col_bl_ext.checkbox("Tem Baseline")
        st.markdown("---")
        with st.form("form_cadastro", clear_on_submit=True):
            novo_id = f"PROJ{gerar_novo_numero():03d}"
            st.markdown(f"**ID do Projeto:** {novo_id}")
            col1, col2 = st.columns(2)
            id_contrato = col1.text_input("Id_Contrato")
            requisicao = col2.text_input("Requisição")
            area_setor = st.text_input("Área/Setor")
            categoria = st.text_input("Categoria")
            empresa = st.selectbox("Empresa", ["Selecione"] + empresas_options)
            responsavel = st.text_input("Responsável")
            descricao = st.text_area("Atividades_Descricao")
            link_arquivos = st.text_input("Link dos Arquivos", placeholder="Cole o link da pasta aqui")
            status = st.selectbox("Status", ["Selecione"] + status_options)
            
            if tem_budget or tem_baseline:
                st.markdown("### Orçamento (Budget/Baseline)")
                c1, c2 = st.columns(2)
                budget = c1.number_input("Budget (R$)", min_value=0.0, format="%.2f", disabled=not tem_budget)
                baseline = c2.number_input("Baseline (R$)", min_value=0.0, format="%.2f", disabled=not tem_baseline)
                melhor_proposta = st.number_input("Melhor Proposta (R$)", min_value=0.0, format="%.2f")
                preco_inicial, preco_final = 0.0, 0.0
            else:
                st.markdown("### Custos (Preço Inicial/Final)")
                preco_inicial = st.number_input("Preço Inicial (R$)", min_value=0.0, format="%.2f")
                preco_final = st.number_input("Preço Final (R$)", min_value=0.0, format="%.2f")
                budget, baseline, melhor_proposta = 0.0, 0.0, 0.0

            resultados_kpis = calcular_kpis_financeiros(tem_budget, tem_baseline, budget, baseline, melhor_proposta, preco_inicial, preco_final)
            st.markdown("---")
            st.markdown("#### Prévia dos Resultados Calculados")
            kpi1, kpi2, kpi3 = st.columns(3)
            kpi1.metric("Saving R$", formatar_moeda(resultados_kpis["Saving_R$"]), f"{resultados_kpis['Percent_Saving']:.2f}%")
            kpi2.metric("CE Baseline R$", formatar_moeda(resultados_kpis["CE_Baseline_R$"]), f"{resultados_kpis['Percent_CE_Baseline']:.2f}%")
            kpi3.metric("CE R$", formatar_moeda(resultados_kpis["CE_R$"]), f"{resultados_kpis['Percent_CE']:.2f}%")
            
            st.markdown("---")
            data_inicio = st.date_input("Data de Início", value=datetime.today(), format="DD/MM/YYYY")
            data_termino = st.date_input("Data de Término", value=datetime.today(), format="DD/MM/YYYY")
            submitted = st.form_submit_button("Salvar Projeto")
            if submitted:
                projeto_dict = {"ID_Projeto": novo_id, "Id_Contrato": id_contrato, "Requisicao": requisicao, "Area_Setor": area_setor, "Categoria": categoria, "Empresa": empresa, "Responsavel": responsavel, "Atividades_Descricao": descricao, "Link_dos_Arquivos": link_arquivos, "Status": status, "Tem_Budget": tem_budget, "Tem_Baseline": tem_baseline, "Budget": budget, "Baseline": baseline, "Melhor_Proposta": melhor_proposta, "Preco_Inicial": preco_inicial, "Preco_Final": preco_final, "Data_Inicio": pd.to_datetime(data_inicio), "Data_Termino": pd.to_datetime(data_termino)}
                projeto_dict.update(resultados_kpis)
                projetos_col.insert_one(projeto_dict)
                st.success(f"Projeto {novo_id} cadastrado com sucesso!")
                st.rerun()

    # =======================
    # ATUALIZAR PROJETO
    # =======================
    elif aba=="Atualizar Projeto":
        st.header("Atualizar Projeto Existente")
        lista_projetos = [""] + df["ID_Projeto"].tolist() if not df.empty else [""]
        id_selecionado = st.selectbox("Selecione o Projeto", lista_projetos)
        if id_selecionado:
            projeto = projetos_col.find_one({"ID_Projeto": id_selecionado})
            if projeto:
                st.markdown("---")
                st.markdown("##### Opções de Orçamento")
                col_b_ext, col_bl_ext, _ = st.columns([1,1,2])
                tem_budget_upd = col_b_ext.checkbox("Tem Budget", value=bool(projeto.get("Tem_Budget")))
                tem_baseline_upd = col_bl_ext.checkbox("Tem Baseline", value=bool(projeto.get("Tem_Baseline")))
                st.markdown("---")
                with st.form("form_atualizar"):
                    st.markdown("#### Dados Gerais do Projeto")
                    col1, col2 = st.columns(2)
                    id_contrato = col1.text_input("Id_Contrato", value=projeto.get("Id_Contrato", ""))
                    requisicao = col2.text_input("Requisição", value=projeto.get("Requisicao", ""))
                    area_setor = st.text_input("Área/Setor", value=projeto.get("Area_Setor", ""))
                    categoria = st.text_input("Categoria", value=projeto.get("Categoria", ""))
                    empresa_idx = empresas_options.index(projeto.get("Empresa", "")) if projeto.get("Empresa") in empresas_options else 0
                    empresa = st.selectbox("Empresa", empresas_options, index=empresa_idx)
                    responsavel = st.text_input("Responsável", value=projeto.get("Responsavel", ""))
                    descricao = st.text_area("Atividades_Descricao", value=projeto.get("Atividades_Descricao", ""))
                    link_arquivos = st.text_input("Link dos Arquivos", value=projeto.get("Link_dos_Arquivos", ""))
                    status_idx = status_options.index(projeto.get("Status", "")) if projeto.get("Status") in status_options else 0
                    status = st.selectbox("Status", status_options, index=status_idx)
                    st.markdown("---")
                    st.markdown("#### Cronograma")
                    c_data1, c_data2 = st.columns(2)
                    data_inicio = c_data1.date_input("Data de Início", value=pd.to_datetime(projeto.get("Data_Inicio", datetime.today())), format="DD/MM/YYYY")
                    data_termino = c_data2.date_input("Data de Término", value=pd.to_datetime(projeto.get("Data_Termino", datetime.today())), format="DD/MM/YYYY")
                    if tem_budget_upd or tem_baseline_upd:
                        st.markdown("---")
                        st.markdown("#### Orçamento (Budget/Baseline)")
                        c1, c2 = st.columns(2)
                        budget = c1.number_input("Budget (R$)", value=float(projeto.get("Budget", 0.0) or 0.0), min_value=0.0, format="%.2f", disabled=not tem_budget_upd)
                        baseline = c2.number_input("Baseline (R$)", value=float(projeto.get("Baseline", 0.0) or 0.0), min_value=0.0, format="%.2f", disabled=not tem_baseline_upd)
                        melhor_proposta = st.number_input("Melhor Proposta (R$)", value=float(projeto.get("Melhor_Proposta", 0.0) or 0.0), min_value=0.0, format="%.2f")
                        preco_inicial, preco_final = 0.0, 0.0
                    else:
                        st.markdown("---")
                        st.markdown("#### Custos (Preço Inicial/Final)")
                        preco_inicial = st.number_input("Preço Inicial (R$)", value=float(projeto.get("Preco_Inicial", 0.0) or 0.0), min_value=0.0, format="%.2f")
                        preco_final = st.number_input("Preço Final (R$)", value=float(projeto.get("Preco_Final", 0.0) or 0.0), min_value=0.0, format="%.2f")
                        budget, baseline, melhor_proposta = 0.0, 0.0, 0.0
                    
                    resultados_kpis_upd = calcular_kpis_financeiros(tem_budget_upd, tem_baseline_upd, budget, baseline, melhor_proposta, preco_inicial, preco_final)
                    st.markdown("---")
                    st.markdown("#### Prévia dos Resultados Calculados")
                    kpi1, kpi2, kpi3 = st.columns(3)
                    kpi1.metric("Saving R$", formatar_moeda(resultados_kpis_upd["Saving_R$"]), f"{resultados_kpis_upd['Percent_Saving']:.2f}%")
                    kpi2.metric("CE Baseline R$", formatar_moeda(resultados_kpis_upd["CE_Baseline_R$"]), f"{resultados_kpis_upd['Percent_CE_Baseline']:.2f}%")
                    kpi3.metric("CE R$", formatar_moeda(resultados_kpis_upd["CE_R$"]), f"{resultados_kpis_upd['Percent_CE']:.2f}%")
                    submitted = st.form_submit_button("Atualizar Projeto")
                    if submitted:
                        update_data = {"Id_Contrato": id_contrato, "Requisicao": requisicao, "Area_Setor": area_setor, "Categoria": categoria, "Empresa": empresa, "Responsavel": responsavel, "Atividades_Descricao": descricao, "Link_dos_Arquivos": link_arquivos, "Status": status, "Tem_Budget": tem_budget_upd, "Tem_Baseline": tem_baseline_upd, "Budget": budget, "Baseline": baseline, "Melhor_Proposta": melhor_proposta, "Preco_Inicial": preco_inicial, "Preco_Final": preco_final, "Data_Inicio": pd.to_datetime(data_inicio), "Data_Termino": pd.to_datetime(data_termino)}
                        update_data.update(resultados_kpis_upd)
                        projetos_col.update_one({"ID_Projeto": id_selecionado}, {"$set": update_data})
                        st.success(f"Projeto {id_selecionado} atualizado com sucesso!")
                        st.rerun()
