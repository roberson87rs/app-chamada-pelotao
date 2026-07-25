import streamlit as st
import pandas as pd
from datetime import datetime, date
import psycopg2
import hashlib
import os
import streamlit.components.v1 as components

# Configuração da página
st.set_page_config(page_title="Sistema de Controle de Efetivo e Faltas", layout="wide", initial_sidebar_state="expanded")

# --- CONEXÃO COM O SUPABASE (POOLER) ---
SUPABASE_URL = "postgresql://postgres.jgzhlalaczpmecwqpofg:1723Rsh32335770@aws-0-sa-east-1.pooler.supabase.com:6543/postgres?sslmode=require"

def get_connection():
    return psycopg2.connect(SUPABASE_URL)

def hash_senha(senha):
    return hashlib.sha256(senha.encode()).hexdigest()

# --- CONFIGURAÇÃO INICIAL E ATUALIZAÇÃO DO SUPABASE ---
def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS pelotoes (id SERIAL PRIMARY KEY, nome_pelotao TEXT UNIQUE)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS fracoes (id SERIAL PRIMARY KEY, nome_fracao TEXT UNIQUE)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS usuarios (id SERIAL PRIMARY KEY, usuario TEXT UNIQUE, identidade TEXT UNIQUE, senha TEXT, pg TEXT, nome TEXT, fracao TEXT, perfil TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS militares (id SERIAL PRIMARY KEY, identidade TEXT UNIQUE, pg TEXT, nome TEXT, fracao TEXT, celular TEXT DEFAULT '', whatsapp TEXT DEFAULT '', telefone TEXT DEFAULT '', email TEXT DEFAULT '', endereco TEXT DEFAULT '', presenca INTEGER DEFAULT 0, falta INTEGER DEFAULT 0, justificativa TEXT DEFAULT '')''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS ausencias_futuras (id SERIAL PRIMARY KEY, nome_militar TEXT, fracao TEXT, data_prevista TEXT, motivo TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS historico (id SERIAL PRIMARY KEY, data_hora TEXT, pg TEXT, nome TEXT, fracao TEXT, status TEXT, justificativa TEXT, gerente_responsavel TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS ferias (id SERIAL PRIMARY KEY, identidade TEXT, data_inicio DATE, data_fim DATE, bi TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS viagens (id SERIAL PRIMARY KEY, identidade TEXT, nome TEXT, fracao TEXT, data_ida DATE, data_volta DATE, cidade TEXT, pais TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS backup_deletados (id SERIAL PRIMARY KEY, identidade TEXT, pg TEXT, nome TEXT, fracao TEXT, celular TEXT, whatsapp TEXT, telefone TEXT, email TEXT, endereco TEXT, usuario TEXT, senha TEXT, perfil TEXT, data_exclusao TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS solicitacoes_dados (id SERIAL PRIMARY KEY, identidade TEXT, pg TEXT, nome TEXT, celular TEXT, whatsapp TEXT, telefone TEXT, email TEXT, endereco TEXT, status TEXT DEFAULT 'PENDENTE')''')
    
    cursor.execute('''ALTER TABLE militares ADD COLUMN IF NOT EXISTS pelotao TEXT DEFAULT 'Geral' ''')
    cursor.execute('''ALTER TABLE militares ADD COLUMN IF NOT EXISTS nome_completo TEXT DEFAULT '' ''')
    cursor.execute('''ALTER TABLE militares ADD COLUMN IF NOT EXISTS ultimo_gerente TEXT DEFAULT '-' ''')
    cursor.execute('''ALTER TABLE militares ADD COLUMN IF NOT EXISTS ultima_atualizacao TEXT DEFAULT '-' ''')
    
    cursor.execute('''ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS pelotao TEXT DEFAULT 'Geral' ''')
    cursor.execute('''ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS nome_completo TEXT DEFAULT '' ''')
    cursor.execute('''ALTER TABLE fracoes ADD COLUMN IF NOT EXISTS pelotao TEXT DEFAULT 'Geral' ''')
    cursor.execute('''ALTER TABLE fracoes ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'APROVADA' ''')
    cursor.execute('''ALTER TABLE backup_deletados ADD COLUMN IF NOT EXISTS pelotao TEXT DEFAULT 'Geral' ''')
    cursor.execute('''ALTER TABLE backup_deletados ADD COLUMN IF NOT EXISTS nome_completo TEXT DEFAULT '' ''')
    cursor.execute('''ALTER TABLE viagens ADD COLUMN IF NOT EXISTS pelotao TEXT DEFAULT 'Geral' ''')
    cursor.execute('''ALTER TABLE historico ADD COLUMN IF NOT EXISTS pelotao TEXT DEFAULT 'Geral' ''')
    
    conn.commit()

    cursor.execute('''
        INSERT INTO militares (identidade, pg, nome, nome_completo, fracao, pelotao)
        SELECT identidade, pg, nome, nome_completo, fracao, pelotao FROM usuarios
        ON CONFLICT (identidade) DO NOTHING
    ''')
    conn.commit()
    
    cursor.execute("SELECT COUNT(*) FROM usuarios WHERE identidade = '000000'")
    if cursor.fetchone()[0] == 0:
        senha_padrao = hash_senha("1234")
        cursor.execute("INSERT INTO usuarios (usuario, identidade, senha, pg, nome, nome_completo, fracao, pelotao, perfil) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING", 
                       ("admin", "000000", senha_padrao, "Cel", "ADMIN", "Administrador Geral do Sistema", "S1", "Geral", "Administrador"))
        conn.commit()
        
    cursor.close()
    conn.close()

try:
    init_db()
except Exception as e:
    st.error(f"Erro ao conectar ou atualizar o Supabase: {e}")
    st.stop()

# --- FUNÇÃO DE LOGIN ---
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
                st.success("✅ Aviso enviado ao Chefe da Seção!")
                
    with t_ferias:
        st.info("💡 As férias registradas aqui preencherão a chamada da sua seção automaticamente.")
        with st.form("form_ferias"):
            c_f1, c_f2 = st.columns(2)
            with c_f1: dt_inicio = st.date_input("Data Início das Férias")
            with c_f2: dt_fim = st.date_input("Data Fim das Férias")
            bi_pub = st.text_input("BI de Publicação (Ex: BI Nr 123, de 10 Ago)")
            if st.form_submit_button("Gravar Férias"):
                conn = get_connection()
                cur = conn.cursor()
                cur.execute("INSERT INTO ferias (identidade, data_inicio, data_fim, bi) VALUES (%s, %s, %s, %s)",
                            (st.session_state.identidade_atual, dt_inicio, dt_fim, bi_pub))
                conn.commit()
                conn.close()
                st.success("✅ Férias registradas no sistema!")

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
        df_militares = pd.read_sql_query("SELECT id, identidade, pg, nome, fracao, presenca, falta, justificativa FROM militares WHERE fracao = %s", conn, params=(st.session_state.fracao,))
        
        df_militares['presenca'] = df_militares['presenca'].astype(bool)
        df_militares['falta'] = df_militares['falta'].astype(bool)
        
        for index, row in df_militares.iterrows():
            if row['identidade'] in ferias_ativas:
                df_militares.at[index, 'falta'] = True
                df_militares.at[index, 'presenca'] = False
                df_militares.at[index, 'justificativa'] = f"Férias ({ferias_ativas[row['identidade']]})"
                
        ordem_hierarquica = ["Gen Ex", "Gen Div", "Gen Bda", "Cel", "Ten Cel", "Maj", "Cap", "1º Ten", "2º Ten", "Asp Of", "S Ten", "1º Sgt", "2º Sgt", "3º Sgt", "Cb", "Sd EP", "Sd EV"]
        pg_upper_map = {rank.upper(): rank for rank in ordem_hierarquica}
        df_militares['pg_norm'] = df_militares['pg'].str.upper().map(pg_upper_map).fillna(df_militares['pg'])
        df_militares['pg_cat'] = pd.Categorical(df_militares['pg_norm'], categories=ordem_hierarquica, ordered=True)
        df_militares = df_militares.sort_values(['pg_cat', 'nome']).drop(columns=['pg_cat', 'pg_norm'])
        
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
        
        if st.button("💾 Salvar Chamada da Seção", type="primary"):
            agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            gerente_nome = f"{st.session_state.pg} {st.session_state.nome_guerra}"
            cursor = conn.cursor()
            for index, row in editado.iterrows():
                cursor.execute("UPDATE militares SET presenca = %s, falta = %s, justificativa = %s, ultimo_gerente = %s, ultima_atualizacao = %s WHERE id = %s",
                               (int(row['presenca']), int(row['falta']), row['justificativa'], gerente_nome, agora, row['id']))
            conn.commit()
            st.success("✅ Chamada registrada com sucesso! (Visível em tempo real para os Comandantes)")
            
    with tab_plano:
        st.info("Abaixo constam os dados de contato atuais da sua fração (Apenas visualização).")
        df_contatos = pd.read_sql_query("SELECT pg, nome as nome_guerra, celular, whatsapp, telefone as residencial, email, endereco FROM militares WHERE fracao = %s", conn, params=(st.session_state.fracao,))
        
        df_contatos['pg_norm'] = df_contatos['pg'].str.upper().map(pg_upper_map).fillna(df_contatos['pg'])
        df_contatos['pg_cat'] = pd.Categorical(df_contatos['pg_norm'], categories=ordem_hierarquica, ordered=True)
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
    
    abas_nomes = ["🏢 Estrutura (Pel/Fração)", "👥 Gestão de Efetivo", "🔑 Acessos", "📨 Solicitações (Contatos)"]
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
                except: st.error("Pelotão já existe.")
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
                except: st.error("Fração já existe.")
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
        
    with abas[1]:
        st.subheader("Adicionar Novo Militar")
        with st.form("novo_militar"):
            c1, c2, c3 = st.columns([1,1,2])
            with c1: nova_identidade = st.text_input("Identidade")
            with c2: novo_pg = st.text_input("Posto/Graduação")
            with c3: novo_nome_guerra = st.text_input("Nome de Guerra (Ficará em Maiúsculo)").upper()
            
            c4, c5, c6 = st.columns([2,1,1])
            with c4: novo_nome_completo = st.text_input("Nome Completo")
            with c5: novo_pel = st.selectbox("Pelotão", pelotoes_bd)
            with c6: nova_fracao = st.selectbox("Fração", fracoes_bd) if fracoes_bd else st.text_input("Fração")
            
            if st.form_submit_button("Cadastrar Novo Militar"):
                cur = conn.cursor()
                try:
                    cur.execute("""INSERT INTO militares (identidade, pg, nome, nome_completo, fracao, pelotao) VALUES (%s, %s, %s, %s, %s, %s) 
                                   ON CONFLICT (identidade) DO UPDATE SET pg=EXCLUDED.pg, nome=EXCLUDED.nome, nome_completo=EXCLUDED.nome_completo, fracao=EXCLUDED.fracao, pelotao=EXCLUDED.pelotao""", 
                                (nova_identidade, novo_pg, novo_nome_guerra, novo_nome_completo, nova_fracao, novo_pel))
                    cur.execute("""INSERT INTO usuarios (usuario, identidade, senha, pg, nome, nome_completo, fracao, pelotao, perfil) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) 
                                   ON CONFLICT (identidade) DO NOTHING""",
                                   (novo_nome_guerra.lower(), nova_identidade, hash_senha("1234"), novo_pg, novo_nome_guerra, novo_nome_completo, nova_fracao, novo_pel, "Convencional"))
                    conn.commit()
                    st.success("Militar cadastrado (Senha padrão: 1234)!")
                except Exception as e: st.error(f"Erro ao cadastrar: {e}")
                
        st.markdown("---")
        st.subheader("⚠️ Gerenciar Efetivo Existente")
        
        query_uniao = """
            SELECT identidade, pg, nome, nome_completo, fracao, pelotao FROM militares
            UNION
            SELECT identidade, pg, nome, nome_completo, fracao, pelotao FROM usuarios
        """
        df_all = pd.read_sql_query(query_uniao, conn)
        df_all = df_all[df_all['identidade'] != '000000'].drop_duplicates(subset=['identidade'])
        
        ordem_hierarquica = ["Gen Ex", "Gen Div", "Gen Bda", "Cel", "Ten Cel", "Maj", "Cap", "1º Ten", "2º Ten", "Asp Of", "S Ten", "1º Sgt", "2º Sgt", "3º Sgt", "Cb", "Sd EP", "Sd EV"]
        
        if not df_all.empty:
            pg_upper_map = {rank.upper(): rank for rank in ordem_hierarquica}
            df_all['pg_norm'] = df_all['pg'].str.upper().map(pg_upper_map).fillna(df_all['pg'])
            df_all['pg_cat'] = pd.Categorical(df_all['pg_norm'], categories=ordem_hierarquica, ordered=True)
            df_all = df_all.sort_values(['pg_cat', 'nome'])
            df_exibicao = df_all.drop(columns=['pg_cat', 'pg_norm'])
            
            militar_selecionado = st.selectbox("Selecione um militar", df_exibicao['identidade'] + " - " + df_exibicao['pg'] + " " + df_exibicao['nome'])
            
            col_ex, col_senha, col_edit = st.columns(3)
            
            if col_ex.button("❌ Excluir Militar"):
                if militar_selecionado:
                    idt_del = militar_selecionado.split(" - ")[0]
                    agora_del = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                    cur = conn.cursor()
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
                    
            if col_senha.button("🔑 Resetar Senha (1234)"):
                if militar_selecionado:
                    idt_res = militar_selecionado.split(" - ")[0]
                    cur = conn.cursor()
                    cur.execute("UPDATE usuarios SET senha = %s WHERE identidade = %s", (hash_senha("1234"), idt_res))
                    conn.commit()
                    st.success(f"Senha redefinida!")

            with st.expander("✏️ Editar Dados do Militar Selecionado (Corrige Nomes e Fração)"):
                if militar_selecionado:
                    idt_edit = militar_selecionado.split(" - ")[0]
                    dados_edit = df_all[df_all['identidade'] == idt_edit].iloc[0]
                    
                    with st.form("form_edicao_rapida"):
                        e_pg = st.text_input("PG", value=dados_edit['pg'])
                        e_guerra = st.text_input("Nome de Guerra", value=dados_edit['nome']).upper()
                        e_completo = st.text_input("Nome Completo", value=dados_edit['nome_completo'])
                        e_fracao = st.selectbox("Fração", fracoes_bd, index=fracoes_bd.index(dados_edit['fracao']) if dados_edit['fracao'] in fracoes_bd else 0)
                        
                        if st.form_submit_button("Salvar Edição"):
                            cur = conn.cursor()
                            cur.execute("UPDATE militares SET pg=%s, nome=%s, nome_completo=%s, fracao=%s WHERE identidade=%s", (e_pg, e_guerra, e_completo, e_fracao, idt_edit))
                            cur.execute("UPDATE usuarios SET pg=%s, nome=%s, nome_completo=%s, fracao=%s WHERE identidade=%s", (e_pg, e_guerra, e_completo, e_fracao, idt_edit))
                            conn.commit()
                            st.success("Dados alterados com sucesso!")
                            st.rerun()

            st.markdown("---")
            st.subheader("📋 Relação do Efetivo")
            st.dataframe(df_exibicao, hide_index=True, use_container_width=True)
            
    with abas[2]:
        st.subheader("Atribuir e Gerenciar Perfis de Acesso")
        if not df_all.empty:
            militar_selecionado_tab5 = st.selectbox("Selecione o Militar para Gerenciar Acessos:", df_exibicao['identidade'] + " - " + df_exibicao['pg'] + " " + df_exibicao['nome'])
            if militar_selecionado_tab5:
                idt_selecionada = militar_selecionado_tab5.split(" - ")[0]
                dados_mil = df_all[df_all['identidade'] == idt_selecionada].iloc[0]
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
                        cur.execute("INSERT INTO militares (identidade, pg, nome, nome_completo, fracao, pelotao) VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (identidade) DO UPDATE SET pg=EXCLUDED.pg, nome=EXCLUDED.nome, fracao=EXCLUDED.fracao, pelotao=EXCLUDED.pelotao", (idt_selecionada, dados_mil['pg'], dados_mil['nome'], dados_mil['nome_completo'], dados_mil['fracao'], dados_mil['pelotao']))
                        if not df_user.empty:
                            cur.execute("UPDATE usuarios SET usuario = %s, perfil = %s, pg = %s, nome = %s, nome_completo = %s, fracao = %s, pelotao = %s WHERE identidade = %s", 
                                        (u_usuario.lower(), perfis_str, dados_mil['pg'], dados_mil['nome'], dados_mil['nome_completo'], dados_mil['fracao'], dados_mil['pelotao'], idt_selecionada))
                        else:
                            cur.execute("INSERT INTO usuarios (usuario, identidade, senha, pg, nome, nome_completo, fracao, pelotao, perfil) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                                        (u_usuario.lower(), idt_selecionada, hash_senha("1234"), dados_mil['pg'], dados_mil['nome'], dados_mil['nome_completo'], dados_mil['fracao'], dados_mil['pelotao'], perfis_str))
                        conn.commit()
                        st.success("✅ Acessos atualizados!")

    with abas[3]:
        st.subheader("📨 Solicitações de Atualização (Plano de Chamada)")
        df_req = pd.read_sql_query("SELECT id, pg, nome, celular, whatsapp, telefone, email, endereco FROM solicitacoes_dados WHERE status = 'PENDENTE'", conn)
        
        if not df_req.empty:
            for idx, row in df_req.iterrows():
                with st.expander(f"📌 Solicitação de: {row['pg']} {row['nome']}"):
                    st.write(f"**Celular:** {row['celular']} | **WhatsApp:** {row['whatsapp']} | **Fixo:** {row['telefone']}")
                    st.write(f"**E-mail:** {row['email']}")
                    st.write(f"**Endereço:** {row['endereco']}")
                    
                    c_acc, c_rej = st.columns(2)
                    if c_acc.button("✔️ Aprovar e Atualizar Banco", key=f"acc_{row['id']}"):
                        cur = conn.cursor()
                        cur.execute("UPDATE militares SET celular=%s, whatsapp=%s, telefone=%s, email=%s, endereco=%s WHERE pg=%s AND nome=%s",
                                    (row['celular'], row['whatsapp'], row['telefone'], row['email'], row['endereco'], row['pg'], row['nome']))
                        cur.execute("UPDATE solicitacoes_dados SET status = 'APROVADA' WHERE id = %s", (row['id'],))
                        conn.commit()
                        st.rerun()
                        
                    if c_rej.button("❌ Rejeitar", key=f"rej_req_{row['id']}"):
                        cur = conn.cursor()
                        cur.execute("UPDATE solicitacoes_dados SET status = 'REJEITADA' WHERE id = %s", (row['id'],))
                        conn.commit()
                        st.rerun()
        else:
            st.info("Nenhuma solicitação de alteração de contatos no momento.")

    if is_super_admin:
        with abas[4]:
            st.subheader("🦸‍♂️ Lixeira do Sistema")
            df_backup = pd.read_sql_query("SELECT id, data_exclusao, identidade, pg, nome FROM backup_deletados ORDER BY id DESC", conn)
            if not df_backup.empty:
                st.dataframe(df_backup, hide_index=True)
                id_resgatar = st.selectbox("Selecione o registro para resgatar", df_backup['id'].astype(str) + " - (Deletado em: " + df_backup['data_exclusao'] + ") - " + df_backup['nome'])
                if st.button("♻️ Resgatar Registro"):
                    id_bkp = id_resgatar.split(" - ")[0]
                    cur = conn.cursor()
                    cur.execute("SELECT identidade, pg, nome, fracao, celular, whatsapp, telefone, email, endereco, usuario, senha, perfil, pelotao, nome_completo FROM backup_deletados WHERE id = %s", (id_bkp,))
                    bkp = cur.fetchone()
                    if bkp:
                        cur.execute("""INSERT INTO militares (identidade, pg, nome, fracao, celular, whatsapp, telefone, email, endereco, pelotao, nome_completo)
                                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (identidade) DO NOTHING""",
                                    (bkp[0], bkp[1], bkp[2], bkp[3], bkp[4], bkp[5], bkp[6], bkp[7], bkp[8], bkp[12], bkp[13]))
                        if bkp[9]:
                            cur.execute("""INSERT INTO usuarios (usuario, identidade, senha, pg, nome, fracao, perfil, pelotao, nome_completo)
                                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (identidade) DO NOTHING""",
                                        (bkp[9], bkp[0], bkp[10], bkp[1], bkp[2], bkp[3], bkp[11], bkp[12], bkp[13]))
                        cur.execute("DELETE FROM backup_deletados WHERE id = %s", (id_bkp,))
                        conn.commit()
                        st.success("✅ Registro resgatado!")
                        st.rerun()

    conn.close()

# --- PERFIL: COMANDANTES ---
def tela_comandante_generica(titulo_painel, is_cmt_om=False):
    st.title(titulo_painel)
    painel_convencional_comum()
    
    conn = get_connection()
    ferias_ativas = get_ferias_ativas(conn)
    
    filtro_pelotao = None if is_cmt_om else st.session_state.pelotao
    
    if filtro_pelotao:
        df_militares = pd.read_sql_query("SELECT identidade, pg, nome as nome_guerra, nome_completo, fracao, pelotao, presenca, falta, justificativa, ultimo_gerente, ultima_atualizacao FROM militares WHERE pelotao = %s", conn, params=(filtro_pelotao,))
    else:
        df_militares = pd.read_sql_query("SELECT identidade, pg, nome as nome_guerra, nome_completo, fracao, pelotao, presenca, falta, justificativa, ultimo_gerente, ultima_atualizacao FROM militares", conn)
    
    agora_exibicao = datetime.now().strftime("%d/%m/%Y")
    for index, row in df_militares.iterrows():
        if row['identidade'] in ferias_ativas:
            df_militares.at[index, 'falta'] = 1
            df_militares.at[index, 'presenca'] = 0
            df_militares.at[index, 'justificativa'] = f"Férias ({ferias_ativas[row['identidade']]})"
            df_militares.at[index, 'ultimo_gerente'] = "Sistema Automático (Férias)"
            df_militares.at[index, 'ultima_atualizacao'] = agora_exibicao
            
    ordem_hierarquica = ["Gen Ex", "Gen Div", "Gen Bda", "Cel", "Ten Cel", "Maj", "Cap", "1º Ten", "2º Ten", "Asp Of", "S Ten", "1º Sgt", "2º Sgt", "3º Sgt", "Cb", "Sd EP", "Sd EV"]
    pg_upper_map = {rank.upper(): rank for rank in ordem_hierarquica}
            
    abas_nomes = ["🗺️ MAPA", "✈️ Livro de Viagens", "📋 Plano de Chamada"]
    if is_cmt_om: abas_nomes.append("📚 Histórico de Faltas")
    else: abas_nomes.append("🏢 Gestão do Pelotão")
        
    abas = st.tabs(abas_nomes)
    
    with abas[0]: # MAPA
        st.subheader("Mapa Geral do Efetivo em Tempo Real")
        df_mapa = df_militares.copy()
        
        df_mapa['pg_norm'] = df_mapa['pg'].str.upper().map(pg_upper_map).fillna(df_mapa['pg'])
        df_mapa['pg_cat'] = pd.Categorical(df_mapa['pg_norm'], categories=ordem_hierarquica, ordered=True)
        df_mapa = df_mapa.sort_values(['pg_cat', 'nome_guerra']).drop(columns=['pg_cat', 'pg_norm'])
        
        df_mapa['STATUS'] = df_mapa.apply(lambda r: 'PRESENTE' if r['presenca']==1 else ('FALTOU' if r['falta']==1 else 'PENDENTE'), axis=1)
        
        st.dataframe(df_mapa[['pg', 'nome_guerra', 'nome_completo', 'fracao', 'pelotao', 'STATUS', 'justificativa', 'ultimo_gerente', 'ultima_atualizacao']], hide_index=True, use_container_width=True)
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Efetivo Total", len(df_mapa))
        c2.metric("Presentes", len(df_mapa[df_mapa['STATUS'] == 'PRESENTE']))
        c3.metric("Faltas / Férias", len(df_mapa[df_mapa['STATUS'] == 'FALTOU']))
        c4.metric("Pendentes", len(df_mapa[df_mapa['STATUS'] == 'PENDENTE']))
        
        # Botão de Consolidação para Cmt Pelotão (Com limpeza automática dos dados manuais)
        if not is_cmt_om:
            st.markdown("---")
            if st.button("✔️ Finalizar e Consolidar Chamada do Pelotão", type="primary"):
                agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                cmt_nome = f"Cmt Pel - {st.session_state.pg} {st.session_state.nome_guerra}"
                cur = conn.cursor()
                for idx, row in df_mapa.iterrows():
                    # 1. Salva no Histórico Oficial
                    cur.execute("INSERT INTO historico (data_hora, pg, nome, fracao, pelotao, status, justificativa, gerente_responsavel) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                                (agora, row['pg'], row['nome_guerra'], row['fracao'], row['pelotao'], row['STATUS'], row['justificativa'], cmt_nome))
                
                # 2. Reseta a tiragem de faltas manuais do pelotão para branco (presenca=0, falta=0, justificativa=''), preservando quem está de férias
                ids_ferias = list(ferias_ativas.keys())
                if ids_ferias:
                    format_strings = ','.join(['%s'] * len(ids_ferias))
                    cur.execute(f"UPDATE militares SET presenca = 0, falta = 0, justificativa = '', ultimo_gerente = '-', ultima_atualizacao = '-' WHERE pelotao = %s AND identidade NOT IN ({format_strings})", tuple([filtro_pelotao] + ids_ferias))
                else:
                    cur.execute("UPDATE militares SET presenca = 0, falta = 0, justificativa = '', ultimo_gerente = '-', ultima_atualizacao = '-' WHERE pelotao = %s", (filtro_pelotao,))
                
                conn.commit()
                st.success("✅ Chamada do pelotão consolidada com sucesso, enviada para o Histórico da OM e os campos manuais foram limpos para o próximo dia!")
                st.rerun()

    with abas[1]: # VIAGENS
        st.subheader("Registros do Livro de Viagens")
        if filtro_pelotao:
            df_viagens = pd.read_sql_query("""
                SELECT m.pg, m.nome as nome_guerra, m.nome_completo, v.fracao, v.pelotao, v.data_ida, v.data_volta, v.cidade, v.pais 
                FROM viagens v 
                INNER JOIN militares m ON v.identidade = m.identidade
                WHERE v.pelotao = %s ORDER BY v.data_ida DESC
            """, conn, params=(filtro_pelotao,))
        else:
            df_viagens = pd.read_sql_query("""
                SELECT m.pg, m.nome as nome_guerra, m.nome_completo, v.fracao, v.pelotao, v.data_ida, v.data_volta, v.cidade, v.pais 
                FROM viagens v 
                INNER JOIN militares m ON v.identidade = m.identidade
                ORDER BY v.data_ida DESC
            """, conn)
        
        if not df_viagens.empty: st.dataframe(df_viagens, hide_index=True, use_container_width=True)
        else: st.info("Nenhuma viagem registrada.")

    with abas[2]: # PLANO DE CHAMADA
        st.subheader("Plano de Chamada")
        if filtro_pelotao:
            df_plano = pd.read_sql_query("SELECT pg, nome as nome_guerra, nome_completo, fracao, celular, whatsapp, telefone as residencial, email, endereco FROM militares WHERE pelotao = %s", conn, params=(filtro_pelotao,))
        else:
            df_plano = pd.read_sql_query("SELECT pg, nome as nome_guerra, nome_completo, fracao, pelotao, celular, whatsapp, telefone as residencial, email, endereco FROM militares", conn)
            
        df_plano['pg_norm'] = df_plano['pg'].str.upper().map(pg_upper_map).fillna(df_plano['pg'])
        df_plano['pg_cat'] = pd.Categorical(df_plano['pg_norm'], categories=ordem_hierarquica, ordered=True)
        df_plano = df_plano.sort_values(['pg_cat', 'nome_guerra']).drop(columns=['pg_cat', 'pg_norm'])
        
        st.dataframe(df_plano, hide_index=True, use_container_width=True)
        
    with abas[3]: 
        if is_cmt_om: # HISTÓRICO OM (Com correção do visual da impressão PDF limpa)
            st.subheader("Histórico de Faltas Consolidado")
            st.write("Filtre o histórico por data para visualização e impressão.")
            data_filtro = st.date_input("Selecione a Data")
            data_str = data_filtro.strftime("%d/%m/%Y")
            
            df_hist = pd.read_sql_query(f"SELECT data_hora as Data_Hora, pg as PG, nome as Nome_de_Guerra, fracao as Fracao, pelotao as Pelotao, status as Status, justificativa as Justificativa, gerente_responsavel as Responsavel FROM historico WHERE data_hora LIKE '{data_str}%%' ORDER BY data_hora DESC", conn)
            
            if not df_hist.empty:
                st.dataframe(df_hist, hide_index=True, use_container_width=True)
                
                # HTML otimizado com fundo branco e texto escuro para legibilidade perfeita na impressão PDF
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
        else: # GESTÃO CMT PEL
            st.subheader(f"Gestão de Frações - {filtro_pelotao}")
            with st.form("solicitar_fracao"):
                nova_f = st.text_input("Solicitar Criação de Nova Fração para o seu Pelotão")
                if st.form_submit_button("Enviar Solicitação ao Administrador"):
                    try:
                        cur = conn.cursor()
                        cur.execute("INSERT INTO fracoes (nome_fracao, pelotao, status) VALUES (%s, %s, 'PENDENTE')", (nova_f.strip(), filtro_pelotao))
                        conn.commit()
                        st.success("✅ Solicitação enviada! O Administrador precisa autorizar.")
                    except:
                        st.error("Esta fração já existe ou já foi solicitada.")
            
    conn.close()

def tela_comandante_pelotao():
    tela_comandante_generica(f"Painel do Cmt - {st.session_state.pelotao}", is_cmt_om=False)

def tela_comandante_om():
    tela_comandante_generica("🛡️ Painel do Comandante de OM", is_cmt_om=True)

# --- FLUXO PRINCIPAL ---
if 'logado' not in st.session_state:
    st.session_state.logado = False

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