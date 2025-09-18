import streamlit as st
import pandas as pd
from pymongo import MongoClient
from datetime import datetime, date
import plotly.express as px
import io
from st_aggrid import AgGrid, GridOptionsBuilder

# =======================
# FUNÇÃO DE LOGIN
# =======================
def check_password():
    """Retorna True se a senha estiver correta, False caso contrário."""
    def password_entered():
        """Verifica se a senha digitada corresponde à secret."""
        if st.session_state["password"] == st.secrets["login_password"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Não manter a senha em memória
        else:
            st.session_state["password_correct"] = False

    # Inicializa o estado da sessão se não existir
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    # Se a senha não estiver correta, mostra o formulário de login
    if not st.session_state["password_correct"]:
        st.title("🔒 Tela de Login")
        st.text_input(
            "Digite a senha para acessar:", type="password", on_change=password_entered, key="password"
        )
        if "password" in st.session_state and not st.session_state["password_correct"]:
             st.error("😕 Senha incorreta. Tente novamente.")
        return False
    else:
        return True

# =======================
# CONFIGURAÇÃO DA PÁGINA
# =======================
st.set_page_config(page_title="Gestão de Projetos", layout="wide")

# =======================
# VERIFICAÇÃO DE LOGIN
# =======================
if not check_password():
    st.stop()  # Para a execução do app se o login falhar

# O restante do seu código original começa aqui...

# =======================
# FUNÇÕES DE FORMATAÇÃO E AUXILIARES
# =======================
def formatar_moeda(valor):
    """Formata um valor numérico como moeda brasileira (R$)."""
    if pd.isna(valor) or valor is None or valor == "":
        return "R$ 0,00"
    valor_float = float(valor)
    return f"R$ {valor_float:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def formatar_percentual(valor):
    """Formata um valor numérico como percentual com duas casas decimais."""
    if pd.isna(valor) or valor is None or valor == "":
        return "0,00%"
    valor_float = float(valor)
    return f"{valor_float:.2f}%".replace(".", ",")

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

def convert_df_to_excel(df):
    """Converte um DataFrame para um arquivo Excel em memória."""
    output = io.BytesIO()
    for col in df.select_dtypes(include=['datetimetz']).columns:
        df[col] = df[col].dt.tz_localize(None)
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Dados')
    processed_data = output.getvalue()
    return processed_data

def parse_currency_input(text_input):
    """Converte um input de texto formatado como moeda para float."""
    try:
        return float(text_input.replace("R$", "").replace(".", "").replace(",", ".").strip())
    except (ValueError, AttributeError):
        return 0.0

# ===============================
# CONEXÃO COM O BANCO DE DADOS
# ===============================
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
db = client[st.secrets["mongo_db"]]
projetos_col = db[st.secrets["mongo_collection_projetos"]]

# =======================
# CARREGAR DADOS
# =======================
@st.cache_data(ttl=10)
def carregar_dados():
    try:
        df = pd.DataFrame(list(projetos_col.find()))
        if '_id' in df.columns:
            df.drop(columns=['_id'], inplace=True)
        
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

df = carregar_dados()

# =======================
# LISTAS E FUNÇÕES AUXILIARES
# =======================
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

def gerar_id_otimizado():
    if projetos_col.count_documents({}) == 0:
        return "PROJ001"
    
    ultimo_projeto = projetos_col.find_one(sort=[("ID_Projeto", -1)])
    if not ultimo_projeto:
        return "PROJ001"
    ultimo_id = ultimo_projeto.get("ID_Projeto", "PROJ000")
    try:
        num = int(ultimo_id.replace("PROJ", "")) + 1
        return f"PROJ{num:03d}"
    except (ValueError, TypeError):
        return "PROJ001"

# =======================
# FUNÇÕES DE FILTRO
# =======================
def aplicar_filtros_projetos(df_base):
    """
    Cria os widgets de filtro na barra lateral.
    """
    status_opcoes = sorted(df_base["Status"].dropna().unique().tolist())
    empresas_opcoes = sorted(df_base["Empresa"].dropna().unique().tolist())
    responsaveis_opcoes = sorted(df_base["Responsável"].dropna().unique().tolist())
    
    filtro_status = st.multiselect("Filtrar por Status", options=status_opcoes, key="filtro_status")
    filtro_empresa = st.multiselect("Filtrar por Empresa", options=empresas_opcoes, key="filtro_empresa")
    filtro_responsavel = st.multiselect("Filtrar por Responsável", options=responsaveis_opcoes, key="filtro_responsavel")
    
    df_filtrado = df_base.copy()
    
    if filtro_status:
        df_filtrado = df_filtrado[df_filtrado["Status"].isin(filtro_status)]
    if filtro_empresa:
        df_filtrado = df_filtrado[df_filtrado["Empresa"].isin(filtro_empresa)]
    if filtro_responsavel:
        df_filtrado = df_filtrado[df_filtrado["Responsável"].isin(filtro_responsavel)]
        
    return df_filtrado

# =======================
# LÓGICA PRINCIPAL DO APP
# =======================
st.sidebar.title("Menu")
aba = st.sidebar.radio(
    "Escolha uma opção:",
    ["Dashboard", "Listar Projetos", "Cadastrar Projeto", "Editar/Excluir"]
)

with st.sidebar.expander("🎯 Filtros Gerais", expanded=True):
    df_filtrado = aplicar_filtros_projetos(df)

# =======================
# RENDERIZAÇÃO DAS ABAS
# =======================
if aba == "Dashboard":
    st.header("📊 Dashboard de Projetos")
    
    if not df_filtrado.empty:
        # Indicadores Chave
        qtd_total = len(df_filtrado)
        qtd_concluidos = len(df_filtrado[df_filtrado["Status"] == "Concluído"])
        qtd_andamento = len(df_filtrado[df_filtrado["Status"] == "Em andamento"])
        qtd_atrasados = len(df_filtrado[df_filtrado["Status"] == "Atrasado"])
        
        # Salvings e Custos
        total_saving = pd.to_numeric(df_filtrado["Saving_R$"], errors='coerce').sum()
        total_ce_baseline = pd.to_numeric(df_filtrado["CE_Baseline_R$"], errors='coerce').sum()
        total_ce_geral = pd.to_numeric(df_filtrado["CE_R$"], errors='coerce').sum()
        
        def format_valor_kpi(valor):
            if pd.isna(valor) or valor == 0: return "R$ 0,00"
            valor = float(valor)
            if valor >= 1_000_000: return f"R$ {valor/1_000_000:,.2f}M".replace('.', '#').replace(',', '.').replace('#', ',')
            if valor >= 1_000: return f"R$ {valor/1_000:,.2f}K".replace('.', '#').replace(',', '.').replace('#', ',')
            return f"R$ {valor:,.2f}".replace('.', '#').replace(',', '.').replace('#', ',')

        card_col1, card_col2, card_col3, card_col4 = st.columns(4)
        
        cards = [
            ("Projetos Totais", qtd_total, "#002776"),
            ("Concluídos", qtd_concluidos, "#2B9348"),
            ("Em Andamento", qtd_andamento, "#2F80ED"),
            ("Atrasados", qtd_atrasados, "#D90429")
        ]
        
        for col, (titulo, valor, cor) in zip([card_col1, card_col2, card_col3, card_col4], cards):
            col.markdown(f'<div style="background-color:{cor};padding:20px;border-radius:15px;text-align:center;height:120px;display:flex;flex-direction:column;justify-content:center;"><h3 style="color:white;margin:0 0 8px 0;font-size:16px;">{titulo}</h3><h2 style="color:white;margin:0;font-size:20px;font-weight:bold;">{valor}</h2></div>', unsafe_allow_html=True)

        st.markdown("", unsafe_allow_html=True)
        card_col5, card_col6, card_col7 = st.columns(3)
        
        cards_financeiro = [
            ("Total Saving (R$)", format_valor_kpi(total_saving), "#6A4C93"),
            ("Total C.E. Baseline (R$)", format_valor_kpi(total_ce_baseline), "#F2994A"),
            ("Total C.E. Geral (R$)", format_valor_kpi(total_ce_geral), "#17a2b8")
        ]
        
        for col, (titulo, valor, cor) in zip([card_col5, card_col6, card_col7], cards_financeiro):
            col.markdown(f'<div style="background-color:{cor};padding:20px;border-radius:15px;text-align:center;height:120px;display:flex;flex-direction:column;justify-content:center;"><h3 style="color:white;margin:0 0 8px 0;font-size:16px;">{titulo}</h3><h2 style="color:white;margin:0;font-size:20px;font-weight:bold;">{valor}</h2></div>', unsafe_allow_html=True)
        
        st.markdown("", unsafe_allow_html=True)
        
        col_graf1, col_graf2 = st.columns(2)
        with col_graf1:
            resumo_status = df_filtrado['Status'].value_counts().reset_index()
            resumo_status.columns = ['Status', 'Quantidade']
            if not resumo_status.empty:
                fig_status = px.pie(resumo_status, values='Quantidade', names='Status', title='Distribuição de Projetos por Status',
                                    color_discrete_map={"A Iniciar": "#F2C94C", "Em andamento": "#2F80ED", "Atrasado": "#D90429", "Concluído": "#27AE60", "Cancelado": "#9B51E0", "Stand By": "#F2994A"})
                fig_status.update_traces(textposition='inside', textinfo='percent+label')
                st.plotly_chart(fig_status, use_container_width=True)
            else:
                st.info("Nenhum projeto encontrado para o gráfico de Status.")

        with col_graf2:
            df_saving = df_filtrado.groupby("Responsável")["Saving_R$"].sum().reset_index().sort_values("Saving_R$", ascending=False)
            df_saving = df_saving[df_saving["Saving_R$"] > 0]
            if not df_saving.empty:
                fig_saving = px.bar(df_saving, x="Responsável", y="Saving_R$", title="Saving por Responsável",
                                    color_discrete_sequence=px.colors.qualitative.Plotly)
                fig_saving.update_traces(texttemplate='R$ %{y:,.2s}', textposition='outside')
                fig_saving.update_layout(uniformtext_minsize=8, uniformtext_mode='hide', xaxis_title="Responsável", yaxis_title="Saving (R$)")
                st.plotly_chart(fig_saving, use_container_width=True)
            else:
                st.info("Nenhum saving registrado para o gráfico.")

        st.markdown("---")
        st.subheader("Tabela de Dados do Dashboard")
        st.dataframe(df_filtrado, use_container_width=True)
        st.download_button("📥 Download como Excel", convert_df_to_excel(df_filtrado), "dashboard_projetos.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else:
        st.info("Nenhum projeto encontrado com os filtros aplicados.")

elif aba == "Listar Projetos":
    st.subheader("📋 Listagem de Projetos")
    if not df_filtrado.empty:
        df_filtrado["Progresso_Porcentagem"] = df_filtrado.apply(
            lambda row: calcular_progresso(row.get('Data_Inicio'), row.get('Data_Termino')), axis=1
        )
        currency_cols = ["Orçamento", "Baseline", "Melhor_Proposta", "Preço_Inicial", "Preço_Final", "Saving_R$", "CE_Baseline_R$", "CE_R$"]
        for col in currency_cols:
            if col in df_filtrado.columns:
                df_filtrado[col] = pd.to_numeric(df_filtrado[col], errors='coerce').fillna(0)

        gb = GridOptionsBuilder.from_dataframe(df_filtrado)
        gb.configure_default_column(editable=False, resizable=True, wrapText=True, autoHeight=True)
        
        for col in currency_cols:
            if col in df_filtrado.columns:
                gb.configure_column(col, type=["numericColumn"], valueFormatter="value != null ? value.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' }) : ''")
        
        gb.configure_column("ID_Projeto", header_name="Código", pinned="left", width=120)
        gb.configure_column("Progresso_Porcentagem", header_name="Progresso (%)", type=["numericColumn"], width=120, valueFormatter="data.Progresso_Porcentagem.toFixed(2) + '%'")
        
        gb.configure_grid_options(domLayout='normal')
        gridOptions = gb.build()
        
        AgGrid(
            df_filtrado, gridOptions=gridOptions, enable_enterprise_modules=False,
            height=400, fit_columns_on_grid_load=True, reload_data=True
        )
        
    else:
        st.info("Nenhum projeto encontrado com os filtros aplicados.")

elif aba == "Cadastrar Projeto":
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
            st.markdown(f"**C.E R$:** {formatar_moeda(ce_r)}")
            st.markdown(f"**% C.E:** {formatar_percentual(percent_ce)}")

        if tem_orcamento:
            saving_r = orcamento - melhor_proposta
            saving_percent = (saving_r / orcamento) * 100 if orcamento != 0 else 0
            st.markdown(f"**Saving R$:** {formatar_moeda(saving_r)}")
            st.markdown(f"**% Saving:** {formatar_percentual(saving_percent)}")
        if linha_base:
            ce_baseline = baseline - melhor_proposta
            percent_baseline = (ce_baseline / baseline) * 100 if baseline != 0 else 0
            st.markdown(f"**C.E Baseline R$:** {formatar_moeda(ce_baseline)}")
            st.markdown(f"**% Baseline:** {formatar_percentual(percent_baseline)}")

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
                    "Data_Inicio": datetime.combine(data_inicio, datetime.min.time()), 
                    "Data_Termino": datetime.combine(data_termino, datetime.min.time()),
                    "Dias": (data_termino - data_inicio).days,
                    "Progresso_Porcentagem": calcular_progresso(data_inicio, data_termino),
                }
                try:
                    projetos_col.insert_one(projeto)
                    st.success(f"✅ Projeto salvo! Código: {id_projeto}")
                    carregar_dados.clear()
                    gerar_id_otimizado.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao salvar projeto: {e}")

elif aba == "Editar/Excluir":
    st.subheader("✍️ Editar ou Excluir Projeto")

    if df.empty:
        st.warning("Nenhum projeto disponível para editar.")
        st.stop()

    projetos_disponiveis = sorted(df["ID_Projeto"].dropna().unique())
    if not projetos_disponiveis:
        st.warning("Nenhum projeto com ID válido encontrado.")
        st.stop()

    projeto_selecionado = st.selectbox("Selecione um projeto para editar", ["Selecione..."] + projetos_disponiveis)
    
    if projeto_selecionado != "Selecione...":
        projeto_existente = projetos_col.find_one({"ID_Projeto": projeto_selecionado})
        
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
                    orcamento_val = projeto_existente.get("Orçamento", 0.0)
                    orcamento_str = st.text_input("Budget (R$)", value=f"{orcamento_val:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
                    orcamento = parse_currency_input(orcamento_str)
                if linha_base:
                    baseline_val = projeto_existente.get("Baseline", 0.0)
                    baseline_str = st.text_input("Baseline (R$)", value=f"{baseline_val:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
                    baseline = parse_currency_input(baseline_str)
                if tem_orcamento or linha_base:
                    melhor_proposta_val = projeto_existente.get("Melhor_Proposta", 0.0)
                    melhor_proposta_str = st.text_input("Melhor Proposta (R$)", value=f"{melhor_proposta_val:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
                    melhor_proposta = parse_currency_input(melhor_proposta_str)
                if not (tem_orcamento or linha_base):
                    preco_inicial_val = projeto_existente.get("Preço_Inicial", 0.0)
                    preco_inicial_str = st.text_input("Preço Inicial (R$)", value=f"{preco_inicial_val:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
                    preco_inicial = parse_currency_input(preco_inicial_str)
                    preco_final_val = projeto_existente.get("Preço_Final", 0.0)
                    preco_final_str = st.text_input("Preço Final (R$)", value=f"{preco_final_val:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
                    preco_final = parse_currency_input(preco_final_str)
                
                # Recalcular valores derivados
                saving_r = orcamento - melhor_proposta if tem_orcamento else 0
                saving_percent = (saving_r / orcamento) * 100 if tem_orcamento and orcamento != 0 else 0
                ce_baseline = baseline - melhor_proposta if linha_base else 0
                percent_baseline = (ce_baseline / baseline) * 100 if linha_base and baseline != 0 else 0
                ce_r = preco_inicial - preco_final if not (tem_orcamento or linha_base) else 0
                percent_ce = (ce_r / preco_inicial) * 100 if not (tem_orcamento or linha_base) and preco_inicial != 0 else 0

                # Exibir valores calculados
                if tem_orcamento:
                    st.markdown(f"**Saving R$:** {formatar_moeda(saving_r)}")
                    st.markdown(f"**% Saving:** {formatar_percentual(saving_percent)}")
                if linha_base:
                    st.markdown(f"**C.E Baseline R$:** {formatar_moeda(ce_baseline)}")
                    st.markdown(f"**% Baseline:** {formatar_percentual(percent_baseline)}")
                if not (tem_orcamento or linha_base):
                    st.markdown(f"**C.E R$:** {formatar_moeda(ce_r)}")
                    st.markdown(f"**% C.E:** {formatar_percentual(percent_ce)}")
                
                st.markdown("---")
                st.write("### Status e Datas")
                col_status, col_data_inicio, col_data_termino = st.columns(3)
                with col_status:
                    status_idx = STATUS.index(projeto_existente.get("Status", "A Iniciar")) if projeto_existente.get("Status") in STATUS else 0
                    status = st.selectbox("Status", STATUS, index=status_idx, key="edit_status")
                with col_data_inicio:
                    data_inicio_val = to_date(projeto_existente.get("Data_Inicio", date.today()))
                    data_inicio = st.date_input("Data de Início", value=data_inicio_val, format="DD/MM/YYYY", key="edit_data_inicio")
                with col_data_termino:
                    data_termino_val = to_date(projeto_existente.get("Data_Termino", date.today()))
                    data_termino = st.date_input("Data de Término", value=data_termino_val, format="DD/MM/YYYY", key="edit_data_termino")
                
                col_botoes_edit = st.columns(2)
                with col_botoes_edit[0]:
                    submit_update = st.form_submit_button("Salvar Alterações", type="primary")
                with col_botoes_edit[1]:
                    # Adicionando uma chave para o botão de exclusão para evitar conflitos
                    delete_button = st.form_submit_button("Excluir Projeto", type="secondary", key="delete_button")
                
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
                        try:
                            result = projetos_col.update_one({"ID_Projeto": projeto_selecionado}, {"$set": dados_atualizados})
                            if result.modified_count > 0:
                                st.success(f"✅ Projeto '{projeto_selecionado}' atualizado com sucesso!")
                                carregar_dados.clear()
                                st.rerun()
                            else:
                                st.info("Nenhuma alteração detectada. O projeto não foi modificado.")
                        except Exception as e:
                            st.error(f"❌ Erro ao atualizar o projeto: {e}")
                
                if delete_button:
                    try:
                        resultado = projetos_col.delete_one({"ID_Projeto": projeto_selecionado})
                        if resultado.deleted_count > 0:
                            st.success(f"🗑️ Projeto '{projeto_selecionado}' foi excluído com sucesso!")
                            carregar_dados.clear()
                            st.rerun()
                        else:
                            st.error("O projeto não foi encontrado para exclusão. Pode já ter sido removido.")
                    except Exception as e:
                        st.error(f"❌ Erro ao excluir o projeto: {e}")
        else:
            st.error(f"Projeto com ID '{projeto_selecionado}' não encontrado no banco de dados.")



