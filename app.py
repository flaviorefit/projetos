import streamlit as st
from pymongo import MongoClient
import pandas as pd
from datetime import datetime, date
import io
from st_aggrid import AgGrid, GridOptionsBuilder, DataReturnMode
import plotly.express as px
from babel.numbers import format_currency
import hashlib

# -------------------------
# Configuração da página
# -------------------------
st.set_page_config(page_title="Gestão de Projetos", layout="wide")

# Inicializa o estado de login
if 'login_realizado' not in st.session_state:
    st.session_state.login_realizado = False
if 'usuario_logado' not in st.session_state:
    st.session_state.usuario_logado = ""

# -------------------------
# Funções de Login
# -------------------------
def hash_password(password):
    """Gera um hash SHA256 para a senha fornecida."""
    return hashlib.sha256(password.encode()).hexdigest()

def verificar_login(usuario, senha):
    """Verifica as credenciais do usuário com o secrets.toml."""
    try:
        # Acessa a senha do usuário usando a estrutura de dicionário aninhado
        # Ex: st.secrets["usuarios"]["flavio.ribeiro"]["password"]
        senha_salva = st.secrets.get("usuarios", {}).get(usuario, {}).get("password")

        # Se o usuário não existir nos segredos, a senha_salva será None
        if senha_salva is None:
            return False
            
        # Gera o hash da senha digitada pelo usuário
        senha_digitada_hash = hash_password(senha)
        
        # Compara o hash gerado com o hash salvo
        if senha_digitada_hash == senha_salva:
            return True
        return False
    except KeyError:
        st.error("Erro: Credenciais de usuário não configuradas ou em formato incorreto no secrets.toml.")
        return False


def tela_login():
    st.markdown(
        """
        <style>
        .stApp { background: linear-gradient(135deg, #e3f2fd 0%, #f3e5f5 100%); }
        .main .block-container { padding-top: 0; padding-bottom: 0; max-width: 100%; }
        .login-container { display: flex; justify-content: center; align-items: flex-start; min-height: 50vh; padding: 50px 20px 20px 20px; }
        </style>
        """,
        unsafe_allow_html=True
    )
    st.markdown('<div class="login-container">', unsafe_allow_html=True)
    _, col2, _ = st.columns([1, 2, 1])

    with col2:
        st.markdown("<h1 style='text-align: center; color: #002776;'>Sistema de Projetos</h1>", unsafe_allow_html=True)
        
        with st.form("login_form"):
            usuario = st.text_input("Usuário", placeholder="Digite seu usuário")
            senha = st.text_input("Senha", type="password", placeholder="Digite sua senha")
            if st.form_submit_button("Entrar", use_container_width=True, type="primary"):
                if verificar_login(usuario, senha):
                    st.session_state.login_realizado = True
                    st.session_state.usuario_logado = usuario
                    st.success("Login realizado com sucesso!")
                    st.rerun()
                else:
                    st.error("Usuário ou senha inválidos.")
    st.markdown('</div>', unsafe_allow_html=True)

def logout():
    st.session_state.clear()
    st.rerun()

# -------------------------
# Conexão MongoDB
# -------------------------
@st.cache_resource
def init_connection():
    try:
        client = MongoClient(st.secrets["mongo_uri"], serverSelectionTimeoutMS=20000)
        client.admin.command("ping")
        return client
    except Exception as e:
        st.error(f"❌ Erro ao conectar no MongoDB: {e}")
        st.stop()

client = init_connection()

def get_db_collection(db_name, collection_name):
    try:
        db = client[db_name]
        collection = db[collection_name]
        return collection
    except Exception as e:
        st.error(f"Erro ao acessar o banco de dados/coleção: {e}")
        return None

# -------------------------
# Carregar Dados
# -------------------------
@st.cache_data(ttl=10)
def carregar_dados():
    try:
        db_name = st.secrets["mongo_db"]
        collection_name = st.secrets["mongo_collection_projetos"]
        collection = get_db_collection(db_name, collection_name)
        if collection is None:
            return pd.DataFrame()
        df = pd.DataFrame(list(collection.find({}, {"_id": 0})))
        
        colunas_essenciais = ['ID_Projeto', 'Status', 'Empresa', 'Responsável']
        for col in colunas_essenciais:
            if col not in df.columns:
                df[col] = pd.NA
        
        for col in df.columns:
            if 'Data' in col:
                df[col] = pd.to_datetime(df[col], errors='coerce')
        return df
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return pd.DataFrame()

# -------------------------
# Funções Auxiliares
# -------------------------
@st.cache_data(ttl=60)
def gerar_id_otimizado():
    db_name = st.secrets["mongo_db"]
    collection_name = st.secrets["mongo_collection_projetos"]
    collection = get_db_collection(db_name, collection_name)
    if collection is None:
        return "PROJ001"
    
    ultimo_projeto = collection.find_one(sort=[("ID_Projeto", -1)])
    if not ultimo_projeto:
        return "PROJ001"
    ultimo_id = ultimo_projeto.get("ID_Projeto", "PROJ000")
    try:
        num = int(ultimo_id.replace("PROJ", "")) + 1
        return f"PROJ{num:03d}"
    except (ValueError, TypeError):
        return "PROJ001"

def salvar_projeto_mongo(projeto):
    db_name = st.secrets["mongo_db"]
    collection_name = st.secrets["mongo_collection_projetos"]
    collection = get_db_collection(db_name, collection_name)
    if collection is None:
        return False
    projeto["Data_Inicio"] = datetime.combine(projeto["Data_Inicio"], datetime.min.time())
    projeto["Data_Termino"] = datetime.combine(projeto["Data_Termino"], datetime.min.time())
    collection.insert_one(projeto)
    return True

def parse_currency_input(value_str):
    if not value_str:
        return 0.0
    value_str = str(value_str).replace("R$", "").strip().replace(".", "").replace(",", ".")
    try:
        return float(value_str)
    except (ValueError, TypeError):
        return 0.0

def to_date(dt):
    if isinstance(dt, (datetime, pd.Timestamp)):
        return dt.date()
    return dt

def calcular_progresso(data_inicio, data_termino):
    hoje = date.today()
    if data_inicio is None or data_termino is None:
        return 0.0
    data_inicio_date = to_date(data_inicio)
    data_termino_date = to_date(data_termino)
    if data_termino_date < data_inicio_date:
        return 0.0
    dias_totais = (data_termino_date - data_inicio_date).days
    if dias_totais <= 0:
        return 100.0 if hoje >= data_termino_date else 0.0
    if hoje <= data_inicio_date:
        return 0.0
    if hoje >= data_termino_date:
        return 100.0
    dias_passados = (hoje - data_inicio_date).days
    progresso = (dias_passados / dias_totais) * 100
    return round(progresso, 2)

def exportar_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Projetos")
    processed_data = output.getvalue()
    return processed_data

# -------------------------
# Início do aplicativo
# -------------------------
if not st.session_state.login_realizado:
    tela_login()
    st.stop()
else:
    st.sidebar.title("Bem-vindo(a), " + st.session_state.usuario_logado)
    st.sidebar.title("Menu")
    
    if st.sidebar.button("Sair"):
        logout()

    STATUS = sorted(["A Iniciar", "Em andamento", "Atrasado", "Concluído", "Cancelado", "Stand By"])
    EMPRESAS = sorted([
        "POSTOS GULF", "76 OIL", "ALPHA FINANCIAL", "ALPHA MATRIZ", "AM GESTÃO FIL", "AM GESTÃO MTZ",
        "ANDRADE MAGRO", "BCAG SP 0002", "BORLANGE SP", "CARINTHIA RJ 01", "CARINTHIA RJ 03", "CAVALINI",
        "CHURCHILL", "CREATIVE", "DIRECIONAL ES", "DIRECIONAL FL", "DIRECIONAL MT", "DIRECIONAL SP",
        "EBTL", "ESTRELA", "EURO", "FAIR ENERGY", "FERA RJ", "FERA SP", "FIT MARINE", "FIT MARINE FILIAL",
        "FIT MARINE MATRIZ", "FITFILE", "FITPAR", "FLAGLER GO", "FLAGLER RJ", "FLAGLER SP", "FOCUS HUB",
        "GOOIL", "LOGFIT FILIAL ARUJA", "LOGFIT FILIAL CAXIAS", "LOGFIT FILIAL RJ", "LOGFIT MATRIZ",
        "LOGFIT RJ 0002", "LOGFIT RJ 0003", "LOGFIT SP 0001", "LOGFIT SP 0006", "LOGFIT TOCANTINS",
        "MAGRO ADV FIL", "MAGRO ADV MATR", "MANGUINHOS FIL", "MANGUINHOS FILIAL", "MANGUINHOS MATR",
        "MANGUINHOS MATRIZ", "MAXIMUS", "MAXIMUS TO", "ORNES GESTAO", "PARAISO TO 0001", "PETRO GO 0006",
        "PETRO MA 0005", "PETRO RJ 0007", "PETRO TO 0001", "PETRO TO 0004", "PORT BRAZIL", "R.A MAGRO ADV",
        "REFIT FILIAL ALAGOAS", "REFIT FILIAL AMAPA", "REFIT MATRIZ", "RENOMEADA 57", "RENOMEADA 61",
        "RENOMEADA 62", "RENOMEADA 64", "RENOMEADA 66", "ROAR FL 0003", "ROAR FL 0004", "ROAR MATRIZ",
        "RODOPETRO CN", "RODOPETRO MTZ", "RODOPETRO RJ DC", "TIGER MATRIZ", "TLIQ", "USINA CIDADANIA",
        "VAISHIA", "XOROQUE", "XYZ SP", "YIELD FILIAL", "YIELD MATRIZ"
    ])
    Empresas_selecione = ["Selecione"] + EMPRESAS
    COMPRADOR_RESPONSAVEL = sorted([
        "TATIANE", "LILIAN", "ISAAC", "DIEGO", "LUCAS NOGUEIRA", "GUILHERME", "JESSICA", "CLAUDIO", "NORMA",
        "TERESA", "BRUNO MUZI", "ANDERSON", "SIMONE", "JOÃO HENRIQUE", "ANA PAULA", "RENATA", "LUCAS MOREIRA",
        "MARINA", "LUIZ PAULO", "EMERSON", "BRUNO ARAUJO", "JOSANE", "MAURO", "MARIA CLARA", "JOÃO SANTA RITA",
        "MILENA SANT", "JULIA", "LEANDRO", "ALICE", "SUELLEN", "JENNIFER", "VANESSA"
    ])
    Comprador_selecione = ["Selecione"] + COMPRADOR_RESPONSAVEL

    menu = st.sidebar.radio("Menu", ["Cadastrar Projeto", "Listar Projetos", "Editar Projeto"])
    
    if menu == "Cadastrar Projeto":
        st.subheader("📝 Cadastro de Projeto")
        col_check_orc, col_check_base = st.columns(2)
        with col_check_orc:
            tem_orcamento = st.checkbox("Tem Orçamento?")
        with col_check_base:
            linha_base = st.checkbox("Tem Baseline?")
        
        exibir_melhor_proposta = tem_orcamento or linha_base
        orcamento, melhor_proposta, saving_r, saving_percent, baseline, ce_baseline, percent_baseline, preco_inicial, preco_final, ce_r, percent_ce = [0] * 11

        with st.form("form_cadastro"):
            st.write("### Informações dos Projetos")
            caminho_pasta = st.text_input("Caminho da Pasta")
            col_pedido, col_contrato = st.columns(2)
            with col_pedido:
                pedido = st.text_input("Número do Pedido")
            with col_contrato:
                id_contrato = st.text_input("ID de Contrato")

            col1, col2 = st.columns(2)
            with col1:
                area_setor = st.text_input("Setor/Área")
            with col2:
                empresa = st.selectbox("Empresa", Empresas_selecione)
            col3, col4 = st.columns(2)
            with col3:
                categoria = st.text_input("Categoria")
            with col4:
                responsavel = st.selectbox("Responsável", Comprador_selecione)
            atividade = st.text_area("Atividade/Descrição")

            st.markdown("---")
            st.write("### Detalhes Financeiros")

            if tem_orcamento:
                orcamento_str = st.text_input("Budget (R$)", value="0,00", key="orcamento_input_cadastro")
                orcamento = parse_currency_input(orcamento_str)
            if linha_base:
                baseline_str = st.text_input("Baseline (R$)", value="0,00", key="baseline_input_cadastro")
                baseline = parse_currency_input(baseline_str)
            if exibir_melhor_proposta:
                melhor_proposta_str = st.text_input("Melhor Proposta (R$)", value="0,00", key="proposta_input_cadastro")
                melhor_proposta = parse_currency_input(melhor_proposta_str)
            if not (tem_orcamento or linha_base):
                preco_inicial_str = st.text_input("Preço Inicial (R$)", value="0,00", key="preco_inicial_input_cadastro")
                preco_inicial = parse_currency_input(preco_inicial_str)
                preco_final_str = st.text_input("Preço Final (R$)", value="0,00", key="preco_final_input_cadastro")
                preco_final = parse_currency_input(preco_final_str)
                ce_r = preco_inicial - preco_final
                percent_ce = (ce_r / preco_inicial) * 100 if preco_inicial != 0 else 0
                st.markdown(f"**C.E R$:** {format_currency(ce_r, 'BRL', locale='pt_BR')}")
                st.markdown(f"**% C.E:** {percent_ce:.2f}%")

            if tem_orcamento:
                saving_r = orcamento - melhor_proposta
                saving_percent = (saving_r / orcamento) * 100 if orcamento != 0 else 0
                st.markdown(f"**Saving R$:** {format_currency(saving_r, 'BRL', locale='pt_BR')}")
                st.markdown(f"**% Saving:** {saving_percent:.2f}%")
            if linha_base:
                ce_baseline = baseline - melhor_proposta
                percent_baseline = (ce_baseline / baseline) * 100 if baseline != 0 else 0
                st.markdown(f"**C.E Baseline R$:** {format_currency(ce_baseline, 'BRL', locale='pt_BR')}")
                st.markdown(f"**% Baseline:** {percent_baseline:.2f}%")

            st.markdown("---")
            st.write("### Status e Datas")
            col_status, col_data_inicio, col_data_termino = st.columns(3)
            with col_status:
                status = st.selectbox("Status", STATUS)
            with col_data_inicio:
                data_inicio = st.date_input("Data de Início", value=date.today(), format="DD/MM/YYYY")
            with col_data_termino:
                data_termino = st.date_input("Data de Término", value=date.today(), format="DD/MM/YYYY")

            submit = st.form_submit_button("Salvar Projeto")
            if submit:
                if data_termino < data_inicio:
                    st.error("A data de término não pode ser anterior à data de início.")
                else:
                    id_projeto = gerar_id_otimizado()
                    projeto = {
                        "ID_Projeto": id_projeto, "Link_da_Pasta": caminho_pasta, "Pedido": pedido,
                        "ID_Contrato": id_contrato, "Área_Setor": area_setor, "Empresa": empresa,
                        "Categoria": categoria, "Atividades_Descrição": atividade, "Responsável": responsavel,
                        "Tem_Orçamento": tem_orcamento, "Linha_de_base": linha_base, "Orçamento": orcamento,
                        "Baseline": baseline, "Melhor_Proposta": melhor_proposta, "Preço_Inicial": preco_inicial,
                        "Preço_Final": preco_final, "Saving_R$": saving_r, "Saving_Percent": saving_percent,
                        "CE_Baseline_R$": ce_baseline, "Percentual_CE_Linha_de_base": percent_baseline,
                        "CE_R$": ce_r, "Porcentagem_CE": percent_ce, "Status": status,
                        "Data_Inicio": data_inicio, "Data_Termino": data_termino,
                        "Dias": (data_termino - data_inicio).days,
                        "Progresso_Porcentagem": calcular_progresso(data_inicio, data_termino),
                    }
                    if salvar_projeto_mongo(projeto):
                        st.success(f"✅ Projeto salvo! Código: {id_projeto}")
                        carregar_dados.clear()
                        gerar_id_otimizado.clear()

    elif menu == "Listar Projetos":
        st.subheader("📋 Listagem de Projetos")
        df = carregar_dados()
        if not df.empty:
            if "Data_Inicio" in df.columns:
                df["Data_Inicio"] = pd.to_datetime(df["Data_Inicio"], errors="coerce").dt.strftime('%d/%m/%Y')
            if "Data_Termino" in df.columns:
                df["Data_Termino"] = pd.to_datetime(df["Data_Termino"], errors="coerce").dt.strftime('%d/%m/%Y')
            if "Progresso_Porcentagem" in df.columns:
                df["Progresso_Porcentagem"] = df["Progresso_Porcentagem"].round(2)
            currency_cols = ["Orçamento", "Baseline", "Melhor_Proposta", "Preço_Inicial", "Preço_Final", "Saving_R$", "CE_Baseline_R$", "CE_R$"]
            for col in currency_cols:
                if col in df.columns:
                    df[col] = df[col].astype(float)
            col1, col2 = st.columns(2)
            with col1:
                filtro_status = st.selectbox("Filtrar por Status", ["Todos"] + sorted(df["Status"].dropna().unique().tolist()), index=0)
            with col2:
                filtro_empresa = st.selectbox("Filtrar por Empresa", ["Todos"] + sorted(df["Empresa"].dropna().unique().tolist()), index=0)
            df_filtrado = df.copy()
            if filtro_status != "Todos":
                df_filtrado = df_filtrado[df_filtrado["Status"] == filtro_status]
            if filtro_empresa != "Todos":
                df_filtrado = df_filtrado[df_filtrado["Empresa"] == filtro_empresa]
            resumo_status = df_filtrado['Status'].value_counts().reset_index()
            resumo_status.columns = ['Status', 'Quantidade']
            if not resumo_status.empty:
                fig_status = px.bar(
                    resumo_status, x='Status', y='Quantidade', text='Quantidade', color='Status',
                    color_discrete_map={
                        "A Iniciar": "#F2C94C", "Em andamento": "#2F80ED", "Atrasado": "#D90429",
                        "Concluído": "#27AE60", "Cancelado": "#9B51E0", "Stand By": "#F2994A"
                    }, title="Distribuição de Projetos por Status"
                )
                fig_status.update_traces(textposition='outside')
                st.plotly_chart(fig_status, use_container_width=True)
            else:
                st.info("Nenhum projeto encontrado com os filtros selecionados.")
            gb = GridOptionsBuilder.from_dataframe(df_filtrado)
            gb.configure_default_column(editable=False, resizable=True, wrapText=True, autoHeight=True)
            for col in currency_cols:
                if col in df_filtrado.columns:
                    gb.configure_column(col, type=["numericColumn"], valueFormatter="value != null ? value.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' }) : ''")
            gb.configure_column("ID_Projeto", header_name="Código", pinned="left", width=120)
            gb.configure_column("Progresso_Porcentagem", header_name="Progresso (%)", type=["numericColumn"], width=120)
            gb.configure_grid_options(domLayout='normal')
            gridOptions = gb.build()
            AgGrid(
                df_filtrado, gridOptions=gridOptions, enable_enterprise_modules=False,
                height=400, fit_columns_on_grid_load=False, reload_data=True
            )
            if not df_filtrado.empty:
                col1, col2 = st.columns(2)
                with col1:
                    csv = df_filtrado.to_csv(index=False).encode("utf-8")
                    st.download_button("⬇️ Exportar CSV", csv, "projetos.csv", "text/csv")
                with col2:
                    excel = exportar_excel(df_filtrado)
                    st.download_button("⬇️ Exportar Excel", excel, "projetos.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        else:
            st.info("Nenhum projeto cadastrado.")
    elif menu == "Editar Projeto":
        st.subheader("✍️ Editar Projeto")
        collection = get_db_collection(st.secrets["mongo_db"], st.secrets["mongo_collection_projetos"])
        if collection is None:
            st.error("Não foi possível conectar ao banco de dados para edição.")
        else:
            df_projetos = carregar_dados()
            if df_projetos.empty:
                st.info("Nenhum projeto encontrado para edição.")
            else:
                lista_projetos = ["Selecione..."] + [f"{row['ID_Projeto']} - {row.get('Pedido', 'Sem Pedido')}" for _, row in df_projetos.iterrows()]
                projeto_selecionado = st.selectbox("Selecione um projeto para editar", lista_projetos)
                if projeto_selecionado != "Selecione...":
                    id_selecionado = projeto_selecionado.split(" - ")[0]
                    projeto_existente = collection.find_one({"ID_Projeto": id_selecionado})
                    if projeto_existente:
                        with st.form("form_edicao"):
                            st.write("### Informações Gerais")
                            caminho_pasta = st.text_input("Caminho da Pasta", value=projeto_existente.get("Link_da_Pasta", ""))
                            col_pedido, col_contrato = st.columns(2)
                            with col_pedido:
                                pedido = st.text_input("Número do Pedido", value=projeto_existente.get("Pedido", ""))
                            with col_contrato:
                                id_contrato = st.text_input("ID de Contrato", value=projeto_existente.get("ID_Contrato", ""))
                            col1, col2 = st.columns(2)
                            with col1:
                                area_setor = st.text_input("Setor/Área", value=projeto_existente.get("Área_Setor", ""))
                            with col2:
                                empresa_idx = Empresas_selecione.index(projeto_existente.get("Empresa", "Selecione")) if projeto_existente.get("Empresa") in Empresas_selecione else 0
                                empresa = st.selectbox("Empresa", Empresas_selecione, index=empresa_idx)
                            col3, col4 = st.columns(2)
                            with col3:
                                categoria = st.text_input("Categoria", value=projeto_existente.get("Categoria", ""))
                            with col4:
                                resp_idx = Comprador_selecione.index(projeto_existente.get("Responsável", "Selecione")) if projeto_existente.get("Responsável") in Comprador_selecione else 0
                                responsavel = st.selectbox("Responsável", Comprador_selecione, index=resp_idx)
                            atividade = st.text_area("Atividade/Descrição", value=projeto_existente.get("Atividades_Descrição", ""))
                            st.markdown("---")
                            st.write("### Detalhes Financeiros")
                            tem_orcamento = st.checkbox("Tem Orçamento?", value=projeto_existente.get("Tem_Orçamento", False))
                            linha_base = st.checkbox("Tem Baseline?", value=projeto_existente.get("Linha_de_base", False))
                            orcamento, baseline, melhor_proposta, preco_inicial, preco_final = 0.0, 0.0, 0.0, 0.0, 0.0
                            if tem_orcamento:
                                orcamento_val_str = f'{projeto_existente.get("Orçamento", 0):,.2f}'.replace('.', '#').replace(',', '.').replace('#', ',')
                                orcamento_str = st.text_input("Budget (R$)", value=orcamento_val_str)
                                orcamento = parse_currency_input(orcamento_str)
                            if linha_base:
                                baseline_val_str = f'{projeto_existente.get("Baseline", 0):,.2f}'.replace('.', '#').replace(',', '.').replace('#', ',')
                                baseline_str = st.text_input("Baseline (R$)", value=baseline_val_str)
                                baseline = parse_currency_input(baseline_str)
                            if tem_orcamento or linha_base:
                                melhor_proposta_val_str = f'{projeto_existente.get("Melhor_Proposta", 0):,.2f}'.replace('.', '#').replace(',', '.').replace('#', ',')
                                melhor_proposta_str = st.text_input("Melhor Proposta (R$)", value=melhor_proposta_val_str)
                                melhor_proposta = parse_currency_input(melhor_proposta_str)
                            if not (tem_orcamento or linha_base):
                                preco_inicial_val_str = f'{projeto_existente.get("Preço_Inicial", 0):,.2f}'.replace('.', '#').replace(',', '.').replace('#', ',')
                                preco_inicial_str = st.text_input("Preço Inicial (R$)", value=preco_inicial_val_str)
                                preco_inicial = parse_currency_input(preco_inicial_str)
                                preco_final_val_str = f'{projeto_existente.get("Preço_Final", 0):,.2f}'.replace('.', '#').replace(',', '.').replace('#', ',')
                                preco_final_str = st.text_input("Preço Final (R$)", value=preco_final_val_str)
                                preco_final = parse_currency_input(preco_final_str)
                            saving_r = orcamento - melhor_proposta if tem_orcamento else 0
                            saving_percent = (saving_r / orcamento) * 100 if tem_orcamento and orcamento != 0 else 0
                            ce_baseline = baseline - melhor_proposta if linha_base else 0
                            percent_baseline = (ce_baseline / baseline) * 100 if linha_base and baseline != 0 else 0
                            ce_r = preco_inicial - preco_final if not (tem_orcamento or linha_base) else 0
                            percent_ce = (ce_r / preco_inicial) * 100 if not (tem_orcamento or linha_base) and preco_inicial != 0 else 0
                            if tem_orcamento:
                                st.markdown(f"**Saving R$:** {format_currency(saving_r, 'BRL', locale='pt_BR')}")
                                st.markdown(f"**% Saving:** {saving_percent:.2f}%")
                            if linha_base:
                                st.markdown(f"**C.E Baseline R$:** {format_currency(ce_baseline, 'BRL', locale='pt_BR')}")
                                st.markdown(f"**% Baseline:** {percent_baseline:.2f}%")
                            if not (tem_orcamento or linha_base):
                                st.markdown(f"**C.E R$:** {format_currency(ce_r, 'BRL', locale='pt_BR')}")
                                st.markdown(f"**% C.E:** {percent_ce:.2f}%")
                            st.markdown("---")
                            st.write("### Status e Datas")
                            col_status, col_data_inicio, col_data_termino = st.columns(3)
                            with col_status:
                                status_idx = STATUS.index(projeto_existente.get("Status", "A Iniciar")) if projeto_existente.get("Status") in STATUS else 0
                                status = st.selectbox("Status", STATUS, index=status_idx)
                            with col_data_inicio:
                                data_inicio = st.date_input("Data de Início", value=to_date(projeto_existente.get("Data_Inicio", date.today())), format="DD/MM/YYYY")
                            with col_data_termino:
                                data_termino = st.date_input("Data de Término", value=to_date(projeto_existente.get("Data_Termino", date.today())), format="DD/MM/YYYY")
                            submit_update = st.form_submit_button("Salvar Alterações")
                            if submit_update:
                                if data_termino < data_inicio:
                                    st.error("A data de término não pode ser anterior à data de início.")
                                else:
                                    dados_atualizados = {
                                        "Link_da_Pasta": caminho_pasta, "Pedido": pedido, "ID_Contrato": id_contrato,
                                        "Área_Setor": area_setor, "Empresa": empresa, "Categoria": categoria,
                                        "Atividades_Descrição": atividade, "Responsável": responsavel,
                                        "Tem_Orçamento": tem_orcamento, "Linha_de_base": linha_base,
                                        "Orçamento": orcamento, "Baseline": baseline, "Melhor_Proposta": melhor_proposta,
                                        "Preço_Inicial": preco_inicial, "Preço_Final": preco_final,
                                        "Saving_R$": saving_r, "Saving_Percent": saving_percent,
                                        "CE_Baseline_R$": ce_baseline, "Percentual_CE_Linha_de_base": percent_baseline,
                                        "CE_R$": ce_r, "Porcentagem_CE": percent_ce, "Status": status,
                                        "Data_Inicio": datetime.combine(data_inicio, datetime.min.time()),
                                        "Data_Termino": datetime.combine(data_termino, datetime.min.time()),
                                        "Dias": (data_termino - data_inicio).days,
                                        "Progresso_Porcentagem": calcular_progresso(data_inicio, data_termino),
                                    }
                                    result = collection.update_one({"ID_Projeto": id_selecionado}, {"$set": dados_atualizados})
                                    if result.modified_count > 0:
                                        st.success(f"✅ Projeto '{id_selecionado}' atualizado com sucesso!")
                                        carregar_dados.clear()
                                    else:
                                        st.info("Nenhuma alteração detectada. O projeto não foi modificado.")
