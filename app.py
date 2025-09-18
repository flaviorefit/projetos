# =======================
# FUNÇÕES DE FORMATAÇÃO
# =======================
def formatar_moeda(valor):
    """Formata um valor numérico como moeda brasileira (R$)."""
    if pd.isna(valor) or valor is None:
        return "R$ 0,00"
    valor_float = float(valor)
    return f"R$ {valor_float:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def formatar_percentual(valor):
    """Formata um valor numérico como percentual com duas casas decimais."""
    if pd.isna(valor) or valor is None:
        return "0,00%"
    valor_float = float(valor)
    return f"{valor_float:.2f}%".replace(".", ",")

# =======================
# FUNÇÃO DE CONVERSÃO PARA EXCEL
# =======================
def convert_df_to_excel(df):
    """Converte um DataFrame para um arquivo Excel em memória."""
    output = io.BytesIO()
    for col in df.select_dtypes(include=['datetimetz']).columns:
        df[col] = df[col].dt.tz_localize(None)
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Dados')
    processed_data = output.getvalue()
    return processed_data

# =======================
# FUNÇÕES DE FILTRO (CORREÇÃO: MOVIDAS PARA O TOPO)
# =======================
def aplicar_filtros(df, prefixo=""):
    """
    Cria os widgets de filtro na interface, permitindo seleção múltipla.
    """
    df["Status"] = df["Status"].fillna("Não Informado")
    df["Base"] = df["Base"].fillna("Não Informada")
    df["Comprador"] = df["Comprador"].fillna("Não Informado")
    df["Fornecedor"] = df["Fornecedor"].astype(str).fillna("Não Informado")
    df["Requisitante"] = df["Requisitante"].astype(str).fillna("Não Informado")

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
    """
    Filtra o DataFrame com base nas seleções.
    Se uma lista de filtro estiver vazia, o filtro não é aplicado.
    """
    df_filtrado = df.copy()

    if requisitante:
        df_filtrado = df_filtrado[df_filtrado["Requisitante"].isin(requisitante)]
    if status:
        df_filtrado = df_filtrado[df_filtrado["Status"].isin(status)]
    if base:
        df_filtrado = df_filtrado[df_filtrado["Base"].isin(base)]
    if comprador:
        df_filtrado = df_filtrado[df_filtrado["Comprador"].isin(comprador)]
    if fornecedor:
        df_filtrado = df_filtrado[df_filtrado["Fornecedor"].isin(fornecedor)]
    if descricao:
        df_filtrado = df_filtrado[df_filtrado["Descrição"].str.contains(descricao, case=False, na=False)]
    if ano != "Todos":
        df_filtrado = df_filtrado[df_filtrado['Devolução Gestão'].notna() & (df_filtrado['Devolução Gestão'].dt.year == ano)]

    return df_filtrado

# =======================
# CONFIGURAÇÃO DA PÁGINA
# =======================
st.set_page_config(page_title="Sistema de Requisições", layout="wide")

# =======================
# SISTEMA DE LOGIN
# =======================
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def verificar_login(usuario, senha):
    usuarios_validos = {info["username"]: hash_password(info["password"]) for _, info in st.secrets["usuarios"].items()}
    return hash_password(senha) == usuarios_validos.get(usuario)

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
        st.markdown("<h1 style='text-align: center; color: #002776;'>Sistema de Requisições</h1>", unsafe_allow_html=True)
        
        with st.form("login_form"):
            usuario = st.text_input("Usuário", placeholder="Digite seu usuário")
            senha = st.text_input("Senha", type="password", placeholder="Digite sua senha")
            if st.form_submit_button("Entrar", use_container_width=True, type="primary"):
                if verificar_login(usuario, senha):
                    st.session_state.login_realizado = True
                    st.session_state.usuario_logado = usuario
                    st.session_state.user_role = "requisitante" if usuario == "requisitante" else "admin"
                    st.success("Login realizado com sucesso!")
                    st.rerun()
                else:
                    st.error("Usuário ou senha inválidos.")
    st.markdown('</div>', unsafe_allow_html=True)

def logout():
    st.session_state.clear()
    st.rerun()

# =======================
# VERIFICAÇÃO DE LOGIN
# =======================
if not st.session_state.get("login_realizado"):
    tela_login()
    st.stop()

# =======================
# ESTILO DA BARRA LATERAL
# =======================
st.markdown(
    """
    <style>
    [data-testid="stSidebar"] { background-color: #c6bed0; }
    [data-testid="stSidebar"] .stRadio label { color: white !important; }
    [data-testid="stSidebar"] .streamlit-expanderHeader { color: white !important; }
    [data-testid="stSidebar"] .stSelectbox label, [data-testid="stSidebar"] .stTextInput label, [data-testid="stSidebar"] .stDateInput label { color: #000000 !important; font-weight: bold !important; }
    </style>
    """,
    unsafe_allow_html=True
)

# =======================
# CABEÇALHO
# =======================
col1, col2, col3 = st.columns([1, 6, 2])
with col1:
    try:
        st.image(Image.open("Imagem_gulf.png"), width=100)
    except FileNotFoundError:
        pass
with col2:
    st.markdown("<h1 style='color:#002776; font-size:36px; font-weight:bold;'>Monitoramento de Demandas Gulf</h1>", unsafe_allow_html=True)
with col3:
    st.markdown(f"**👤 Usuário:** {st.session_state.usuario_logado}")
    if st.button("🚪 Logout", type="secondary"):
        logout()

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
requisicoes_col = db[st.secrets["mongo_collection_requisicoes"]]
st.sidebar.success("✅ Conectado")

# =======================
# CARREGAR DADOS
# =======================
@st.cache_data(ttl=10)
def carregar_dados():
    try:
        df = pd.DataFrame(list(requisicoes_col.find()))
        if '_id' in df.columns:
            df.drop(columns=['_id'], inplace=True)
        colunas_essenciais = ['Nº de Pedido', 'Status', 'Base', 'Comprador', 'Fornecedor', 'Descrição', 'Devolução Gestão', 'Requisitante', 'Preço Final', 'Diferença R$']
        for col in colunas_essenciais:
            if col not in df.columns:
                df[col] = pd.NA
        for col in df.columns:
            if 'Data' in col or 'Gestão' in col or 'Diretoria' in col or 'Minuta' in col:
                df[col] = pd.to_datetime(df[col], errors='coerce')
        return df
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return pd.DataFrame()

df = carregar_dados()
