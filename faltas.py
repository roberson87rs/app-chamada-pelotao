import streamlit as st
import pandas as pd
from datetime import datetime, date
import time
import psycopg2
import hashlib
import os
import warnings
import streamlit.components.v1 as components

# Ignorar avisos desnecessários do pandas no terminal
warnings.filterwarnings('ignore', category=UserWarning)

# Configuração da página
st.set_page_config(page_title="Efetivo OM", page_icon="brasao.png", layout="wide", initial_sidebar_state="expanded")

# --- CONEXÃO COM O SUPABASE (POOLER) ---
SUPABASE_URL = "postgresql://postgres.jgzhlalaczpmecwqpofg:1723Rsh32335770@aws-0-sa-east-1.pooler.supabase.com:6543/postgres?sslmode=require"

# Constantes Hierárquicas Globais
ORDEM_HIERARQUICA = ["Gen Ex", "Gen Div", "Gen Bda", "Cel", "Ten Cel", "Maj", "Cap", "1º Ten", "2º Ten", "Asp Of", "S Ten", "1º Sgt", "2º Sgt", "3º Sgt", "Cb", "Sd EP", "Sd EV"]
PG_UPPER_MAP = {rank.upper(): rank for rank in ORDEM_HIERARQUICA}

def get_connection():
    return psycopg2.connect(SUPABASE_URL)

def hash_senha(senha):
    return hashlib.sha256(senha.encode()).hexdigest()

def formatar_nome_completo(nome):
    if not nome:
        return ""
    excecoes = ["de", "da", "do", "das", "dos", "e"]
    partes = nome.strip().lower().split()
    formatado = [p.capitalize() if p not in excecoes else p for p in partes]
    return " ".join(formatado)

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS pelotoes (id SERIAL PRIMARY KEY, nome_pelotao TEXT UNIQUE)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS fracoes (id SERIAL PRIMARY KEY, nome_fracao TEXT UNIQUE, pelotao TEXT DEFAULT 'Geral', status TEXT DEFAULT 'APROVADA')''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS usuarios (id SERIAL PRIMARY KEY, usuario TEXT UNIQUE, identidade TEXT UNIQUE, senha TEXT, pg TEXT, nome TEXT, fracao TEXT, pelotao TEXT DEFAULT 'Geral', perfil TEXT, nome_completo TEXT DEFAULT '')''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS militares (id SERIAL PRIMARY KEY, identidade TEXT UNIQUE, pg TEXT, nome TEXT, nome_completo TEXT DEFAULT '', fracao TEXT, pelotao TEXT DEFAULT 'Geral', celular TEXT DEFAULT '', whatsapp TEXT DEFAULT '', telefone TEXT DEFAULT '', email TEXT DEFAULT '', endereco TEXT DEFAULT '', presenca INTEGER DEFAULT 0, falta INTEGER DEFAULT 0, justificativa TEXT DEFAULT '', ultimo_gerente TEXT DEFAULT '-', ultima_atualizacao TEXT DEFAULT '-')''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS ausencias_futuras (id SERIAL PRIMARY KEY, nome_militar TEXT, fracao TEXT, data_prevista TEXT, motivo TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS historico (id SERIAL PRIMARY KEY, data_hora TEXT, pg TEXT, nome TEXT, fracao TEXT, pelotao TEXT DEFAULT 'Geral', status TEXT, justificativa TEXT, gerente_responsavel TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS ferias (id SERIAL PRIMARY KEY, identidade TEXT, data_inicio DATE, data_fim DATE, bi TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS viagens (id SERIAL PRIMARY KEY, identidade TEXT, nome TEXT, fracao TEXT, pelotao TEXT DEFAULT 'Geral', data_ida DATE, data_volta DATE, cidade TEXT, pais TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS backup_deletados (id SERIAL PRIMARY KEY, identidade TEXT, pg TEXT, nome TEXT, fracao TEXT, pelotao TEXT DEFAULT 'Geral', celular TEXT, whatsapp TEXT, telefone TEXT, email TEXT, endereco TEXT, usuario TEXT, senha TEXT, perfil TEXT, data_exclusao TEXT, nome_completo TEXT DEFAULT '')''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS solicitacoes_dados (id SERIAL PRIMARY KEY, identidade TEXT, pg TEXT, nome TEXT, celular TEXT, whatsapp TEXT, telefone TEXT, email TEXT, endereco TEXT, status TEXT DEFAULT 'PENDENTE')''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS solicitacoes_pessoal (
                        id SERIAL PRIMARY KEY, 
                        tipo TEXT, 
                        identidade TEXT, 
                        pg TEXT, 
                        nome TEXT, 
                        nome_completo TEXT, 
                        pelotao_destino TEXT, 
                        fracao_destino TEXT, 
                        status TEXT DEFAULT 'PENDENTE'
                    )''')
    
    conn.commit()
    
    # Criar admin geral se não existir na tabela de usuários
    cursor.execute("SELECT COUNT(*) FROM usuarios WHERE identidade = '000000'")
    if cursor.fetchone()[0] == 0:
        senha_padrao = hash_senha("1234")
        cursor.execute("INSERT INTO usuarios (usuario, identidade, senha, pg, nome, nome_completo, fracao, pelotao, perfil) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING", 
                       ("admin", "000000", senha_padrao, "Cel", "ADMIN", "Administrador Geral do Sistema", "S1", "Geral", "Administrador"))
        
    # Assegurar que o Administrador NUNCA apareça na tabela de efetivo (militares)
    cursor.execute("DELETE FROM militares WHERE identidade = '000000'")
    conn.commit()
        
    cursor.close()
    conn.close()

try:
    init_db()
except Exception as e:
    st.error(f"Erro ao conectar ou atualizar o Supabase: {e}")
    st.stop()

# --- GESTÃO DE SESSÃO ---
if 'logado' not in st.session_state:
    st.session_state.logado = False
if 'ultima_atividade' not in st.session_state:
    st.session_state.ultima_atividade = time.time()

TEMPO_LIMITE_INATIVIDADE = 600
if st.session_state.logado:
    tempo_atual = time.time()
    if (tempo_atual - st.session_state.ultima_atividade) > TEMPO_LIMITE_INATIVIDADE:
        st.session_state.logado = False
        st.warning("⚠️ Sessão expirada por inatividade (10 minutos). Por favor, faça login novamente.")
        st.rerun()
    else:
        st.session_state.ultima_atividade = tempo_atual

def login():
    if os.path.exists("brasao.png"):
        col_img, col_txt = st.columns([1, 8])
        with col_img: st.image("brasao.png", width=100)
        with col_txt:
            st.title("Sistema Integrado de Controle de Faltas")
            st.markdown("Identifique-se informando o seu **Usuário** ou **Identidade** e sua senha.")
    else:
        st.title("Sistema Integrado de Controle de Faltas")
    
    st.markdown("---")
    with st.form("login_form"):
        login_input = st.text_input("Usuário ou Nº de Identidade")
        senha = st.text_input("Senha", type="password")
        submit = st.form_submit_button("Entrar no Sistema")
        
        if submit:
            conn = get_connection()
            cursor = conn.cursor()
            senha_cript = hash_senha(senha)
            cursor.execute("SELECT usuario, identidade, pg, nome, fracao, perfil, pelotao, nome_completo FROM usuarios WHERE (usuario = %s OR identidade = %s) AND senha = %s", (login_input, login_input, senha_cript))
            user = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if user:
                st.session_state.logado = True
                st.session_state.usuario_login = user[0]
                st.session_state.identidade_atual = user[1]
                st.session_state.pg = user[2]
                st.session_state.nome_guerra = user[3]
                st.session_state.fracao = user[4]
                
                perfis_db = user[5]
                st.session_state.perfis_usuario = [p.strip() for p in perfis_db.split(',')] if perfis_db else ["Convencional"]
                st.session_state.perfil_ativo = st.session_state.perfis_usuario[0]
                st.session_state.pelotao = user[6] if len(user) > 6 else 'Geral'
                st.session_state.nome_completo = user[7] if len(user) > 7 and user[7] else user[3]
                st.session_state.ultima_atividade = time.time()
                st.rerun()
            else:
                st.error("Usuário/Identidade ou senha incorretos!")

def painel_convencional_comum():
    with st.expander("🔑 Alterar Minha Senha"):
        with st.form("form_senha"):
            nova_senha = st.text_input("Nova Senha", type="password")
            confirma_senha = st.text_input("Confirme a Nova Senha", type="password")
            if st.form_submit_button("Salvar Nova Senha"):
                if nova_senha == confirma_senha and len(nova_senha) > 0:
                    conn = get_connection()
                    cur = conn.cursor()
                    cur.execute("UPDATE usuarios SET senha = %s WHERE identidade = %s", (hash_senha(nova_senha), st.session_state.identidade_atual))
                    conn.commit()
                    conn.close()
                    st.success("✅ Senha alterada!")
                else:
                    st.error("As senhas não coincidem.")

# --- COMPONENTE COMPARTILHADO: PLANILHA DE FÉRIAS (COMANDANTES E ADMIN) ---
def exibir_planilha_ferias(conn, filtro_pelotao=None):
    st.subheader("🏖️ Planilha de Férias do Efetivo")
    st.write("Acompanhe o cronograma de férias. Utilize os filtros abaixo para refinar a busca.")
    
    query_ferias = """
        SELECT m.pg, m.nome as nome_guerra, m.nome_completo, m.fracao, m.pelotao, f.data_inicio, f.data_fim, f.bi 
        FROM ferias f
        INNER JOIN militares m ON f.identidade = m.identidade
        WHERE m.identidade != '000000'
    """
    if filtro_pelotao:
        query_ferias += f" AND m.pelotao = '{filtro_pelotao}'"
        
    df_todas_ferias = pd.read_sql_query(query_ferias, conn)
    
    if not df_todas_ferias.empty:
        df_todas_ferias['data_inicio'] = pd.to_datetime(df_todas_ferias['data_inicio'])
        df_todas_ferias['Mês Início'] = df_todas_ferias['data_inicio'].dt.month.map(
            {1:'Janeiro', 2:'Fevereiro', 3:'Março', 4:'Abril', 5:'Maio', 6:'Junho', 7:'Julho', 8:'Agosto', 9:'Setembro', 10:'Outubro', 11:'Novembro', 12:'Dezembro'}
        )
        
        c_filt1, c_filt2 = st.columns(2)
        with c_filt1:
            meses_disp = df_todas_ferias['Mês Início'].dropna().unique().tolist()
            filtro_mes = st.selectbox("Filtrar por Mês de Início", ["Todos"] + meses_disp)
        with c_filt2:
            pgs_unicos = df_todas_ferias['pg'].unique().tolist()
            pgs_ordenados = [p for p in ORDEM_HIERARQUICA if p in pgs_unicos] + [p for p in pgs_unicos if p not in ORDEM_HIERARQUICA]
            filtro_pg = st.selectbox("Filtrar por Posto/Graduação", ["Todos"] + pgs_ordenados)
            
        df_filtrado = df_todas_ferias.copy()
        if filtro_mes != "Todos":
            df_filtrado = df_filtrado[df_filtrado['Mês Início'] == filtro_mes]
        if filtro_pg != "Todos":
            df_filtrado = df_filtrado[df_filtrado['pg'] == filtro_pg]
            
        df_filtrado['data_inicio'] = df_filtrado['data_inicio'].dt.strftime('%d/%m/%Y')
        df_filtrado['data_fim'] = pd.to_datetime(df_filtrado['data_fim']).dt.strftime('%d/%m/%Y')
            
        df_filtrado['pg_norm'] = df_filtrado['pg'].str.upper().map(PG_UPPER_MAP).fillna(df_filtrado['pg'])
        df_filtrado['pg_cat'] = pd.Categorical(df_filtrado['pg_norm'], categories=ORDEM_HIERARQUICA, ordered=True)
        
        colunas_exib = ['pg', 'nome_guerra', 'nome_completo', 'data_inicio', 'data_fim', 'fracao', 'pelotao', 'bi']
        if filtro_pelotao:
            colunas_exib.remove('pelotao')
            
        df_final = df_filtrado.sort_values(['data_inicio', 'pg_cat']).drop(columns=['pg_cat', 'pg_norm', 'Mês Início'])
        
        st.dataframe(df_final[colunas_exib], hide_index=True, use_container_width=True)
        st.caption(f"Exibindo {len(df_final)} período(s) de férias cadastrado(s).")
    else:
        st.info("Nenhuma férias registrada no momento.")


# --- PERFIL: USUÁRIO CONVENCIONAL ---
def tela_convencional():
    st.title(f"👤 Painel do Militar - {st.session_state.pg} {st.session_state.nome_guerra}")
    painel_convencional_comum()
    
    st.markdown("---")
    t_aus, t_ferias, t_viagem, t_dados = st.tabs(["🏥 Ausência Prevista", "🏖️ Registro de Férias", "✈️ Livro de Viagem", "📞 Atualizar Contatos"])
    
    with t_aus:
        with st.form("form_ausencia"):
            data_prevista = st.date_input("Data prevista da ausência")
            motivo = st.text_area("Justificativa (Ex: Consulta, Dispensa)")
            if st.form_submit_button("Enviar Aviso"):
                conn = get_connection()
                cur = conn.cursor()
                cur.execute("INSERT INTO ausencias_futuras (nome_militar, fracao, data_prevista, motivo) VALUES (%s, %s, %s, %s)",
                               (f"{st.session_state.pg} {st.session_state.nome_guerra}", st.session_state.fracao, str(data_prevista), motivo))
                conn.commit()
                conn.close()
                st.success("✅ Aviso enviado ao Gerente da sua fração!")
                
    with t_ferias:
        st.info("💡 As datas registradas aqui preencherão a chamada da sua seção automaticamente no período correspondente.")
        
        conn = get_connection()
        df_minhas_ferias = pd.read_sql_query("SELECT data_inicio, data_fim, bi FROM ferias WHERE identidade = %s ORDER BY data_inicio", conn, params=(st.session_state.identidade_atual,))
        
        if not df_minhas_ferias.empty:
            st.write("🗓️ **Seus Períodos de Férias Cadastrados:**")
            df_minhas_ferias['data_inicio'] = pd.to_datetime(df_minhas_ferias['data_inicio']).dt.strftime('%d/%m/%Y')
            df_minhas_ferias['data_fim'] = pd.to_datetime(df_minhas_ferias['data_fim']).dt.strftime('%d/%m/%Y')
            st.dataframe(df_minhas_ferias, hide_index=True, use_container_width=True)
            
            if st.button("🗑️ Apagar Registros e Começar de Novo", type="primary"):
                cur = conn.cursor()
                cur.execute("DELETE FROM ferias WHERE identidade = %s", (st.session_state.identidade_atual,))
                conn.commit()
                st.success("✅ Registros apagados com sucesso! A página será atualizada.")
                time.sleep(1)
                st.rerun()
        else:
            st.write("⚖️ **Cadastrar Novo Período de Férias**")
            num_parcelas = st.radio("Em quantas parcelas você deseja dividir suas férias?", [1, 2, 3], horizontal=True, help="1 parcela de 30 dias, 2 de 15 dias, ou 3 de 10 dias.")
            
            with st.form("form_ferias"):
                datas_escolhidas = []
                for i in range(num_parcelas):
                    st.markdown(f"**Parcela {i+1}**")
                    c_f1, c_f2 = st.columns(2)
                    with c_f1: dt_ini = st.date_input(f"Início da Parcela {i+1}", key=f"dt_ini_{i}")
                    with c_f2: dt_fim = st.date_input(f"Fim da Parcela {i+1}", key=f"dt_fim_{i}")
                    datas_escolhidas.append((dt_ini, dt_fim))
                    
                bi_pub = st.text_input("BI de Publicação (Opcional. Ex: BI Nr 123)")
                
                if st.form_submit_button("Gravar Férias no Sistema"):
                    cur = conn.cursor()
                    try:
                        for dt_ini, dt_fim in datas_escolhidas:
                            cur.execute("INSERT INTO ferias (identidade, data_inicio, data_fim, bi) VALUES (%s, %s, %s, %s)",
                                        (st.session_state.identidade_atual, dt_ini, dt_fim, bi_pub))
                        conn.commit()
                        st.success("✅ Férias registradas no sistema! Atualizando...")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        conn.rollback()
                        st.error(f"Erro ao salvar: {e}")
        conn.close()

    with t_viagem:
        st.write("Livro de Registro de Viagens (Visível aos Comandantes)")
        with st.form("form_viagem"):
            v1, v2 = st.columns(2)
            with v1: v_ida = st.date_input("Data de Ida")
            with v2: v_volta = st.date_input("Data de Retorno")
            v3, v4 = st.columns(2)
            with v3: v_cid = st.text_input("Cidade de Destino")
            with v4: v_pais = st.text_input("País")
            if st.form_submit_button("Registrar no Livro de Viagens"):
                conn = get_connection()
                cur = conn.cursor()
                cur.execute("INSERT INTO viagens (identidade, nome, fracao, pelotao, data_ida, data_volta, cidade, pais) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                            (st.session_state.identidade_atual, st.session_state.nome_guerra, st.session_state.fracao, st.session_state.pelotao, v_ida, v_volta, v_cid, v_pais))
                conn.commit()
                conn.close()
                st.success("✅ Viagem registrada com sucesso!")
                
    with t_dados:
        st.info("As alterações solicitadas aqui serão enviadas ao Administrador para aprovação.")
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT celular, whatsapp, telefone, email, endereco FROM militares WHERE identidade = %s", (st.session_state.identidade_atual,))
        dados_atuais = cur.fetchone() or ("", "", "", "", "")
        conn.close()
        
        with st.form("form_atualiza_contatos"):
            c_c1, c_c2, c_c3 = st.columns(3)
            with c_c1: n_cel = st.text_input("Telefone Celular", value=dados_atuais[0])
            with c_c2: n_wts = st.text_input("WhatsApp", value=dados_atuais[1])
            with c_c3: n_tel = st.text_input("Telefone Residencial/Fixo", value=dados_atuais[2])
            n_email = st.text_input("E-mail", value=dados_atuais[3])
            n_end = st.text_area("Endereço Completo", value=dados_atuais[4])
            
            if st.form_submit_button("Solicitar Atualização de Dados"):
                conn = get_connection()
                cur = conn.cursor()
                cur.execute("""INSERT INTO solicitacoes_dados (identidade, pg, nome, celular, whatsapp, telefone, email, endereco, status)
                               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'PENDENTE')""",
                            (st.session_state.identidade_atual, st.session_state.pg, st.session_state.nome_guerra, n_cel, n_wts, n_tel, n_email, n_end))
                conn.commit()
                conn.close()
                st.success("✅ Solicitação enviada! Aguarde a aprovação.")

def get_ferias_ativas(conn):
    cur = conn.cursor()
    cur.execute("SELECT identidade, data_inicio, data_fim, bi FROM ferias")
    todas_ferias = cur.fetchall()
    cur.close()
    hoje = date.today()
    ferias_ativas = {}
    for idt, dt_ini, dt_fim, bi in todas_ferias:
        if dt_ini <= hoje <= dt_fim:
            ferias_ativas[idt] = bi
    return ferias_ativas

# --- PERFIL: GERENTE ---
def tela_gerente():
    st.title(f"📋 Gestão da Fração - {st.session_state.fracao}")
    painel_convencional_comum()
    st.markdown("---")
    
    conn = get_connection()
    ferias_ativas = get_ferias_ativas(conn)
    
    tab_chamada, tab_plano = st.tabs(["📋 Chamada Diária", "📞 Plano de Chamada (Contatos)"])
    
    with tab_chamada:
        df_ausencias = pd.read_sql_query("SELECT nome_militar as Militar, data_prevista as Data, motivo as Motivo FROM ausencias_futuras WHERE fracao = %s ORDER BY data_prevista ASC", conn, params=(st.session_state.fracao,))
        if not df_ausencias.empty:
            with st.expander(f"⚠️ Você tem {len(df_ausencias)} aviso(s) de ausência na sua fração (Clique para ver)"):
                st.dataframe(df_ausencias, hide_index=True, use_container_width=True)
                if st.button("Limpar Todos os Avisos Recebidos"):
                    cur = conn.cursor()
                    cur.execute("DELETE FROM ausencias_futuras WHERE fracao = %s", (st.session_state.fracao,))
                    conn.commit()
                    st.rerun()
        else:
            st.info("Nenhum aviso de ausência pendente para a sua fração.")
            
        st.markdown("---")
        
        df_militares = pd.read_sql_query("SELECT id, identidade, pg, nome, fracao, presenca, falta, justificativa FROM militares WHERE fracao = %s AND identidade != '000000'", conn, params=(st.session_state.fracao,))
        
        df_militares['presenca'] = df_militares['presenca'].astype(bool)
        df_militares['falta'] = df_militares['falta'].astype(bool)
        
        for index, row in df_militares.iterrows():
            if row['identidade'] in ferias_ativas:
                df_militares.at[index, 'falta'] = True
                df_militares.at[index, 'presenca'] = False
                df_militares.at[index, 'justificativa'] = f"Férias ({ferias_ativas[row['identidade']]})"
                
        df_militares['pg_norm'] = df_militares['pg'].str.upper().map(PG_UPPER_MAP).fillna(df_militares['pg'])
        df_militares['pg_cat'] = pd.Categorical(df_militares['pg_norm'], categories=ORDEM_HIERARQUICA, ordered=True)
        df_militares = df_militares.sort_values(['pg_cat', 'nome']).drop(columns=['pg_cat', 'pg_norm'])
        
        with st.form("form_chamada_diaria"):
            editado = st.data_editor(
                df_militares,
                column_config={
                    "id": None, "identidade": None, 
                    "pg": st.column_config.TextColumn("P/G", disabled=True), 
                    "nome": st.column_config.TextColumn("NOME DE GUERRA", disabled=True), 
                    "fracao": None, 
                    "presenca": st.column_config.CheckboxColumn("PRESENÇA", default=False), 
                    "falta": st.column_config.CheckboxColumn("FALTA", default=False), 
                    "justificativa": st.column_config.TextColumn("JUSTIFICATIVA")
                },
                hide_index=True, use_container_width=True, key="editor_gerente"
            )
            
            submit_chamada = st.form_submit_button("💾 Salvar Chamada da Seção", type="primary")
            
            if submit_chamada:
                agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                gerente_nome = f"{st.session_state.pg} {st.session_state.nome_guerra}"
                cursor = conn.cursor()
                for index, row in editado.iterrows():
                    cursor.execute("UPDATE militares SET presenca = %s, falta = %s, justificativa = %s, ultimo_gerente = %s, ultima_atualizacao = %s WHERE id = %s",
                                   (int(row['presenca']), int(row['falta']), row['justificativa'], gerente_nome, agora, row['id']))
                conn.commit()
                st.success("✅ Chamada registrada com sucesso! (Visível em tempo real para os Comandantes)")
                st.rerun()
            
    with tab_plano:
        st.info("Abaixo constam os dados de contato atuais da sua fração (Apenas visualização).")
        df_contatos = pd.read_sql_query("SELECT pg, nome as nome_guerra, celular, whatsapp, telefone as residencial, email, endereco FROM militares WHERE fracao = %s AND identidade != '000000'", conn, params=(st.session_state.fracao,))
        
        df_contatos['pg_norm'] = df_contatos['pg'].str.upper().map(PG_UPPER_MAP).fillna(df_contatos['pg'])
        df_contatos['pg_cat'] = pd.Categorical(df_contatos['pg_norm'], categories=ORDEM_HIERARQUICA, ordered=True)
        df_contatos = df_contatos.sort_values(['pg_cat', 'nome_guerra']).drop(columns=['pg_cat', 'pg_norm'])
        
        st.dataframe(df_contatos, hide_index=True, use_container_width=True)

    conn.close()

# --- PERFIL: ADMINISTRADOR ---
def tela_administrador():
    st.title("🛡️ Painel do Administrador Geral")
    painel_convencional_comum()
    
    conn = get_connection()
    is_super_admin = (st.session_state.identidade_atual == '000000')
    
    pelotoes_bd = pd.read_sql_query("SELECT nome_pelotao FROM pelotoes", conn)['nome_pelotao'].tolist()
    if not pelotoes_bd: pelotoes_bd = ["Geral"]
    fracoes_bd = pd.read_sql_query("SELECT nome_fracao FROM fracoes WHERE status = 'APROVADA'", conn)['nome_fracao'].tolist()
    todas_fracoes_bd = pd.read_sql_query("SELECT nome_fracao FROM fracoes", conn)['nome_fracao'].tolist()
    
    abas_nomes = ["🏢 Estrutura (Pel/Fração)", "👥 Gestão de Efetivo", "🔑 Acessos", "📨 Solicitações", "🏖️ Gestão de Férias"]
    if is_super_admin: abas_nomes.append("🦸‍♂️ Restauração (Lixeira)")
        
    abas = st.tabs(abas_nomes)
    
    with abas[0]:
        st.subheader("1. Gestão de Pelotões")
        with st.form("form_novo_pelotao"):
            novo_pelotao = st.text_input("Nome do Novo Pelotão")
            if st.form_submit_button("Criar Pelotão") and novo_pelotao:
                try:
                    cur = conn.cursor()
                    cur.execute("INSERT INTO pelotoes (nome_pelotao) VALUES (%s)", (novo_pelotao.strip(),))
                    conn.commit()
                    st.success("Pelotão criado!")
                    st.rerun()
                except Exception as e:
                    conn.rollback()
                    st.error(f"Pelotão já existe ou erro: {e}")
        st.write("**Pelotões Ativos:**", pelotoes_bd)
        
        st.markdown("---")
        st.subheader("2. Gestão de Frações")
        df_pendentes = pd.read_sql_query("SELECT id, nome_fracao, pelotao FROM fracoes WHERE status = 'PENDENTE'", conn)
        if not df_pendentes.empty:
            st.warning("⚠️ Solicitações de novas frações aguardando sua autorização:")
            for idx, row in df_pendentes.iterrows():
                col_texto, col_ok, col_rej = st.columns([4,1,1])
                col_texto.write(f"Fração **{row['nome_fracao']}** solicitada para o **{row['pelotao']}**")
                if col_ok.button("✔️ Autorizar", key=f"ok_{row['id']}"):
                    cur = conn.cursor()
                    cur.execute("UPDATE fracoes SET status = 'APROVADA' WHERE id = %s", (row['id'],))
                    conn.commit()
                    st.rerun()
                if col_rej.button("❌ Rejeitar", key=f"rej_{row['id']}"):
                    cur = conn.cursor()
                    cur.execute("DELETE FROM fracoes WHERE id = %s", (row['id'],))
                    conn.commit()
                    st.rerun()
        
        with st.form("form_nova_fracao"):
            nf_nome = st.text_input("Nome da Nova Fração")
            nf_pel = st.selectbox("Vincular ao Pelotão", pelotoes_bd)
            if st.form_submit_button("Adicionar Fração Oficial") and nf_nome:
                try:
                    cur = conn.cursor()
                    cur.execute("INSERT INTO fracoes (nome_fracao, pelotao, status) VALUES (%s, %s, 'APROVADA')", (nf_nome.strip(), nf_pel))
                    conn.commit()
                    st.success("Fração adicionada!")
                    st.rerun()
                except Exception as e:
                    conn.rollback()
                    st.error(f"Fração já existe ou erro: {e}")
        st.write("**Frações Aprovadas:**", fracoes_bd)
        
        st.markdown("---")
        st.subheader("❌ Excluir Estruturas")
        col_del_pel, col_del_frac = st.columns(2)
        with col_del_pel:
            pel_del = st.selectbox("Excluir Pelotão", pelotoes_bd)
            if st.button("Excluir Pelotão Selecionado"):
                cur = conn.cursor()
                cur.execute("DELETE FROM pelotoes WHERE nome_pelotao = %s", (pel_del,))
                conn.commit()
                st.success("Pelotão removido!")
                st.rerun()
        with col_del_frac:
            frac_del = st.selectbox("Excluir Fração", todas_fracoes_bd)
            if st.button("Excluir Fração Selecionada"):
                cur = conn.cursor()
                cur.execute("DELETE FROM fracoes WHERE nome_fracao = %s", (frac_del,))
                conn.commit()
                st.success("Fração removida!")
                st.rerun()

        st.markdown("---")
        st.subheader("🧹 Limpeza e Manutenção do Banco de Dados")
        st.write("Selecione qual tipo de informação deseja apagar do sistema.")
        
        c_limp1, c_limp2 = st.columns(2)
        
        with c_limp1:
            st.info("🕒 **Limpar Faltas e Históricos**\nApaga o histórico de chamadas, férias, viagens e ausências previstas, além de zerar a chamada atual. Mantém o efetivo intacto.")
            if st.button("🗑️ Apagar Registros de Faltas", type="primary"):
                cur = conn.cursor()
                try:
                    cur.execute("DELETE FROM historico")
                    cur.execute("DELETE FROM ausencias_futuras")
                    cur.execute("DELETE FROM ferias")
                    cur.execute("DELETE FROM viagens")
                    cur.execute("UPDATE militares SET presenca = 0, falta = 0, justificativa = '', ultimo_gerente = '-', ultima_atualizacao = '-'")
                    conn.commit()
                    st.success("✅ Histórico de faltas limpo com sucesso!")
                    st.rerun()
                except Exception as e:
                    conn.rollback()
                    st.error(f"Erro ao limpar faltas: {e}")
                    
        with c_limp2:
            st.error("⚠️ **Limpar Efetivo (Zeramento)**\nApaga TODOS os militares, usuários e lixeiras do banco, exceto a sua conta de Administrador (000000). Mantém a estrutura de pelotões.")
            if st.button("🗑️ Apagar Todo o Efetivo", type="primary"):
                cur = conn.cursor()
                try:
                    cur.execute("DELETE FROM militares WHERE identidade != '000000'")
                    cur.execute("DELETE FROM usuarios WHERE identidade != '000000'")
                    cur.execute("DELETE FROM backup_deletados")
                    cur.execute("DELETE FROM solicitacoes_dados")
                    cur.execute("DELETE FROM solicitacoes_pessoal")
                    conn.commit()
                    st.success("✅ Todo o efetivo foi apagado com sucesso!")
                    st.rerun()
                except Exception as e:
                    conn.rollback()
                    st.error(f"Erro ao apagar efetivo: {e}")
        
    with abas[1]:
        st.subheader("Adicionar Novo Militar (Direto)")
        
        admin_pel_escolhido = st.selectbox("Pelotão", pelotoes_bd, key="admin_pel_cad_inst")
        frac_filtradas_admin = pd.read_sql_query("SELECT nome_fracao FROM fracoes WHERE pelotao = %s AND status = 'APROVADA'", conn, params=(admin_pel_escolhido,))['nome_fracao'].tolist()
        
        with st.form("novo_militar"):
            c1, c2, c3 = st.columns([1,1,2])
            with c1: nova_identidade = st.text_input("Identidade")
            with c2: novo_pg = st.text_input("Posto/Graduação")
            with c3: novo_nome_guerra = st.text_input("Nome de Guerra (Ficará em Maiúsculo)").upper()
            
            c4, c5 = st.columns([2,1])
            with c4: novo_nome_completo = st.text_input("Nome Completo")
            with c5: nova_fracao = st.selectbox("Fração", frac_filtradas_admin if frac_filtradas_admin else fracoes_bd, key="admin_frac_cad")
            
            if st.form_submit_button("Cadastrar Novo Militar"):
                cur = conn.cursor()
                try:
                    novo_nome_completo_fmt = formatar_nome_completo(novo_nome_completo)
                    
                    cur.execute("SELECT COUNT(*) FROM militares WHERE identidade = %s", (nova_identidade,))
                    existe_mil = cur.fetchone()[0] > 0
                    
                    if existe_mil:
                        cur.execute("""UPDATE militares SET pg = %s, nome = %s, nome_completo = %s, fracao = %s, pelotao = %s WHERE identidade = %s""",
                                    (novo_pg, novo_nome_guerra, novo_nome_completo_fmt, nova_fracao, admin_pel_escolhido, nova_identidade))
                    else:
                        cur.execute("""INSERT INTO militares (identidade, pg, nome, nome_completo, fracao, pelotao) VALUES (%s, %s, %s, %s, %s, %s)""", 
                                    (nova_identidade, novo_pg, novo_nome_guerra, novo_nome_completo_fmt, nova_fracao, admin_pel_escolhido))
                    
                    cur.execute("SELECT COUNT(*) FROM usuarios WHERE identidade = %s", (nova_identidade,))
                    existe_usr = cur.fetchone()[0] > 0
                    
                    if not existe_usr:
                        cur.execute("""INSERT INTO usuarios (usuario, identidade, senha, pg, nome, nome_completo, fracao, pelotao, perfil) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                                    (novo_nome_guerra.lower(), nova_identidade, hash_senha("1234"), novo_pg, novo_nome_guerra, novo_nome_completo_fmt, nova_fracao, admin_pel_escolhido, "Convencional"))
                    else:
                        cur.execute("""UPDATE usuarios SET pg = %s, nome = %s, nome_completo = %s, fracao = %s, pelotao = %s WHERE identidade = %s""",
                                    (novo_pg, novo_nome_guerra, novo_nome_completo_fmt, nova_fracao, admin_pel_escolhido, nova_identidade))
                        
                    conn.commit()
                    st.success("Militar cadastrado com sucesso! (Senha padrão: 1234)")
                except Exception as e: 
                    conn.rollback()
                    st.error(f"Erro ao cadastrar: {e}")
                
        st.markdown("---")
        st.subheader("⚠️ Gerenciar Efetivo Existente")
        
        if 'admin_gestao_pel' not in st.session_state:
            st.session_state.admin_gestao_pel = pelotoes_bd[0] if pelotoes_bd else "Geral"

        def atualizar_gestao_pel():
            st.session_state.admin_gestao_pel = st.session_state.sb_gestao_pel

        filtro_gestao_pel = st.selectbox("1. Filtrar por Pelotão para Gerenciamento", pelotoes_bd, key="sb_gestao_pel", on_change=atualizar_gestao_pel)
        
        try:
            query_uniao = """
                SELECT identidade, pg, nome, nome_completo, fracao, pelotao FROM militares WHERE pelotao = %s AND identidade != '000000'
                UNION
                SELECT identidade, pg, nome, nome_completo, fracao, pelotao FROM usuarios WHERE pelotao = %s AND identidade != '000000'
            """
            df_all = pd.read_sql_query(query_uniao, conn, params=(st.session_state.admin_gestao_pel, st.session_state.admin_gestao_pel))
            df_all = df_all.drop_duplicates(subset=['identidade'])
        except Exception as e:
            conn.rollback()
            df_all = pd.DataFrame()
            st.error(f"Erro ao carregar efetivo: {e}")
        
        if not df_all.empty:
            df_all['pg_norm'] = df_all['pg'].str.upper().map(PG_UPPER_MAP).fillna(df_all['pg'])
            df_all['pg_cat'] = pd.Categorical(df_all['pg_norm'], categories=ORDEM_HIERARQUICA, ordered=True)
            df_all = df_all.sort_values(['pg_cat', 'nome'])
            df_exibicao = df_all.drop(columns=['pg_cat', 'pg_norm'])
            
            militar_selecionado = st.selectbox("2. Selecione um militar do pelotão", df_exibicao['identidade'] + " - " + df_exibicao['pg'] + " " + df_exibicao['nome'])
            
            col_ex, col_senha, col_edit = st.columns(3)
            
            if col_ex.button("❌ Excluir Militar"):
                if militar_selecionado:
                    idt_del = militar_selecionado.split(" - ")[0]
                    agora_del = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                    cur = conn.cursor()
                    try:
                        cur.execute("SELECT pg, nome, fracao, celular, whatsapp, telefone, email, endereco, pelotao, nome_completo FROM militares WHERE identidade = %s", (idt_del,))
                        mil_data = cur.fetchone() or ("", "", "", "", "", "", "", "", "Geral", "")
                        cur.execute("SELECT usuario, senha, perfil FROM usuarios WHERE identidade = %s", (idt_del,))
                        usr_data = cur.fetchone() or ("", "", "")
                        
                        cur.execute("""INSERT INTO backup_deletados (identidade, pg, nome, fracao, pelotao, celular, whatsapp, telefone, email, endereco, usuario, senha, perfil, data_exclusao, nome_completo)
                                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                                    (idt_del, mil_data[0], mil_data[1], mil_data[2], mil_data[8], mil_data[3], mil_data[4], mil_data[5], mil_data[6], mil_data[7], usr_data[0], usr_data[1], usr_data[2], agora_del, mil_data[9]))
                        
                        cur.execute("DELETE FROM militares WHERE identidade = %s", (idt_del,))
                        cur.execute("DELETE FROM usuarios WHERE identidade = %s", (idt_del,))
                        conn.commit()
                        st.success(f"Militar excluído e enviado para a lixeira.")
                        st.rerun()
                    except Exception as e:
                        conn.rollback()
                        st.error(f"Erro ao excluir: {e}")
                    
            if col_senha.button("🔑 Resetar Senha (1234)"):
                if militar_selecionado:
                    idt_res = militar_selecionado.split(" - ")[0]
                    cur = conn.cursor()
                    try:
                        cur.execute("UPDATE usuarios SET senha = %s WHERE identidade = %s", (hash_senha("1234"), idt_res))
                        conn.commit()
                        st.success(f"Senha redefinida!")
                    except Exception as e:
                        conn.rollback()
                        st.error(f"Erro ao resetar: {e}")

            with st.expander("✏️ Editar Dados do Militar Selecionado"):
                if militar_selecionado:
                    idt_edit = militar_selecionado.split(" - ")[0]
                    dados_edit = df_all[df_all['identidade'] == idt_edit].iloc[0]
                    
                    with st.form("form_edicao_rapida"):
                        e_pg = st.text_input("PG", value=dados_edit['pg'])
                        e_guerra = st.text_input("Nome de Guerra", value=dados_edit['nome']).upper()
                        e_completo = st.text_input("Nome Completo", value=dados_edit['nome_completo'])
                        
                        e_pelotao = st.selectbox("Pelotão", pelotoes_bd, index=pelotoes_bd.index(dados_edit['pelotao']) if dados_edit['pelotao'] in pelotoes_bd else 0)
                        frac_filtradas_edicao = pd.read_sql_query("SELECT nome_fracao FROM fracoes WHERE pelotao = %s AND status = 'APROVADA'", conn, params=(e_pelotao,))['nome_fracao'].tolist()
                        
                        e_fracao = st.selectbox("Fração", frac_filtradas_edicao if frac_filtradas_edicao else fracoes_bd, index=(frac_filtradas_edicao.index(dados_edit['fracao']) if frac_filtradas_edicao and dados_edit['fracao'] in frac_filtradas_edicao else 0))
                        
                        if st.form_submit_button("Salvar Edição"):
                            cur = conn.cursor()
                            try:
                                e_completo_fmt = formatar_nome_completo(e_completo)
                                cur.execute("UPDATE militares SET pg=%s, nome=%s, nome_completo=%s, pelotao=%s, fracao=%s WHERE identidade=%s", (e_pg, e_guerra, e_completo_fmt, e_pelotao, e_fracao, idt_edit))
                                cur.execute("UPDATE usuarios SET pg=%s, nome=%s, nome_completo=%s, pelotao=%s, fracao=%s WHERE identidade=%s", (e_pg, e_guerra, e_completo_fmt, e_pelotao, e_fracao, idt_edit))
                                conn.commit()
                                st.success("Dados alterados com sucesso!")
                                st.rerun()
                            except Exception as e:
                                conn.rollback()
                                st.error(f"Erro ao editar: {e}")

            st.markdown("---")
            st.subheader("📋 Relação do Efetivo do Pelotão Selecionado")
            st.dataframe(df_exibicao, hide_index=True, use_container_width=True)
        else:
            st.info("Nenhum militar cadastrado neste pelotão.")
            
    with abas[2]:
        st.subheader("Atribuir e Gerenciar Perfis de Acesso")
        try:
            query_uniao_acesso = """
                SELECT identidade, pg, nome, nome_completo, fracao, pelotao FROM militares WHERE identidade != '000000'
                UNION
                SELECT identidade, pg, nome, nome_completo, fracao, pelotao FROM usuarios WHERE identidade != '000000'
            """
            df_all_acc = pd.read_sql_query(query_uniao_acesso, conn)
            df_all_acc = df_all_acc.drop_duplicates(subset=['identidade'])
        except:
            df_all_acc = pd.DataFrame()

        if not df_all_acc.empty:
            militar_selecionado_tab5 = st.selectbox("Selecione o Militar para Gerenciar Acessos:", df_all_acc['identidade'] + " - " + df_all_acc['pg'] + " " + df_all_acc['nome'], key="sel_acesso")
            if militar_selecionado_tab5:
                idt_selecionada = militar_selecionado_tab5.split(" - ")[0]
                dados_mil = df_all_acc[df_all_acc['identidade'] == idt_selecionada].iloc[0]
                df_user = pd.read_sql_query("SELECT usuario, perfil FROM usuarios WHERE identidade = %s", conn, params=(idt_selecionada,))
                
                usuario_atual = ""
                perfis_atuais = ["Convencional"]
                if not df_user.empty:
                    usuario_atual = df_user.iloc[0]['usuario']
                    perfis_bd = df_user.iloc[0]['perfil']
                    if perfis_bd: perfis_atuais = [p.strip() for p in perfis_bd.split(',')]
                
                opcoes_permitidas = ["Convencional", "Gerente", "Administrador", "Comandante de Pelotão", "Comandante de OM"]
                perfis_corrigidos = [p if p != "Comandante" else "Comandante de Pelotão" for p in perfis_atuais if p in opcoes_permitidas or p == "Comandante"]
                perfis_atuais = list(set(perfis_corrigidos))
                        
                with st.form("form_atualiza_perfil"):
                    st.info(f"Modificando acessos de: **{dados_mil['pg']} {dados_mil['nome']}**")
                    u_usuario = st.text_input('Login (Ex: "sargento")', value=usuario_atual)
                    u_perfis = st.multiselect("Perfis de Acesso", opcoes_permitidas, default=perfis_atuais)
                    
                    if st.form_submit_button("Salvar Configurações de Acesso"):
                        perfis_str = ",".join(u_perfis)
                        cur = conn.cursor()
                        try:
                            cur.execute("SELECT COUNT(*) FROM militares WHERE identidade = %s", (idt_selecionada,))
                            if cur.fetchone()[0] == 0:
                                cur.execute("INSERT INTO militares (identidade, pg, nome, nome_completo, fracao, pelotao) VALUES (%s, %s, %s, %s, %s, %s)", 
                                            (idt_selecionada, dados_mil['pg'], dados_mil['nome'], dados_mil['nome_completo'], dados_mil['fracao'], dados_mil['pelotao']))
                            else:
                                cur.execute("UPDATE militares SET pg = %s, nome = %s, fracao = %s, pelotao = %s WHERE identidade = %s", 
                                            (dados_mil['pg'], dados_mil['nome'], dados_mil['fracao'], dados_mil['pelotao'], idt_selecionada))
                            
                            if not df_user.empty:
                                cur.execute("UPDATE usuarios SET usuario = %s, perfil = %s, pg = %s, nome = %s, nome_completo = %s, fracao = %s, pelotao = %s WHERE identidade = %s", 
                                            (u_usuario.lower(), perfis_str, dados_mil['pg'], dados_mil['nome'], dados_mil['nome_completo'], dados_mil['fracao'], dados_mil['pelotao'], idt_selecionada))
                            else:
                                cur.execute("INSERT INTO usuarios (usuario, identidade, senha, pg, nome, nome_completo, fracao, pelotao, perfil) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                                            (u_usuario.lower(), idt_selecionada, hash_senha("1234"), dados_mil['pg'], dados_mil['nome'], dados_mil['nome_completo'], dados_mil['fracao'], dados_mil['pelotao'], perfis_str))
                            conn.commit()
                            st.success("✅ Acessos atualizados!")
                        except Exception as e:
                            conn.rollback()
                            st.error(f"Erro ao salvar acesso: {e}")

    with abas[3]:
        st.subheader("📨 Solicitações (Pessoal, Gerências e Contatos)")
        
        st.markdown("#### 👥 Solicitações de Movimentação, Inclusão e Gerentes")
        df_req_pessoal = pd.read_sql_query("SELECT id, tipo, identidade, pg, nome, nome_completo, pelotao_destino, fracao_destino FROM solicitacoes_pessoal WHERE status = 'PENDENTE'", conn)
        
        if not df_req_pessoal.empty:
            for idx, row in df_req_pessoal.iterrows():
                acao_texto = f"Destino/Fração: {row['pelotao_destino']} / {row['fracao_destino']}"
                if row['tipo'] == 'REMOVER_GERENTE':
                    acao_texto = f"Solicitação de DESTITUIÇÃO do perfil de GERENTE ({row['pelotao_destino']})"
                    
                with st.expander(f"📌 [{row['tipo']}] {row['pg']} {row['nome']} ➔ {acao_texto}"):
                    st.write(f"**Identidade:** {row['identidade']} | **Nome Completo:** {row['nome_completo']}")
                    c_acc_p, c_rej_p = st.columns(2)
                    
                    if c_acc_p.button("✔️ Autorizar Solicitação", key=f"acc_p_{row['id']}"):
                        cur = conn.cursor()
                        try:
                            if row['tipo'] == 'TRANSFERENCIA':
                                cur.execute("UPDATE militares SET pelotao = %s, fracao = %s WHERE identidade = %s", (row['pelotao_destino'], row['fracao_destino'], row['identidade']))
                                cur.execute("UPDATE usuarios SET pelotao = %s, fracao = %s WHERE identidade = %s", (row['pelotao_destino'], row['fracao_destino'], row['identidade']))
                            elif row['tipo'] == 'INCLUSAO':
                                cur.execute("SELECT COUNT(*) FROM militares WHERE identidade = %s", (row['identidade'],))
                                if cur.fetchone()[0] == 0:
                                    cur.execute("INSERT INTO militares (identidade, pg, nome, nome_completo, fracao, pelotao) VALUES (%s, %s, %s, %s, %s, %s)",
                                                (row['identidade'], row['pg'], row['nome'], row['nome_completo'], row['fracao_destino'], row['pelotao_destino']))
                                else:
                                    cur.execute("UPDATE militares SET pelotao = %s, fracao = %s, pg = %s, nome = %s, nome_completo = %s WHERE identidade = %s",
                                                (row['pelotao_destino'], row['fracao_destino'], row['pg'], row['nome'], row['nome_completo'], row['identidade']))
                                
                                cur.execute("SELECT COUNT(*) FROM usuarios WHERE identidade = %s", (row['identidade'],))
                                if cur.fetchone()[0] == 0:
                                    cur.execute("INSERT INTO usuarios (usuario, identidade, senha, pg, nome, nome_completo, fracao, pelotao, perfil) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                                                (row['nome'].lower(), row['identidade'], hash_senha("1234"), row['pg'], row['nome'], row['nome_completo'], row['fracao_destino'], row['pelotao_destino'], "Convencional"))
                            elif row['tipo'] == 'GERENTE':
                                cur.execute("SELECT perfil FROM usuarios WHERE identidade = %s", (row['identidade'],))
                                u_res = cur.fetchone()
                                perfis_atuais = [p.strip() for p in u_res[0].split(',')] if u_res and u_res[0] else ["Convencional"]
                                if "Gerente" not in perfis_atuais: perfis_atuais.append("Gerente")
                                novo_perfil_str = ",".join(perfis_atuais)
                                
                                cur.execute("UPDATE usuarios SET perfil = %s, fracao = %s, pelotao = %s WHERE identidade = %s", (novo_perfil_str, row['fracao_destino'], row['pelotao_destino'], row['identidade']))
                                cur.execute("UPDATE militares SET fracao = %s, pelotao = %s WHERE identidade = %s", (row['fracao_destino'], row['pelotao_destino'], row['identidade']))
                                
                            elif row['tipo'] == 'REMOVER_GERENTE':
                                cur.execute("SELECT perfil FROM usuarios WHERE identidade = %s", (row['identidade'],))
                                u_res = cur.fetchone()
                                if u_res and u_res[0]:
                                    perfis_atuais = [p.strip() for p in u_res[0].split(',')]
                                    if "Gerente" in perfis_atuais:
                                        perfis_atuais.remove("Gerente")
                                    if not perfis_atuais:
                                        perfis_atuais = ["Convencional"]
                                    novo_perfil_str = ",".join(perfis_atuais)
                                    cur.execute("UPDATE usuarios SET perfil = %s WHERE identidade = %s", (novo_perfil_str, row['identidade']))
                            
                            cur.execute("UPDATE solicitacoes_pessoal SET status = 'APROVADA' WHERE id = %s", (row['id'],))
                            conn.commit()
                            st.rerun()
                        except Exception as e:
                            conn.rollback()
                            st.error(f"Erro ao aprovar solicitação: {e}")
                        
                    if c_rej_p.button("❌ Rejeitar", key=f"rej_p_{row['id']}"):
                        cur = conn.cursor()
                        cur.execute("UPDATE solicitacoes_pessoal SET status = 'REJEITADA' WHERE id = %s", (row['id'],))
                        conn.commit()
                        st.rerun()
        else:
            st.info("Nenhuma solicitação de pessoal pendente.")

        st.markdown("---")
        
        st.markdown("#### 📞 Solicitações de Atualização de Contatos")
        df_req = pd.read_sql_query("SELECT id, pg, nome, celular, whatsapp, telefone, email, endereco FROM solicitacoes_dados WHERE status = 'PENDENTE'", conn)
        
        if not df_req.empty:
            for idx, row in df_req.iterrows():
                with st.expander(f"📌 Contato de: {row['pg']} {row['nome']}"):
                    st.write(f"**Celular:** {row['celular']} | **WhatsApp:** {row['whatsapp']} | **Fixo:** {row['telefone']}")
                    st.write(f"**E-mail:** {row['email']}")
                    st.write(f"**Endereço:** {row['endereco']}")
                    
                    c_acc, c_rej = st.columns(2)
                    if c_acc.button("✔️ Aprovar e Atualizar Banco", key=f"acc_{row['id']}"):
                        cur = conn.cursor()
                        try:
                            cur.execute("UPDATE militares SET celular=%s, whatsapp=%s, telefone=%s, email=%s, endereco=%s WHERE pg=%s AND nome=%s",
                                        (row['celular'], row['whatsapp'], row['telefone'], row['email'], row['endereco'], row['pg'], row['nome']))
                            cur.execute("UPDATE solicitacoes_dados SET status = 'APROVADA' WHERE id = %s", (row['id'],))
                            conn.commit()
                            st.rerun()
                        except Exception as e:
                            conn.rollback()
                            st.error(f"Erro ao atualizar contato: {e}")
                        
                    if c_rej.button("❌ Rejeitar", key=f"rej_req_{row['id']}"):
                        cur = conn.cursor()
                        cur.execute("UPDATE solicitacoes_dados SET status = 'REJEITADA' WHERE id = %s", (row['id'],))
                        conn.commit()
                        st.rerun()
        else:
            st.info("Nenhuma solicitação de alteração de contatos no momento.")

    with abas[4]:
        exibir_planilha_ferias(conn, filtro_pelotao=None)

    if is_super_admin:
        with abas[5]:
            st.subheader("🦸‍♂️ Lixeira do Sistema")
            df_backup = pd.read_sql_query("SELECT id, data_exclusao, identidade, pg, nome FROM backup_deletados ORDER BY id DESC", conn)
            if not df_backup.empty:
                st.dataframe(df_backup, hide_index=True)
                id_resgatar = st.selectbox("Selecione o registro para resgatar", df_backup['id'].astype(str) + " - (Deletado em: " + df_backup['data_exclusao'] + ") - " + df_backup['nome'])
                if st.button("♻️ Resgatar Registro"):
                    id_bkp = id_resgatar.split(" - ")[0]
                    cur = conn.cursor()
                    try:
                        cur.execute("SELECT identidade, pg, nome, fracao, celular, whatsapp, telefone, email, endereco, usuario, senha, perfil, pelotao, nome_completo FROM backup_deletados WHERE id = %s", (id_bkp,))
                        bkp = cur.fetchone()
                        if bkp:
                            cur.execute("SELECT COUNT(*) FROM militares WHERE identidade = %s", (bkp[0],))
                            if cur.fetchone()[0] == 0:
                                cur.execute("""INSERT INTO militares (identidade, pg, nome, fracao, celular, whatsapp, telefone, email, endereco, pelotao, nome_completo)
                                               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                                            (bkp[0], bkp[1], bkp[2], bkp[3], bkp[4], bkp[5], bkp[6], bkp[7], bkp[8], bkp[12], bkp[13]))
                            
                            if bkp[9]:
                                cur.execute("SELECT COUNT(*) FROM usuarios WHERE identidade = %s", (bkp[0],))
                                if cur.fetchone()[0] == 0:
                                    cur.execute("""INSERT INTO usuarios (usuario, identidade, senha, pg, nome, fracao, perfil, pelotao, nome_completo)
                                                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                                                (bkp[9], bkp[0], bkp[10], bkp[1], bkp[2], bkp[3], bkp[11], bkp[12], bkp[13]))
                                    
                            cur.execute("DELETE FROM backup_deletados WHERE id = %s", (id_bkp,))
                            conn.commit()
                            st.success("✅ Registro resgatado!")
                            st.rerun()
                    except Exception as e:
                        conn.rollback()
                        st.error(f"Erro ao resgatar: {e}")

    conn.close()

# --- PERFIL: COMANDANTES ---
def tela_comandante_generica(titulo_painel, is_cmt_om=False):
    st.title(titulo_painel)
    painel_convencional_comum()
    
    conn = get_connection()
    ferias_ativas = get_ferias_ativas(conn)
    
    filtro_pelotao = None if is_cmt_om else st.session_state.pelotao
    
    # ATENÇÃO: Adicionado WHERE identidade != '000000' para ocultar o Admin Geral do efetivo real
    if filtro_pelotao:
        df_militares = pd.read_sql_query("SELECT identidade, pg, nome as nome_guerra, nome_completo, fracao, pelotao, presenca, falta, justificativa, ultimo_gerente, ultima_atualizacao FROM militares WHERE pelotao = %s AND identidade != '000000'", conn, params=(filtro_pelotao,))
    else:
        df_militares = pd.read_sql_query("SELECT identidade, pg, nome as nome_guerra, nome_completo, fracao, pelotao, presenca, falta, justificativa, ultimo_gerente, ultima_atualizacao FROM militares WHERE identidade != '000000'", conn)
    
    agora_exibicao = datetime.now().strftime("%d/%m/%Y")
    for index, row in df_militares.iterrows():
        if row['identidade'] in ferias_ativas:
            df_militares.at[index, 'falta'] = 1
            df_militares.at[index, 'presenca'] = 0
            df_militares.at[index, 'justificativa'] = f"Férias ({ferias_ativas[row['identidade']]})"
            df_militares.at[index, 'ultimo_gerente'] = "Sistema Automático"
            df_militares.at[index, 'ultima_atualizacao'] = agora_exibicao
            
    abas_nomes = ["🗺️ MAPA", "✈️ Livro de Viagens", "📋 Plano de Chamada", "🏖️ Planilha de Férias"]
    if is_cmt_om: 
        abas_nomes.extend(["📚 Histórico de Faltas", "🛡️ Estrutura de Segurança (Cargos)"])
    else: 
        abas_nomes.extend(["🏢 Gestão do Pelotão", "👥 Gestão de Efetivo"])
        
    abas = st.tabs(abas_nomes)
    
    with abas[0]: # MAPA
        st.subheader(f"Mapa Geral - {filtro_pelotao if filtro_pelotao else 'OM'}")
        df_mapa = df_militares.copy()
        
        df_mapa['pg_norm'] = df_mapa['pg'].str.upper().map(PG_UPPER_MAP).fillna(df_mapa['pg'])
        df_mapa['pg_cat'] = pd.Categorical(df_mapa['pg_norm'], categories=ORDEM_HIERARQUICA, ordered=True)
        df_mapa = df_mapa.sort_values(['pg_cat', 'nome_guerra']).drop(columns=['pg_cat', 'pg_norm'])
        
        def determinar_status(row):
            if row['presenca'] == 1: return 'PRESENTE'
            if row['falta'] == 1:
                if row['justificativa'] and 'Férias' in str(row['justificativa']):
                    return 'FÉRIAS'
                return 'FALTA'
            return 'PENDENTE'
            
        df_mapa['STATUS'] = df_mapa.apply(determinar_status, axis=1)
        
        if not is_cmt_om:
            colunas_exibicao_mapa = ['pg', 'nome_guerra', 'STATUS', 'justificativa', 'ultima_atualizacao', 'ultimo_gerente', 'fracao', 'pelotao']
        else:
            colunas_exibicao_mapa = ['pg', 'nome_guerra', 'nome_completo', 'STATUS', 'justificativa', 'ultima_atualizacao', 'ultimo_gerente', 'fracao', 'pelotao']
        
        st.dataframe(df_mapa[colunas_exibicao_mapa], hide_index=True, use_container_width=True)
        
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Efetivo Total", len(df_mapa))
        c2.metric("Presentes", len(df_mapa[df_mapa['STATUS'] == 'PRESENTE']))
        c3.metric("Faltas", len(df_mapa[df_mapa['STATUS'] == 'FALTA']))
        c4.metric("Férias", len(df_mapa[df_mapa['STATUS'] == 'FÉRIAS']))
        c5.metric("Pendentes", len(df_mapa[df_mapa['STATUS'] == 'PENDENTE']))
        
        st.markdown("---")
        col_resumo, col_avisos = st.columns([2, 1])
        
        with col_resumo:
            st.write("📋 **Relação de Faltosos**")
            df_faltosos = df_mapa[df_mapa['STATUS'] == 'FALTA'][['pg', 'nome_guerra', 'justificativa']]
            if not df_faltosos.empty:
                st.dataframe(df_faltosos, hide_index=True, use_container_width=True)
            else:
                st.success("Nenhum militar faltoso no momento.")
                
            st.write("⏳ **Militares Pendentes (Aguardando Chamada)**")
            df_pendentes_militares = df_mapa[df_mapa['STATUS'] == 'PENDENTE'][['pg', 'nome_guerra', 'fracao']]
            if not df_pendentes_militares.empty:
                st.dataframe(df_pendentes_militares, hide_index=True, use_container_width=True)
            else:
                st.success("Nenhum militar pendente. Chamada completa!")
                
        with col_avisos:
            st.write("⚠️ **Frações Pendentes (Não tiraram a falta)**")
            fracoes_pendentes = df_mapa[df_mapa['STATUS'] == 'PENDENTE']['fracao'].unique()
            if len(fracoes_pendentes) > 0:
                for frac in sorted(fracoes_pendentes):
                    st.warning(f"• {frac}")
            else:
                st.success("Todas as seções lançaram a chamada!")
        
        if not is_cmt_om:
            st.markdown("---")
            if st.button("✔️ Finalizar e Consolidar Chamada do Pelotão", type="primary"):
                agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                cmt_nome = f"Cmt Pel - {st.session_state.pg} {st.session_state.nome_guerra}"
                cur = conn.cursor()
                try:
                    for idx, row in df_mapa.iterrows():
                        cur.execute("INSERT INTO historico (data_hora, pg, nome, fracao, pelotao, status, justificativa, gerente_responsavel) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                                    (agora, row['pg'], row['nome_guerra'], row['fracao'], row['pelotao'], row['STATUS'], row['justificativa'], cmt_nome))
                    
                    ids_ferias = list(ferias_ativas.keys())
                    if ids_ferias:
                        format_strings = ','.join(['%s'] * len(ids_ferias))
                        cur.execute(f"UPDATE militares SET presenca = 0, falta = 0, justificativa = '', ultimo_gerente = '-', ultima_atualizacao = '-' WHERE pelotao = %s AND identidade != '000000' AND identidade NOT IN ({format_strings})", tuple([filtro_pelotao] + ids_ferias))
                    else:
                        cur.execute("UPDATE militares SET presenca = 0, falta = 0, justificativa = '', ultimo_gerente = '-', ultima_atualizacao = '-' WHERE pelotao = %s AND identidade != '000000'", (filtro_pelotao,))
                    
                    conn.commit()
                    st.success("✅ Chamada do pelotão consolidada com sucesso, enviada para o Histórico da OM e os campos manuais foram limpos!")
                    st.rerun()
                except Exception as e:
                    conn.rollback()
                    st.error(f"Erro ao consolidar chamada: {e}")

    with abas[1]: # VIAGENS
        st.subheader("Registros do Livro de Viagens")
        if filtro_pelotao:
            df_viagens = pd.read_sql_query("""
                SELECT m.pg, m.nome as nome_guerra, m.nome_completo, v.fracao, v.pelotao, v.data_ida, v.data_volta, v.cidade, v.pais 
                FROM viagens v 
                INNER JOIN militares m ON v.identidade = m.identidade
                WHERE v.pelotao = %s AND m.identidade != '000000' ORDER BY v.data_ida DESC
            """, conn, params=(filtro_pelotao,))
        else:
            df_viagens = pd.read_sql_query("""
                SELECT m.pg, m.nome as nome_guerra, m.nome_completo, v.fracao, v.pelotao, v.data_ida, v.data_volta, v.cidade, v.pais 
                FROM viagens v 
                INNER JOIN militares m ON v.identidade = m.identidade
                WHERE m.identidade != '000000' ORDER BY v.data_ida DESC
            """, conn)
        
        if not df_viagens.empty: st.dataframe(df_viagens, hide_index=True, use_container_width=True)
        else: st.info("Nenhuma viagem registrada.")

    with abas[2]: # PLANO DE CHAMADA
        st.subheader("Plano de Chamada")
        if filtro_pelotao:
            df_plano = pd.read_sql_query("SELECT pg, nome as nome_guerra, nome_completo, fracao, celular, whatsapp, telefone as residencial, email, endereco FROM militares WHERE pelotao = %s AND identidade != '000000'", conn, params=(filtro_pelotao,))
        else:
            df_plano = pd.read_sql_query("SELECT pg, nome as nome_guerra, nome_completo, fracao, pelotao, celular, whatsapp, telefone as residencial, email, endereco FROM militares WHERE identidade != '000000'", conn)
            
        df_plano['pg_norm'] = df_plano['pg'].str.upper().map(PG_UPPER_MAP).fillna(df_plano['pg'])
        df_plano['pg_cat'] = pd.Categorical(df_plano['pg_norm'], categories=ORDEM_HIERARQUICA, ordered=True)
        df_plano = df_plano.sort_values(['pg_cat', 'nome_guerra']).drop(columns=['pg_cat', 'pg_norm'])
        
        st.dataframe(df_plano, hide_index=True, use_container_width=True)

    with abas[3]: # PLANILHA DE FÉRIAS
        exibir_planilha_ferias(conn, filtro_pelotao)
        
    if is_cmt_om:
        with abas[4]: # HISTÓRICO OM
            st.subheader("Histórico de Faltas Consolidado")
            st.write("Filtre o histórico por data para visualização e impressão.")
            data_filtro = st.date_input("Selecione a Data")
            data_str = data_filtro.strftime("%d/%m/%Y")
            
            df_hist = pd.read_sql_query(f"SELECT data_hora as Data_Hora, pg as PG, nome as Nome_de_Guerra, fracao as Fracao, pelotao as Pelotao, status as Status, justificativa as Justificativa, gerente_responsavel as Responsavel FROM historico WHERE data_hora LIKE '{data_str}%%' ORDER BY data_hora DESC", conn)
            
            if not df_hist.empty:
                st.dataframe(df_hist, hide_index=True, use_container_width=True)
                
                html_tabela = df_hist.to_html(index=False)
                html_completo = f"""
                <html><head>
                    <title>Relatório - {data_str}</title>
                    <style>
                        body {{ background-color: #ffffff; color: #000000; font-family: sans-serif; }}
                        table {{ border-collapse: collapse; width: 100%; font-size: 12px; }}
                        th, td {{ border: 1px solid #333333; padding: 6px; text-align: left; color: #000000; }}
                        th {{ background-color: #e0e0e0; color: #000000; }}
                        .btn-print {{ padding: 10px 15px; font-size: 14px; background-color: #4CAF50; color: white; border: none; border-radius: 4px; cursor: pointer; margin-bottom: 15px; }}
                        @media print {{ .btn-print {{ display: none; }} }}
                    </style>
                </head><body>
                    <button class="btn-print" onclick="window.print()">🖨️ Imprimir / Salvar PDF</button>
                    <h3>Relatório Consolidado de Faltas - OM ({data_str})</h3>
                    {html_tabela}
                </body></html>
                """
                components.html(html_completo, height=500, scrolling=True)
            else:
                st.info(f"Nenhuma chamada foi consolidada no banco de dados no dia {data_str}.")

        with abas[5]: # ESTRUTURA DE SEGURANÇA
            st.subheader("🛡️ Estrutura de Segurança e Gestão (Cargos Chave da OM)")
            st.write("Lista oficial de todos os militares que possuem funções e perfis administrativos ou gerenciais no sistema.")
            
            df_seguranca = pd.read_sql_query("""
                SELECT pg, nome as nome_guerra, nome_completo, pelotao, fracao, perfil, usuario 
                FROM usuarios 
                WHERE perfil IS NOT NULL AND perfil != '' AND perfil != 'Convencional' AND identidade != '000000'
                ORDER BY pelotao, nome
            """, conn)
            
            if not df_seguranca.empty:
                st.dataframe(df_seguranca, hide_index=True, use_container_width=True)
            else:
                st.info("Nenhum perfil especial atribuído além do padrão convencional no momento.")
    else:
        with abas[4]: # GESTÃO FRAÇÃO E GERENTES
            st.subheader(f"Gestão de Frações - {filtro_pelotao}")
            with st.form("solicitar_fracao"):
                nova_f = st.text_input("Solicitar Criação de Nova Fração para o seu Pelotão")
                if st.form_submit_button("Enviar Solicitação ao Administrador"):
                    try:
                        cur = conn.cursor()
                        cur.execute("INSERT INTO fracoes (nome_fracao, pelotao, status) VALUES (%s, %s, 'PENDENTE')", (nova_f.strip(), filtro_pelotao))
                        conn.commit()
                        st.success("✅ Solicitação enviada! O Administrador precisa autorizar.")
                    except Exception as e:
                        conn.rollback()
                        st.error(f"Erro ao solicitar fração: {e}")
            
            st.markdown("---")
            
            st.subheader("👨‍💼 Gerentes Atuais do Pelotão")
            df_gerentes_atuais = pd.read_sql_query(
                "SELECT identidade, pg, nome as nome_guerra, fracao FROM usuarios WHERE pelotao = %s AND perfil LIKE '%%Gerente%%' AND identidade != '000000'", 
                conn, params=(filtro_pelotao,)
            )
            
            if not df_gerentes_atuais.empty:
                df_exib_gerentes = df_gerentes_atuais[['pg', 'nome_guerra', 'fracao']].rename(columns={'pg': 'P/G', 'nome_guerra': 'Nome de Guerra', 'fracao': 'Fração Base'})
                st.dataframe(df_exib_gerentes, hide_index=True, use_container_width=True)
                
                with st.expander("❌ Deseja Destituir algum Gerente Atual?"):
                    with st.form("form_remover_gerente"):
                        st.write("A solicitação será enviada ao Administrador para aprovação.")
                        opcoes_remover = df_gerentes_atuais['identidade'] + " - " + df_gerentes_atuais['pg'] + " " + df_gerentes_atuais['nome_guerra'] + " (" + df_gerentes_atuais['fracao'] + ")"
                        sel_remover = st.selectbox("Selecione o Gerente para Remoção", opcoes_remover)
                        
                        if st.form_submit_button("Solicitar Destituição ao Administrador"):
                            idt_rem = sel_remover.split(" - ")[0]
                            cur = conn.cursor()
                            cur.execute("SELECT pg, nome, nome_completo FROM militares WHERE identidade = %s", (idt_rem,))
                            m_data = cur.fetchone()
                            try:
                                cur.execute("""INSERT INTO solicitacoes_pessoal (tipo, identidade, pg, nome, nome_completo, pelotao_destino, fracao_destino, status)
                                               VALUES ('REMOVER_GERENTE', %s, %s, %s, %s, %s, %s, 'PENDENTE')""",
                                            (idt_rem, m_data[0], m_data[1], m_data[2], filtro_pelotao, 'N/A'))
                                conn.commit()
                                st.success("✅ Solicitação de remoção de gerente enviada ao Administrador!")
                            except Exception as e:
                                conn.rollback()
                                st.error(f"Erro ao enviar solicitação: {e}")
            else:
                st.info("Não há nenhum gerente cadastrado ou em atividade no seu pelotão.")
                
            st.markdown("---")

            st.subheader("👔 Indicar Novo Gerente para Fração")
            fracoes_pelotao_ativo = pd.read_sql_query("SELECT nome_fracao FROM fracoes WHERE pelotao = %s AND status = 'APROVADA'", conn, params=(filtro_pelotao,))['nome_fracao'].tolist()
            militares_pelotao_ativo = pd.read_sql_query("SELECT identidade, pg, nome FROM militares WHERE pelotao = %s AND identidade != '000000'", conn, params=(filtro_pelotao,))
            
            if fracoes_pelotao_ativo and not militares_pelotao_ativo.empty:
                with st.form("form_indicar_gerente"):
                    sel_frac_gerente = st.selectbox("Selecione a Fração", fracoes_pelotao_ativo)
                    mil_opcoes = militares_pelotao_ativo['identidade'] + " - " + militares_pelotao_ativo['pg'] + " " + militares_pelotao_ativo['nome']
                    sel_mil_gerente = st.selectbox("Selecione o Militar para ser Gerente", mil_opcoes)
                    
                    if st.form_submit_button("Solicitar Atribuição de Gerente ao Administrador"):
                        idt_g = sel_mil_gerente.split(" - ")[0]
                        m_row = militares_pelotao_ativo[militares_pelotao_ativo['identidade'] == idt_g].iloc[0]
                        cur = conn.cursor()
                        try:
                            cur.execute("""INSERT INTO solicitacoes_pessoal (tipo, identidade, pg, nome, nome_completo, pelotao_destino, fracao_destino, status)
                                           VALUES ('GERENTE', %s, %s, %s, %s, %s, %s, 'PENDENTE')""",
                                        (m_row['identidade'], m_row['pg'], m_row['nome'], m_row['nome'], filtro_pelotao, sel_frac_gerente))
                            conn.commit()
                            st.success("✅ Solicitação de indicação de gerente enviada ao Administrador!")
                        except Exception as e:
                            conn.rollback()
                            st.error(f"Erro ao solicitar gerente: {e}")
            else:
                st.info("Cadastre frações e militares no seu pelotão para indicar gerentes.")
                        
        with abas[5]: # GESTÃO DE EFETIVO
            st.subheader("👥 Gestão e Movimentação de Efetivo")
            
            pelotoes_cadastrados = pd.read_sql_query("SELECT nome_pelotao FROM pelotoes", conn)['nome_pelotao'].tolist()
            fracoes_pelotao_destino = pd.read_sql_query("SELECT nome_fracao FROM fracoes WHERE pelotao = %s AND status = 'APROVADA'", conn, params=(filtro_pelotao,))['nome_fracao'].tolist()
            
            st.markdown("#### 🔄 Solicitar Transferência de Militar para o seu Pelotão")
            
            if 'pel_origem_selecionado' not in st.session_state:
                st.session_state.pel_origem_selecionado = pelotoes_cadastrados[0] if pelotoes_cadastrados else "Geral"

            def atualizar_pel_origem():
                st.session_state.pel_origem_selecionado = st.session_state.sb_pel_origem

            filtro_pel_origem = st.selectbox("Filtrar por Pelotão de Origem", pelotoes_cadastrados, key="sb_pel_origem", on_change=atualizar_pel_origem)
            
            fracoes_origem_lista = pd.read_sql_query("SELECT nome_fracao FROM fracoes WHERE pelotao = %s AND status = 'APROVADA'", conn, params=(st.session_state.pel_origem_selecionado,))['nome_fracao'].tolist()
            filtro_frac_origem = st.selectbox("Filtrar por Fração de Origem", fracoes_origem_lista if fracoes_origem_lista else ["Geral"])
            
            df_mil_origem = pd.read_sql_query("SELECT identidade, pg, nome, nome_completo, pelotao FROM militares WHERE pelotao = %s AND fracao = %s AND identidade != '000000'", conn, params=(st.session_state.pel_origem_selecionado, filtro_frac_origem))
            
            if not df_mil_origem.empty:
                militar_escolhido = st.selectbox("Selecione o Militar", df_mil_origem['identidade'] + " - " + df_mil_origem['pg'] + " " + df_mil_origem['nome'])
                fracao_destino_transf = st.selectbox("Selecione a Fração de Destino no seu Pelotão", fracoes_pelotao_destino if fracoes_pelotao_destino else ["Geral"])
                
                if st.button("Enviar Solicitação de Transferência"):
                    idt_t = militar_escolhido.split(" - ")[0]
                    mil_row = df_mil_origem[df_mil_origem['identidade'] == idt_t].iloc[0]
                    cur = conn.cursor()
                    try:
                        cur.execute("""INSERT INTO solicitacoes_pessoal (tipo, identidade, pg, nome, nome_completo, pelotao_destino, fracao_destino, status)
                                       VALUES ('TRANSFERENCIA', %s, %s, %s, %s, %s, %s, 'PENDENTE')""",
                                    (mil_row['identidade'], mil_row['pg'], mil_row['nome'], mil_row['nome_completo'], filtro_pelotao, fracao_destino_transf))
                        conn.commit()
                        st.success("✅ Solicitação de transferência enviada ao Administrador!")
                    except Exception as e:
                        conn.rollback()
                        st.error(f"Erro ao solicitar transferência: {e}")
            else:
                st.info("Nenhum militar encontrado nesta fração.")
                
            st.markdown("---")
            
            st.markdown("#### ➕ Solicitar Inclusão de Novo Militar")
            with st.form("form_incluir_militar_pel"):
                i_idt = st.text_input("Nº de Identidade")
                i_pg = st.text_input("Posto / Graduação")
                i_guerra = st.text_input("Nome de Guerra (Maiúsculo)").upper()
                i_completo = st.text_input("Nome Completo")
                i_fracao = st.selectbox("Fração de Destino no seu Pelotão", fracoes_pelotao_destino if fracoes_pelotao_destino else ["Geral"])
                
                if st.form_submit_button("Solicitar Inclusão ao Administrador"):
                    if i_idt and i_pg and i_guerra:
                        cur = conn.cursor()
                        try:
                            i_completo_fmt = formatar_nome_completo(i_completo)
                            
                            cur.execute("""INSERT INTO solicitacoes_pessoal (tipo, identidade, pg, nome, nome_completo, pelotao_destino, fracao_destino, status)
                                           VALUES ('INCLUSAO', %s, %s, %s, %s, %s, %s, 'PENDENTE')""",
                                        (i_idt, i_pg, i_guerra, i_completo_fmt, filtro_pelotao, i_fracao))
                            conn.commit()
                            st.success("✅ Solicitação de inclusão enviada ao Administrador!")
                        except Exception as e:
                            conn.rollback()
                            st.error(f"Erro ao solicitar inclusão: {e}")
                    else:
                        st.error("Preencha todos os campos obrigatórios.")
            
    conn.close()

def tela_comandante_pelotao():
    tela_comandante_generica(f"Painel do Cmt - {st.session_state.pelotao}", is_cmt_om=False)

def tela_comandante_om():
    tela_comandante_generica("🛡️ Painel do Comandante de OM", is_cmt_om=True)

# --- FLUXO PRINCIPAL DE EXIBIÇÃO ---
if not st.session_state.logado:
    login()
else:
    with st.sidebar:
        if os.path.exists("brasao.png"): st.image("brasao.png", width=80)
        st.markdown(f"👤 **{st.session_state.pg} {st.session_state.nome_guerra}**")
        st.markdown(f"🏢 **{st.session_state.pelotao}**")
        
        if len(st.session_state.perfis_usuario) > 1:
            st.markdown("---")
            novo_perfil = st.selectbox("🛡️ Alternar Perfil:", st.session_state.perfis_usuario, index=st.session_state.perfis_usuario.index(st.session_state.perfil_ativo))
            if novo_perfil != st.session_state.perfil_ativo:
                st.session_state.perfil_ativo = novo_perfil
                st.rerun()
        else:
            st.markdown(f"🛡️ Perfil: **{st.session_state.perfil_ativo}**")
            
        st.markdown("---")
        if st.button("🚪 Sair do Sistema"):
            st.session_state.logado = False
            st.rerun()
            
    perfil = st.session_state.perfil_ativo
    if perfil == "Administrador": tela_administrador()
    elif perfil == "Comandante de Pelotão": tela_comandante_pelotao()
    elif perfil == "Comandante de OM": tela_comandante_om()
    elif perfil == "Gerente": tela_gerente()
    else: tela_convencional()